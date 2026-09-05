#!/usr/bin/env python3
import json, math, os
from datetime import datetime, timezone
os.chdir('/root/bitarrow/riesgo_onchain')

VENTANA, PASO, CORTE = 90, 15, 280
CORR_DESC, VOL_DESC = 0.70, 1.20

carteras = json.load(open("posiciones_hoy.json"))
# la distancia a liquidacion es un HECHO de hoy, no una estimacion: se toma del
# indice de produccion. No hay fuga: no depende de precios futuros.
_idx = json.load(open("indice_20260905.json"))["wallets"]
DIST = {x["wallet"]: x["dist_liquidacion"] for x in _idx}
px = {k: {int(a): b for a, b in v.items()} for k, v in json.load(open("precios_largos.json")).items()}
meta = json.load(open("meta_cache.json")) if os.path.exists("meta_cache.json") else None
import urllib.request
if meta is None:
    q=urllib.request.Request("https://api.hyperliquid.xyz/info",
        data=json.dumps({"type":"meta"}).encode(),headers={"Content-Type":"application/json"})
    meta=json.load(urllib.request.urlopen(q,timeout=30)); json.dump(meta,open("meta_cache.json","w"))
mm = {a["name"]: 1.0/(2.0*a["maxLeverage"]) for a in meta["universe"]}

todas = sorted({t for s in px.values() for t in s})
i_corte = len(todas) - CORTE
pre = todas[:i_corte]                       # SOLO esto ve el modelo
print(f"  calendario {len(todas)}d  |  entrenamiento {len(pre)}d hasta "
      f"{datetime.fromtimestamp(pre[-1]/1000, timezone.utc):%Y-%m-%d}")

# --- vol y correlacion con datos PRE-corte unicamente ---
ret = {}
for c, s in px.items():
    fs = [t for t in sorted(s) if t <= pre[-1]]
    if len(fs) < 60: continue
    ret[c] = {fs[i]: math.log(s[fs[i]]/s[fs[i-1]]) for i in range(1, len(fs)) if s[fs[i-1]]>0}
vol, med, dv = {}, {}, {}
for c, r in ret.items():
    v = list(r.values()); k = len(v)
    if k < 40: continue
    m_ = sum(v)/k; s_ = math.sqrt(sum((x-m_)**2 for x in v)/(k-1))
    med[c], dv[c], vol[c] = m_, s_, s_*math.sqrt(365)
print(f"  volatilidades estimadas con datos previos: {len(vol)} monedas")

_cc = {}
def corr(a, b):
    if a == b: return 1.0
    k = (a,b) if a<b else (b,a)
    if k in _cc: return _cc[k]
    if a not in ret or b not in ret: _cc[k]=CORR_DESC; return CORR_DESC
    com = sorted(set(ret[a]) & set(ret[b]))
    if len(com) < 40 or dv.get(a,0)==0 or dv.get(b,0)==0: _cc[k]=CORR_DESC; return CORR_DESC
    ma=sum(ret[a][f] for f in com)/len(com); mb=sum(ret[b][f] for f in com)/len(com)
    sa=math.sqrt(sum((ret[a][f]-ma)**2 for f in com)/(len(com)-1))
    sb=math.sqrt(sum((ret[b][f]-mb)**2 for f in com)/(len(com)-1))
    if sa==0 or sb==0: _cc[k]=CORR_DESC; return CORR_DESC
    cv=sum((ret[a][f]-ma)*(ret[b][f]-mb) for f in com)/(len(com)-1)
    _cc[k]=max(-1,min(1,cv/(sa*sb))); return _cc[k]

def vd(c): return vol.get(c, VOL_DESC)

# --- calificar con esas vol (sin ver el futuro) ---
def calificar(eq, pos, dmin=1.0):
    firm=[(p[0], p[1]*p[2]) for p in pos]
    bruto=sum(abs(v) for _,v in firm)
    if bruto<=0: return None
    var=sum(va*vb*vd(a)*vd(b)*corr(a,b) for a,va in firm for b,vb in firm)
    volusd=math.sqrt(max(var,0)); volc=volusd/eq
    den=sum(abs(va)*abs(vb)*corr(a,b) for a,va in firm for b,vb in firm)
    efec=(bruto**2/den) if den>0 else 0
    exp=bruto/eq
    pts=0
    if volc>2.0: pts+=45
    elif volc>1.2: pts+=35
    elif volc>0.7: pts+=22
    elif volc>0.45: pts+=10
    if bruto>0:
        if dmin<0.10: pts+=40
        elif dmin<0.20: pts+=28
        elif dmin<0.35: pts+=15
    if exp>2 and efec<1.3: pts+=8
    neto=sum(v for _,v in firm)
    return min(pts,100), volc, exp, efec, neto/bruto

