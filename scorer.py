#!/usr/bin/env python3
"""Calificadora de riesgo on-chain — motor de scoring v2.

Puntua cualquier cuenta de Hyperliquid con datos 100% publicos. No necesita
permiso, credenciales, ni que el calificado se entere.

QUE MIDE
--------
Una sola cosa: que tanto riesgo de destruccion carga la cuenta. NO predice
precios ni rendimientos. Una calificacion A no significa que vaya a ganar.

EN QUE SE BASA — y por que casi no usa Kelly
--------------------------------------------
El criterio de Kelly dice que existe un tamaño de apuesta optimo (f* = mu/sigma^2)
y que arriba del doble de ese tamaño el crecimiento de largo plazo es negativo
AUNQUE la apuesta tenga ventaja. Es correcto y es de 1956.

El problema es que Kelly necesita mu — el rendimiento esperado — y mu es lo mas
dificil de estimar que hay. Medido sobre BTC, el punto de ruina sale en 3.06x o
en 7.63x segun la ventana que escojas. Un puntaje construido sobre eso es fragil.

Por eso el nucleo del puntaje NO usa mu. Califica sobre lo medible:

  1. VOLATILIDAD DE LA CUENTA  — vol anual del portafolio / patrimonio.
     Usa vol y correlaciones reales por moneda (ver mercado.py). Las posiciones
     entran CON SIGNO: un largo contra un corto se cancela, como debe ser.
  2. DISTANCIA A LIQUIDACION   — un hecho, no una estimacion.
  3. APUESTAS EFECTIVAS        — cuantas apuestas independientes hay de verdad.
     Con correlacion media de 0.64, cinco altcoins no son cinco apuestas.

Kelly se REPORTA como referencia, con el supuesto de mu escrito y visible, para
que quien lea pueda cambiarlo y recalcular. Pesa poco en el puntaje.
"""
from __future__ import annotations
import json, math, os, time, urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

import mercado

API = "https://api.hyperliquid.xyz/info"
MU_SUPUESTO = 0.55        # deriva anual asumida para el marco de Kelly.
                          # ES UN SUPUESTO. Se publica para que se pueda discutir.
PATRIMONIO_MIN = 100.0
MATERIALIDAD = 0.05      # una posicion bajo 5% del patrimonio no fija el riesgo de la cuenta


def post(payload, reintentos=3):
    for i in range(reintentos):
        try:
            req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception:
            if i == reintentos - 1:
                raise
            time.sleep(0.6 * (i + 1))


@dataclass
class Calificacion:
    wallet: str
    fecha: str
    patrimonio: float
    nocional: float             # bruto, suma de valores absolutos
    exposicion: float           # nocional bruto / patrimonio
    vol_cuenta: float           # VOL ANUAL DE LA CUENTA / patrimonio  <- nucleo
    dist_liquidacion: float
    n_posiciones: int
    n_aisladas: int
    apuestas_efectivas: float   # posiciones independientes de verdad
    concentracion: float
    kelly_ratio: float          # referencia, depende de MU_SUPUESTO
    mu_supuesto: float
    puntos: int
    grado: str
    banderas: list = field(default_factory=list)


def _grado(p):
    return "A" if p < 20 else "B" if p < 40 else "C" if p < 60 else "D" if p < 80 else "F"


