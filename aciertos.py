#!/usr/bin/env python3
"""Verificacion de grados. ESTE es el activo: el registro fechado de si los
grados aciertan.

QUE MIDE Y QUE NO
-----------------
La calificacion contesta una sola pregunta: "¿que tan cerca esta esta cuenta
de ser liquidada?". Entonces la verificacion mide UNA sola cosa:

    ¿esta wallet perdio dinero en liquidaciones forzadas, si o no?

Eso sale de los fills marcados 'liquidation' con closedPnl negativo. Es un
hecho on-chain, sin valuar nada, sin suponer nada. Es la metrica principal.

Todo lo demas es secundario y se marca como tal, porque medir "cuanto gano o
perdio esta persona" exige valuar spot, staking, boveda y subcuentas — y cada
intento de hacerlo produjo un numero falso:

  - patrimonio de perp en cero se leia como muerte: era gente que se movio a
    spot. Un "destruido" tenia $2,205,079 USDC en spot.
  - los fills 'liquidation' se contaban completos: HL tambien marca al que
    ABSORBE la liquidacion, y ese gana. Salian "wallets grado A liquidadas".
  - valuar spot por posicion del indice cruzaba precios entre tokens y
    producia patrimonios de $2,697,995,123.
  - ignorar en silencio el tipo 'send' desaparecia retiros enteros.

Regla final: lo que no se puede medir exacto se marca NO MEDIBLE y se saca de
la muestra. Una n mas chica y honesta vale mas que un numero grande y falso.
"""
import json, glob, sys, time, urllib.request
from datetime import datetime, timezone

API = 'https://api.hyperliquid.xyz/info'
UMBRAL_DESTRUCCION = 0.30      # perdida por liquidacion > 30% del patrimonio
UMBRAL_FLUJO = 0.50            # flujos > 50% -> el rendimiento no es medible

FLUJOS = {'deposit': +1, 'withdraw': -1,
          'vaultwithdraw': +1, 'vaultdeposit': -1, 'vaultcreate': -1,
          'accountclasstransfer': 0, 'internaltransfer': 0,
          'cstakingtransfer': 0, 'spotgenesis': 0, 'rewardsclaim': +1}
DIRIGIDOS = ('send', 'spottransfer', 'subaccounttransfer')


