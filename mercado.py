#!/usr/bin/env python3
"""Volatilidades y correlaciones reales por moneda, medidas de Hyperliquid.

Esto existe porque el scorer v1 usaba el punto de ruina de BTC para TODAS las
wallets. Medido sobre 180 dias, el punto de ruina va de 7.63x en BTC a 0.67x
en ZEC — once veces de diferencia. Calificar a los dos igual estaba mal.

Y porque contar posiciones no es diversificar: la correlacion media entre pares
de cripto grandes es 0.64, y BTC-ETH corre a 0.90. Cinco altcoins no son cinco
apuestas, son una apuesta con cinco nombres.
"""
import json, math, os, time, urllib.request
from datetime import datetime, timezone, timedelta

API = "https://api.hyperliquid.xyz/info"
DIAS = 180
VOL_DESCONOCIDA = 1.20      # moneda sin historia: se asume muy volatil
CORR_DESCONOCIDA = 0.70     # y muy correlacionada con todo. Conservador a proposito.


def _post(payload, reintentos=3):
    for i in range(reintentos):
        try:
            r = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                       headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(r, timeout=30))
        except Exception:
            if i == reintentos - 1:
                raise
            time.sleep(1.0 * (i + 1))


def _top_monedas(n=40):
    meta, ctx = _post({"type": "metaAndAssetCtxs"})
    pares = [(meta["universe"][i]["name"], float(c.get("dayNtlVlm") or 0))
             for i, c in enumerate(ctx)]
    pares.sort(key=lambda x: -x[1])
    return [m for m, _ in pares[:n]]


def medir(monedas=None, dias=DIAS):
    """Devuelve {'vol': {moneda: vol_anual}, 'corr': {a: {b: rho}}}"""
    monedas = monedas or _top_monedas()
    fin = int(datetime.now(timezone.utc).timestamp() * 1000)
    ini = int((datetime.now(timezone.utc) - timedelta(days=dias)).timestamp() * 1000)

    cierres = {}
    for c in monedas:
        try:
            v = _post({"type": "candleSnapshot",
                       "req": {"coin": c, "interval": "1d",
                               "startTime": ini, "endTime": fin}})
            if len(v) >= 30:
                cierres[c] = {int(x["t"]): math.log(float(x["c"])) for x in v}
            time.sleep(0.12)
        except Exception:
            pass
    if len(cierres) < 2:
        return {"vol": {}, "corr": {}, "dias": 0, "fecha": ""}

    # OJO: NO se usa la interseccion de fechas de todas las monedas. Una moneda
    # nueva con 56 dias arrastraria a BTC a 56 dias. Cada vol se mide sobre la
    # historia propia de esa moneda; cada correlacion sobre el traslape del par.
    ret = {}
    for c, s_ in cierres.items():
        fs = sorted(s_)
        ret[c] = {fs[i]: s_[fs[i]] - s_[fs[i-1]] for i in range(1, len(fs))}

    vol, media, desv, n_dias = {}, {}, {}, {}
    for c, r in ret.items():
        vals = list(r.values()); k = len(vals)
        if k < 20:
            continue
        m_ = sum(vals) / k
        s2 = math.sqrt(sum((x - m_) ** 2 for x in vals) / (k - 1))
        media[c], desv[c], n_dias[c] = m_, s2, k
        vol[c] = s2 * math.sqrt(365)

    corr = {}
    for a in vol:
        corr[a] = {}
        for b in vol:
            if a == b:
                corr[a][b] = 1.0
                continue
            comun = sorted(set(ret[a]) & set(ret[b]))
            if len(comun) < 20 or desv[a] == 0 or desv[b] == 0:
                corr[a][b] = CORR_DESCONOCIDA
                continue
            ma = sum(ret[a][f] for f in comun) / len(comun)
            mb = sum(ret[b][f] for f in comun) / len(comun)
            sa = math.sqrt(sum((ret[a][f]-ma)**2 for f in comun) / (len(comun)-1))
            sb = math.sqrt(sum((ret[b][f]-mb)**2 for f in comun) / (len(comun)-1))
            if sa == 0 or sb == 0:
                corr[a][b] = CORR_DESCONOCIDA
                continue
            cov = sum((ret[a][f]-ma)*(ret[b][f]-mb) for f in comun) / (len(comun)-1)
            corr[a][b] = max(-1.0, min(1.0, cov / (sa * sb)))

    n = max(n_dias.values()) if n_dias else 0
    return {"vol": vol, "corr": corr, "dias": n, "dias_por_moneda": n_dias,
            "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d")}


def cargar(ruta="mercado.json", max_edad_dias=7):
    """Lee el cache; lo regenera si no existe o esta viejo."""
    try:
        d = json.load(open(ruta))
        f = datetime.strptime(d["fecha"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - f).days <= max_edad_dias and d["vol"]:
            return d
    except Exception:
        pass
    d = medir()
    json.dump(d, open(ruta, "w"), indent=1)
    return d


def vol_de(m, moneda):
    return m["vol"].get(moneda, VOL_DESCONOCIDA)


def corr_de(m, a, b):
    if a == b:
        return 1.0
    try:
        return m["corr"][a][b]
    except KeyError:
        return CORR_DESCONOCIDA


def riesgo_portafolio(m, posiciones):
    """posiciones: [(moneda, valor_con_signo_usd), ...]
    Devuelve (vol_usd_anual, vol_por_unidad_de_nocional, apuestas_efectivas).

    Las posiciones llevan signo: un largo en BTC contra un corto en ETH se
    cancela parcialmente, como debe ser. Sumar nocionales ignora eso."""
    if not posiciones:
        return 0.0, 0.0, 0.0
    var = 0.0
    for a, va in posiciones:
        for b, vb in posiciones:
            var += va * vb * vol_de(m, a) * vol_de(m, b) * corr_de(m, a, b)
    vol_usd = math.sqrt(max(var, 0.0))

    bruto = sum(abs(v) for _, v in posiciones)
    vol_unit = vol_usd / bruto if bruto > 0 else 0.0

    # apuestas efectivas: (suma de pesos)^2 / (suma ponderada por correlacion)
    den = 0.0
    for a, va in posiciones:
        for b, vb in posiciones:
            den += abs(va) * abs(vb) * corr_de(m, a, b)
    efectivas = (bruto ** 2 / den) if den > 0 else 0.0
    return vol_usd, vol_unit, efectivas


if __name__ == "__main__":
    m = cargar()
    print(f"  medido sobre {m['dias']} dias, {len(m['vol'])} monedas\n")
    for c, v in sorted(m["vol"].items(), key=lambda x: -x[1])[:15]:
        print(f"  {c:<10}{v*100:>6.0f}%")