def calificar(wallet: str, m=None) -> Calificacion | None:
    m = m or mercado.cargar()
    st = post({"type": "clearinghouseState", "user": wallet})
    ms = st.get("marginSummary", {})
    pos = st.get("assetPositions", [])
    base = float(ms.get("accountValue", 0) or 0)
    flot = sum(float(a["position"].get("unrealizedPnl") or 0) for a in pos)
    patr = base + flot
    if patr <= 0:
        return None

    # posiciones CON SIGNO: szi negativo = corto
    firmadas, bruto, mayor, dmin = [], 0.0, 0.0, 1.0
    n_aisladas = 0
    for a in pos:
        p = a["position"]
        szi = float(p["szi"])
        pv = float(p["positionValue"])
        if pv <= 0:
            continue
        firmadas.append((p["coin"], pv if szi > 0 else -pv))
        bruto += pv
        mayor = max(mayor, pv)

        # La distancia a liquidacion de la CUENTA solo la fijan posiciones que
        # de verdad pueden tumbarla. Dos filtros, los dos aprendidos de un caso
        # real: una cuenta de $42,647 salia con "liquidacion a 12%" por una
        # posicion AISLADA de $21 cuya perdida maxima era $27.
        #   1. aislada  -> la perdida esta acotada al margen de esa posicion
        #   2. inmaterial -> menos de MATERIALIDAD del patrimonio, no mueve la aguja
        aislada = str((p.get("leverage") or {}).get("type", "")).lower() == "isolated"
        if aislada:
            n_aisladas += 1
            continue
        if pv < MATERIALIDAD * patr:
            continue
        lq = float(p.get("liquidationPx") or 0)
        if lq > 0 and abs(szi) > 0:
            mk = pv / abs(szi)
            dmin = min(dmin, abs(mk - lq) / mk)

    vol_usd, vol_unit, efectivas = mercado.riesgo_portafolio(m, firmadas)
    vol_cuenta = vol_usd / patr if patr > 0 else 0.0
    exp = bruto / patr if patr > 0 else 0.0
    conc = mayor / bruto if bruto > 0 else 0.0

    # Kelly SOLO como referencia. L_ruina = 2*mu/sigma_unitaria^2
    l_ruina = (2 * MU_SUPUESTO / vol_unit ** 2) if vol_unit > 0 else 0.0
    kelly_ratio = (exp / l_ruina) if l_ruina > 0 else 0.0

    pts, banderas = 0, []

    # 1. volatilidad de la cuenta — el nucleo, sin mu
    if vol_cuenta > 2.00:
        pts += 45; banderas.append(f"volatilidad de cuenta {vol_cuenta*100:.0f}% anual — extrema")
    elif vol_cuenta > 1.20:
        pts += 35; banderas.append(f"volatilidad de cuenta {vol_cuenta*100:.0f}% anual — muy alta")
    elif vol_cuenta > 0.70:
        pts += 22; banderas.append(f"volatilidad de cuenta {vol_cuenta*100:.0f}% anual — alta")
    elif vol_cuenta > 0.45:
        pts += 10; banderas.append(f"volatilidad de cuenta {vol_cuenta*100:.0f}% anual")

    # 2. distancia a liquidacion — hecho
    if bruto > 0:
        if dmin < 0.10:
            pts += 40; banderas.append(f"liquidacion a {dmin*100:.0f}% — critico")
        elif dmin < 0.20:
            pts += 28; banderas.append(f"liquidacion a {dmin*100:.0f}%")
        elif dmin < 0.35:
            pts += 15; banderas.append(f"liquidacion a {dmin*100:.0f}%")

    # 3. diversificacion EFECTIVA, no numero de posiciones
    if bruto > 0 and exp > 2 and efectivas < 1.3:
        pts += 8
        banderas.append(f"{len(firmadas)} posiciones pero solo {efectivas:.1f} apuestas "
                        f"independientes — correlacionadas")

    # 4. Kelly, referencia con supuesto explicito, peso bajo
    if kelly_ratio > 2.0:
        pts += 7
        banderas.append(f"{kelly_ratio:.1f}x el punto de ruina de Kelly "
                        f"(supuesto mu={MU_SUPUESTO*100:.0f}%)")

    pts = min(pts, 100)
    return Calificacion(
        wallet=wallet,
        fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        patrimonio=round(patr, 2), nocional=round(bruto, 2),
        exposicion=round(exp, 3), vol_cuenta=round(vol_cuenta, 4),
        dist_liquidacion=round(dmin, 4), n_posiciones=len(firmadas),
        n_aisladas=n_aisladas,
        apuestas_efectivas=round(efectivas, 2), concentracion=round(conc, 3),
        kelly_ratio=round(kelly_ratio, 2), mu_supuesto=MU_SUPUESTO,
        puntos=pts, grado=_grado(pts), banderas=banderas)


# ---------- universo ----------

def top_monedas(n=20):
    try:
        meta, ctx = post({"type": "metaAndAssetCtxs"})
        pares = [(meta["universe"][i]["name"], float(c.get("dayNtlVlm") or 0))
                 for i, c in enumerate(ctx)]
        pares.sort(key=lambda x: -x[1])
        return [mm for mm, _ in pares[:n]]
    except Exception:
        return ["BTC", "ETH", "SOL", "HYPE", "XRP", "DOGE"]


