#!/usr/bin/env python3
"""Auditoria historica. IMPORTA scorer.puntuar() — no reimplementa nada.
Asi la calibracion no puede divergir de produccion."""
import json, math, os, sys
from datetime import datetime, timezone
sys.path.insert(0, '/root/bitarrow/riesgo_onchain'); os.chdir('/root/bitarrow/riesgo_onchain')
from scorer import puntuar, _grado, TASA_HISTORICA          # <- la misma formula

VENTANA, PASO, CORTE = 90, 15, 280
CORR_DESC, VOL_DESC = 0.70, 1.20

carteras = json.load(open("posiciones_hoy.json"))
px = {k: {int(a): b for a, b in v.items()} for k, v in json.load(open("precios_largos.json")).items()}
DIST = {x["wallet"]: x["dist_liquidacion"] for x in json.load(open("indice_20260905.json"))["wallets"]}
meta = json.load(open("meta_cache.json"))
mm = {a["name"]: 1.0/(2.0*a["maxLeverage"]) for a in meta["universe"]}

todas = sorted({t for s in px.values() for t in s})
i_corte = len(todas) - CORTE
pre = todas[:i_corte]
print(f"  entrenamiento: {len(pre)}d hasta {datetime.fromtimestamp(pre[-1]/1000,timezone.utc):%Y-%m-%d}")

ret, vol, med, dv = {}, {}, {}, {}
for c, s in px.items():
    fs = [t for t in sorted(s) if t <= pre[-1]]
    if len(fs) < 60: continue
    ret[c] = {fs[i]: math.log(s[fs[i]]/s[fs[i-1]]) for i in range(1,len(fs)) if s[fs[i-1]]>0}
for c, r in ret.items():
    v=list(r.values()); k=len(v)
    if k<40: continue
    m_=sum(v)/k; s_=math.sqrt(sum((x-m_)**2 for x in v)/(k-1))
    med[c],dv[c],vol[c]=m_,s_,s_*math.sqrt(365)

_cc={}
def corr(a,b):
    if a==b: return 1.0
    k=(a,b) if a<b else (b,a)
    if k in _cc: return _cc[k]
    if a not in ret or b not in ret: _cc[k]=CORR_DESC; return CORR_DESC
    com=sorted(set(ret[a])&set(ret[b]))
    if len(com)<40 or dv.get(a,0)==0 or dv.get(b,0)==0: _cc[k]=CORR_DESC; return CORR_DESC
    ma=sum(ret[a][f] for f in com)/len(com); mb=sum(ret[b][f] for f in com)/len(com)
    sa=math.sqrt(sum((ret[a][f]-ma)**2 for f in com)/(len(com)-1))
    sb=math.sqrt(sum((ret[b][f]-mb)**2 for f in com)/(len(com)-1))
    if sa==0 or sb==0: _cc[k]=CORR_DESC; return CORR_DESC
    cv=sum((ret[a][f]-ma)*(ret[b][f]-mb) for f in com)/(len(com)-1)
    _cc[k]=max(-1,min(1,cv/(sa*sb))); return _cc[k]
def vd(c): return vol.get(c, VOL_DESC)

def puntos_oos(w, eq, pos):
    firm=[(p[0], p[1]*p[2]) for p in pos]
    bruto=sum(abs(v) for _,v in firm)
    if bruto<=0: return None
    var=sum(va*vb*vd(a)*vd(b)*corr(a,b) for a,va in firm for b,vb in firm)
    volc=math.sqrt(max(var,0))/eq
    den=sum(abs(va)*abs(vb)*corr(a,b) for a,va in firm for b,vb in firm)
    efec=(bruto**2/den) if den>0 else 0
    pts,_ = puntuar(volc, DIST.get(w,1.0), bruto/eq, efec, bruto, len(firm))
    return pts

def simular(eq,pos,ini,fin):
    us=[p for p in pos if p[0] in px]
    if not us: return None
    cub=sum(abs(p[1]*p[2]) for p in us); tot=sum(abs(p[1]*p[2]) for p in pos)
    if tot<=0 or cub/tot<0.8: return None
    fs=[t for t in todas[ini:fin] if all(t in px[p[0]] for p in us)]
    if len(fs)<VENTANA*0.7: return None
    p0={p[0]:px[p[0]][fs[0]] for p in us}
    for t in fs:
        e=eq+sum(p[1]*(px[p[0]][t]-p0[p[0]]) for p in us)
        if e<=sum(abs(p[1])*px[p[0]][t]*mm.get(p[0],0.02) for p in us): return True
    return False

pts={w:puntos_oos(w,c["eq"],c["pos"]) for w,c in carteras.items()}
pts={w:p for w,p in pts.items() if p is not None}
inicios=list(range(i_corte,len(todas)-VENTANA,PASO))
print(f"  {len(pts)} carteras, {len(inicios)} ventanas de {VENTANA}d\n")

tramos=[(0,10),(10,20),(20,30),(30,40),(40,50),(50,60),(60,70),(70,80),(80,90),(90,101)]
ct={t:[0,0] for t in tramos}; cg={g:[0,0] for g in "ABCDF"}
for ini in inicios:
    for w,c in carteras.items():
        if w not in pts: continue
        s=simular(c["eq"],c["pos"],ini,ini+VENTANA)
        if s is None: continue
        tr=next(t for t in tramos if t[0]<=pts[w]<t[1]); g=_grado(pts[w])
        ct[tr][1]+=1; cg[g][1]+=1
        if s: ct[tr][0]+=1; cg[g][0]+=1

print("  TASA POR TRAMO DE PUNTOS (formula de produccion, sin fuga)")
print(f"  {'puntos':>10}{'wallets':>9}{'sims':>8}{'liquidadas':>12}{'tasa':>8}")
print("  "+"-"*47)
nueva=[]
for t in tramos:
    n,d=ct[t]; nw=sum(1 for w in pts if t[0]<=pts[w]<t[1])
    if d:
        print(f"  {f'{t[0]}-{t[1]-1}':>10}{nw:>9}{d:>8,}{n:>12,}{n/d*100:>7.1f}%")
        nueva.append((t[0], round(n/d,3)))
    else:
        nueva.append((t[0], None))

print(f"\n  TASA POR GRADO (cortes calibrados A<20 B<40 C<50 D<90 F>=90)")
print(f"  {'grado':>6}{'wallets':>9}{'sims':>9}{'liquidadas':>12}{'tasa':>8}")
print("  "+"-"*45)
for g in "ABCDF":
    n,d=cg[g]; nw=sum(1 for w in pts if _grado(pts[w])==g)
    if d: print(f"  {g:>6}{nw:>9}{d:>9,}{n:>12,}{n/d*100:>7.1f}%")
ab=sum(cg[g][0] for g in "AB"); nab=sum(cg[g][1] for g in "AB")
df=sum(cg[g][0] for g in "DF"); ndf=sum(cg[g][1] for g in "DF")
if nab and ndf and ab:
    print(f"\n  A+B {ab/nab*100:.1f}%  |  D+F {df/ndf*100:.1f}%  |  discriminacion {(df/ndf)/(ab/nab):.1f}x")
print("\n  TASA_HISTORICA recalculada:")
print("  " + str(tuple((a, b if b is not None else 0.0) for a,b in nueva)))
