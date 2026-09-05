#!/bin/bash
# Sube el indice del dia al repo publico. Un commit por dia: la fecha la pone
# GitHub, no nosotros. Ahi esta todo el valor del registro.
set -e
cd "$(dirname "$0")"
REPO="${REPO_INDICE:-/root/bitarrow/repo-indice}"
HOY=$(date -u +%Y%m%d)
[ -f "indice_${HOY}.json" ] || { echo "$(date -u '+%F %T') sin indice hoy" >> publicar.log; exit 0; }
mkdir -p "$REPO/indices"
cp "indice_${HOY}.json" "$REPO/indices/"
cp mercado.json universo.json scorer.py mercado.py aciertos.py "$REPO/" 2>/dev/null || true
cd "$REPO"
git add -A
git diff --cached --quiet && { echo "$(date -u '+%F %T') sin cambios" >> /root/bitarrow/riesgo_onchain/publicar.log; exit 0; }
N=$(python3 -c "import json;print(len(json.load(open('indices/indice_${HOY}.json'))['wallets']))")
git commit -q -m "Index $(date -u +%Y-%m-%d): ${N} accounts rated"
git push -q origin main
echo "$(date -u '+%F %T') publicado: ${N} wallets" >> /root/bitarrow/riesgo_onchain/publicar.log