def cosechar(rondas=8, pausa=25, monedas=None):
    """recentTrades solo da 10 trades por moneda: una pasada rinde ~50 wallets.
    Se barre varias veces con pausa para atrapar trades distintos."""
    monedas = monedas or top_monedas(20)
    ws = set()
    for r in range(rondas):
        for c in monedas:
            try:
                for t in post({"type": "recentTrades", "coin": c}):
                    for u in t.get("users", []):
                        if u and u != "0x" + "0" * 40:
                            ws.add(u.lower())
            except Exception:
                pass
            time.sleep(0.12)
        if r < rondas - 1:
            time.sleep(pausa)
    return ws


def cargar_universo(ruta="universo.json"):
    try:
        return json.load(open(ruta))
    except Exception:
        return {}


def guardar_universo(u, ruta="universo.json"):
    json.dump(u, open(ruta, "w"), indent=1, sort_keys=True)


def wallet_propia():
    """La wallet de la casa SIEMPRE va en el indice, calificada con el mismo
    criterio que las demas. Publicar la propia mala nota es lo que ninguna
    cuenta de trading hace, y es justo lo que hace creible al resto."""
    d = os.getenv("HYPERLIQUID_WALLET_ADDRESS", "").strip().strip('"')
    if d:
        return d.lower()
    for ruta in ("/root/bitarrow/.env", "../.env", ".env"):
        try:
            for ln in open(ruta):
                if ln.startswith("HYPERLIQUID_WALLET_ADDRESS"):
                    return ln.split("=", 1)[1].strip().strip('"').strip("'").lower()
        except Exception:
            pass
    return None


if __name__ == "__main__":
    import sys
    from collections import Counter

    m = mercado.cargar()
    print(f"  mercado: {len(m['vol'])} monedas medidas sobre {m['dias']} dias "
          f"(cache {m['fecha']})")

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    propia = wallet_propia()

    consulta = len(sys.argv) > 1     # consulta puntual: NO toca el indice del dia
    if consulta:
        objetivo = [w.lower() for w in sys.argv[1:]]
    else:
        u = cargar_universo()
        antes = len(u)
        for w in cosechar():
            u.setdefault(w, {"primera_vez": hoy})
        if propia:
            u.setdefault(propia, {"primera_vez": hoy, "casa": True})
        guardar_universo(u)
        print(f"  universo: {antes} -> {len(u)} (+{len(u)-antes} nuevas)")
        objetivo = sorted(u, key=lambda w: u[w]["primera_vez"])

    print(f"  calificando {len(objetivo)} wallets...\n")
    print(f"  {'wallet':<14}{'gr':>3}{'pts':>5}{'patrimonio':>14}"
          f"{'vol cta':>9}{'expo':>7}{'liq':>6}{'apuestas':>10}  bandera")
    res, vacias = [], 0
    for w in objetivo:
        try:
            c = calificar(w, m)
            time.sleep(0.1)
            if not c or c.patrimonio < PATRIMONIO_MIN:
                vacias += 1
                continue
            res.append(c)
            marca = " <-CASA" if propia and w == propia else ""
            b = (c.banderas[0][:40] if c.banderas else "") + marca
            print(f"  {w[:12]:<14}{c.grado:>3}{c.puntos:>5}{c.patrimonio:>14,.0f}"
                  f"{c.vol_cuenta*100:>8.0f}%{c.exposicion:>6.1f}x"
                  f"{c.dist_liquidacion*100:>5.0f}%{c.apuestas_efectivas:>10.1f}  {b}")
        except Exception:
            continue

    if res and not consulta:
        f = f"indice_{datetime.now().strftime('%Y%m%d')}.json"
        json.dump({"fecha": datetime.now(timezone.utc).isoformat(),
                   "mu_supuesto": MU_SUPUESTO,
                   "mercado": {"dias": m["dias"], "fecha": m["fecha"]},
                   "wallets": [asdict(x) for x in res]},
                  open(f, "w"), indent=2)
        d = Counter(x.grado for x in res)
        print(f"\n  {len(res)} calificaciones -> {f}")
        print(f"  {vacias} wallets del universo bajo ${PATRIMONIO_MIN:,.0f}")
        print("  distribucion: " + "  ".join(f"{g}:{d.get(g,0)}" for g in "ABCDF"))
    elif res:
        print(f"\n  consulta puntual: {len(res)} wallets. NO se escribio el indice del dia.")
