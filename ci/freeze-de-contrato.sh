#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CONTRATO — o schema vivo não pode derivar do arquivo congelado.
# Uso: freeze-de-contrato.sh <celula> <caminho-do-openapi-exportado>
# Chamado pelo `make contrato-check` de cada célula com contrato.
# =============================================================================
set -euo pipefail
CELULA="${1:?uso: freeze-de-contrato.sh <celula> <openapi-vivo>}"
VIVO="${2:?informe o caminho do openapi exportado do código}"
RAIZ="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
CONGELADO="$RAIZ/contracts/${CELULA}.openapi.yaml"

if [[ ! -f "$CONGELADO" ]]; then
  echo "ℹ Célula '$CELULA' sem contrato congelado — nada a checar."
  exit 0
fi

norm() {
  python3 - "$1" <<'PY'
import sys, yaml, json
print(json.dumps(yaml.safe_load(open(sys.argv[1])), sort_keys=True, indent=2))
PY
}

if ! diff -u <(norm "$CONGELADO") <(norm "$VIVO") > /tmp/drift.txt 2>&1; then
  echo "❌ FREEZE: o schema vivo de '$CELULA' derivou do contrato congelado."
  echo "   Primeiras linhas do drift:"
  head -60 /tmp/drift.txt
  echo "   Mudança de contrato tem rito próprio (RITOS.md §3) — nunca nasce dentro da célula."
  exit 1
fi
echo "✅ Freeze de contrato ($CELULA): OK"