# --- simular ventanas rodantes ---
def simular(eq, pos, ini, fin):
    us=[p for p in pos if p[0] in px]
    if not us: return None
    cub=sum(abs(p[1]*p[2]) for p in us); tot=sum(abs(p[1]*p[2]) for p in pos)
    if tot<=0 or cub/tot<0.8: return None
    fs=[t for t in todas[ini:fin] if all(t in px[p[0]] for p in us)]
    if len(fs)<VENTANA*0.7: return None
    p0={p[0]:px[p[0]][fs[0]] for p in us}
    esc=eq/cub if cub>0 else 1     # normaliza: mismo apalancamiento, capital=eq
    for t in fs:
        pnl=sum(p[1]*(px[p[0]][t]-p0[p[0]]) for p in us)
        e=eq+pnl
        req=sum(abs(p[1])*px[p[0]][t]*mm.get(p[0],0.02) for p in us)
        if e<=req: return True
    return False

inicios=list(range(i_corte, len(todas)-VENTANA, PASO))
print(f"  {len(inicios)} ventanas de {VENTANA} dias\n")

grados={}
for w,c in carteras.items():
    r=calificar(c["eq"], c["pos"], DIST.get(w, 1.0))
    if r: grados[w]=r
print(f"  {len(grados)} carteras calificadas fuera de muestra\n")

def gr(p): return "A" if p<20 else "B" if p<40 else "C" if p<60 else "D" if p<80 else "F"

acum={g:[0,0] for g in "ABCDF"}
por_ventana=[]
for ini in inicios:
    fin=ini+VENTANA
    btc0,btc1=px["BTC"][todas[ini]], px["BTC"][todas[fin-1]]
    mercado=(btc1/btc0-1)
    cnt={g:[0,0] for g in "ABCDF"}
    for w,c in carteras.items():
        if w not in grados: continue
        g=gr(grados[w][0])
        s=simular(c["eq"], c["pos"], ini, fin)
        if s is None: continue
        cnt[g][1]+=1; acum[g][1]+=1
        if s: cnt[g][0]+=1; acum[g][0]+=1
    por_ventana.append((datetime.fromtimestamp(todas[ini]/1000,timezone.utc).strftime("%Y-%m-%d"),
                        mercado, cnt))

print("  TASA DE LIQUIDACION POR GRADO, VENTANA POR VENTANA")
print(f"  {'inicio':<12}{'BTC':>8}   " + "".join(f"{g:>8}" for g in "ABCDF"))
print("  "+"-"*62)
for f,m_,cnt in por_ventana:
    fila=f"  {f:<12}{m_*100:>+7.1f}%   "
    for g in "ABCDF":
        n,d=cnt[g][0],cnt[g][1]
        fila+=f"{(f'{n/d*100:.0f}%' if d else '—'):>8}"
    print(fila)

print(f"\n  AGREGADO SOBRE {len(inicios)} VENTANAS")
print(f"  {'grado':>6}{'simulaciones':>14}{'liquidadas':>12}{'tasa':>9}")
print("  "+"-"*43)
for g in "ABCDF":
    n,d=acum[g]
    if d: print(f"  {g:>6}{d:>14,}{n:>12,}{n/d*100:>8.1f}%")

ab=sum(acum[g][0] for g in "AB"); nab=sum(acum[g][1] for g in "AB")
df_=sum(acum[g][0] for g in "DF"); ndf=sum(acum[g][1] for g in "DF")
if nab and ndf:
    print(f"\n  A+B: {ab/nab*100:.1f}%   D+F: {df_/ndf*100:.1f}%   "
          f"discriminacion: {(df_/ndf)/(ab/nab):.1f}x" if ab else "")

print("\n  DIRECCION NETA POR GRADO (¿el grado captura riesgo o solo 'largo'?)")
print(f"  {'grado':>6}{'neto medio':>14}{'% netos largos':>17}")
print("  "+"-"*40)
for g in "ABCDF":
    ns=[grados[w][4] for w in grados if gr(grados[w][0])==g]
    if ns:
        print(f"  {g:>6}{sum(ns)/len(ns):>+13.2f}{sum(1 for x in ns if x>0)/len(ns)*100:>16.0f}%")