def post(payload, reintentos=3):
    for i in range(reintentos):
        try:
            req = urllib.request.Request(
                API, data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            if i == reintentos - 1:
                raise
            time.sleep(1.5)


_px = None
def precio(token):
    """markPx del token contra USDC. Se mapea POR NOMBRE de par: los indices
    de universe (326) y ctx (718) no corresponden."""
    global _px
    if _px is None:
        _px = {'USDC': 1.0}
        try:
            meta, ctx = post({'type': 'spotMetaAndAssetCtxs'})
            por_coin = {c['coin']: c for c in ctx}
            nombre = {t['index']: t['name'] for t in meta['tokens']}
            for par in meta['universe']:
                base, quote = nombre.get(par['tokens'][0]), nombre.get(par['tokens'][1])
                c = por_coin.get(par['name'])
                if base and quote == 'USDC' and c:
                    p = c.get('markPx') or c.get('midPx')
                    if p:
                        _px.setdefault(base, float(p))
        except Exception:
            pass
    return _px.get(token, 0.0)


def perp(wallet):
    st = post({'type': 'clearinghouseState', 'user': wallet})
    ms = st.get('marginSummary', {})
    return (float(ms.get('accountValue', 0) or 0)
            + sum(float(a['position'].get('unrealizedPnl') or 0)
                  for a in st.get('assetPositions', [])))


def fondos_fuera(wallet):
    """Dinero del usuario que NO esta en perp. Solo se usa para distinguir
    'se salio' de 'lo perdio' — nunca para calcular rendimiento. Se cuenta
    USDC de spot y HYPE en staking, que son los dos valuables sin ambiguedad."""
    total = 0.0
    try:
        for b in post({'type': 'spotClearinghouseState',
                       'user': wallet}).get('balances', []):
            if b.get('coin') == 'USDC':
                total += float(b.get('total') or 0)
    except Exception:
        pass
    try:
        d = post({'type': 'delegatorSummary', 'user': wallet})
        hype = (float(d.get('delegated') or 0) + float(d.get('undelegated') or 0)
                + float(d.get('totalPendingWithdrawal') or 0))
        total += hype * precio('HYPE')
    except Exception:
        pass
    return total


def forense(wallet, desde_ms, ahora_ms):
    perdida = 0.0
    try:
        for f in post({'type': 'userFillsByTime', 'user': wallet,
                       'startTime': desde_ms}):
            if f.get('liquidation'):
                pnl = float(f.get('closedPnl') or 0)
                if pnl < 0:
                    perdida += -pnl
    except Exception:
        pass

    neto = pond = 0.0
    span = max(ahora_ms - desde_ms, 1)
    raros = set()
    try:
        for m in post({'type': 'userNonFundingLedgerUpdates', 'user': wallet,
                       'startTime': desde_ms}):
            d = m.get('delta', {})
            t = str(d.get('type', '')).lower()
            monto = abs(float(d.get('usdcValue') or d.get('usdc') or 0))
            if t in DIRIGIDOS:
                signo = -1 if str(d.get('user','')).lower() == wallet.lower() else +1
            elif t in FLUJOS:
                signo = FLUJOS[t]
            else:
                raros.add(t); continue
            if signo == 0 or monto == 0:
                continue
            w_i = max(0.0, min(1.0, (ahora_ms - m.get('time', desde_ms)) / span))
            neto += signo * monto
            pond += signo * monto * w_i
    except Exception:
        pass
    return perdida, neto, pond, raros


def main():
    archivos = sorted(glob.glob("indice_*.json"))
    if len(archivos) < 2:
        print(f"  hay {len(archivos)} indice(s). Necesitas al menos 2 fechas.")
        sys.exit(0)

    _d = json.load(open(archivos[0]))
    viejo = _d["wallets"] if isinstance(_d, dict) else _d   # v2 trae metadatos
    fecha = archivos[0][7:15]
    desde = datetime(int(fecha[:4]), int(fecha[4:6]), int(fecha[6:8]), tzinfo=timezone.utc)
    ahora = datetime.now(timezone.utc)
    desde_ms, ahora_ms = int(desde.timestamp()*1000), int(ahora.timestamp()*1000)
    dias = (ahora - desde).days

    print(f"\n  BITARROW — verificacion de grados")
    print(f"  indice del {fecha}  vs  {ahora:%Y-%m-%d}   ({dias} dias)\n")
    print(f"  {'wallet':<13}{'gr':>3}{'V0 perp':>13}{'V1 perp':>13}"
          f"{'perd. liq':>12}{'% de V0':>9}{'  estado'}")
    print("  " + "-" * 82)

    dest, rend, raros_tot = {}, {}, set()
    for c in viejo:
        try:
            v0 = c['patrimonio']; g = c['grado']
            if v0 <= 0:
                continue
            v1 = perp(c['wallet']); time.sleep(0.12)
            perd, neto, pond, raros = forense(c['wallet'], desde_ms, ahora_ms)
            time.sleep(0.12)
            raros_tot |= raros
            ratio = perd / v0

            # --- metrica principal: destruccion por liquidacion ---
            destruido = ratio > UMBRAL_DESTRUCCION
            dest.setdefault(g, []).append(destruido)

            if destruido:
                estado = "DESTRUIDO por liquidacion"
            elif perd > 0:
                estado = "liquidado parcial"
            elif v1 < v0 * 0.05:
                estado = "salio" if fondos_fuera(c['wallet']) > v0*0.2 else "perp vacio"
            else:
                estado = "activo"

            # --- metrica secundaria: rendimiento del perp, si es medible ---
            if not raros and abs(neto) <= UMBRAL_FLUJO * v0 and (v0 + pond) > 0:
                rend.setdefault(g, []).append((v1 - v0 - neto) / (v0 + pond))

            print(f"  {c['wallet'][:11]:<13}{g:>3}{v0:>13,.0f}{v1:>13,.0f}"
                  f"{perd:>12,.0f}{ratio*100:>8.1f}%  {estado}")
        except Exception:
            continue

    print(f"\n  === METRICA PRINCIPAL: TASA DE DESTRUCCION POR GRADO ===")
    print(f"  (wallets que perdieron >{UMBRAL_DESTRUCCION*100:.0f}% de su patrimonio")
    print(f"   en liquidaciones forzadas. Hecho on-chain, sin valuar nada.)\n")
    for g in "ABCDF":
        if g in dest:
            l = dest[g]
            print(f"    grado {g}:  {sum(l)}/{len(l)}  =  {sum(l)/len(l)*100:5.1f}%")

    print(f"\n  --- secundario: rendimiento del perp (ajustado por flujos) ---")
    for g in "ABCDF":
        if g in rend and rend[g]:
            l = sorted(rend[g])
            print(f"    grado {g}:  mediana {l[len(l)//2]*100:+7.1f}%   (n={len(l)}"
                  f" de {len(dest.get(g,[]))} medibles)")

    if raros_tot:
        print(f"\n  tipos de movimiento no reconocidos: {sorted(raros_tot)}")

    n = sum(len(v) for v in dest.values())
    print(f"\n  muestra: {n} wallets / {dias} dias.")
    if n < 50 or dias < 30:
        print(f"  ADVERTENCIA: con n<50 o ventana <30d esto NO es significativo.")


if __name__ == '__main__':
    main()
