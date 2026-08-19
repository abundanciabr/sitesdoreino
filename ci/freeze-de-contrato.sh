#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CONTRATO — o schema vivo não pode derivar do arquivo congelado.
# Uso: freeze-de-contrato.sh <celula> <caminho-do-openapi-exportado>
# Chamado pelo `make contrato-check` de cada célula com contrato.
# =============================================================================
set -euo pipefail
CELULA="${1:?uso: freeze-de-contrato.sh <celula> <openapi-vivo>}"
VIVO="${2:?informe o caminho do openapi exportado do código}"
# Mesma lógica do bloco do Python abaixo: sem git não dá para localizar a raiz do
# repositório, e cair para "." acharia que a célula não tem contrato — outro "OK"
# que nunca comparou nada.
if ! RAIZ="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "❌ FREEZE: não foi possível localizar a raiz do repositório (git indisponível?)."
  echo "   O contrato de '$CELULA' NÃO foi validado — isto não é um OK."
  exit 1
fi
CONGELADO="$RAIZ/contracts/${CELULA}.openapi.yaml"

if [[ ! -f "$CONGELADO" ]]; then
  echo "ℹ Célula '$CELULA' sem contrato congelado — nada a checar."
  exit 0
fi

# Sem interpretador, este script NÃO pode dizer "OK": ele diria isso sem ter
# comparado nada. Falhar alto é a única resposta honesta de um portão que não
# consegue medir. (Já aconteceu de verdade: com `python3` apontando para o stub
# da Microsoft Store, as duas pontas do diff falhavam igual e "batiam" — o
# portão ficou decorativo por semanas sem ninguém perceber.)
PY_BIN="$(command -v python3 || command -v python || true)"
if [[ -z "$PY_BIN" ]]; then
  echo "❌ FREEZE: nenhum interpretador Python encontrado (python3/python)."
  echo "   O contrato de '$CELULA' NÃO foi validado — isto não é um OK."
  exit 1
fi

norm() {
  "$PY_BIN" - "$1" <<'PYEOF'
import sys, yaml, json
print(json.dumps(yaml.safe_load(open(sys.argv[1])), sort_keys=True, indent=2))
PYEOF
}

# Substituição de COMANDO (e não de processo): com <(...) a falha do
# interpretador se perde e o diff acaba comparando dois vazios — que "batem".
CONGELADO_NORM="$(norm "$CONGELADO")" || {
  echo "❌ FREEZE: falha ao normalizar o contrato congelado de '$CELULA'."
  exit 1
}
VIVO_NORM="$(norm "$VIVO")" || {
  echo "❌ FREEZE: falha ao normalizar o schema vivo de '$CELULA'."
  exit 1
}

if [[ -z "$CONGELADO_NORM" || -z "$VIVO_NORM" ]]; then
  echo "❌ FREEZE: a normalização devolveu vazio — não há o que comparar."
  exit 1
fi

DRIFT="$(mktemp)"
trap 'rm -f "$DRIFT"' EXIT

if ! diff -u <(printf '%s\n' "$CONGELADO_NORM") <(printf '%s\n' "$VIVO_NORM") > "$DRIFT" 2>&1; then
  echo "❌ FREEZE: o schema vivo de '$CELULA' derivou do contrato congelado."
  echo "   Primeiras linhas do drift:"
  head -60 "$DRIFT"
  echo "   Mudança de contrato tem rito próprio (RITOS.md §3) — nunca nasce dentro da célula."
  exit 1
fi
echo "✅ Freeze de contrato ($CELULA): OK"
