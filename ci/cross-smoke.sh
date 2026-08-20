#!/usr/bin/env bash
# =============================================================================
# MURALHA INTERNA DE PAGAMENTOS — a resposta mecânica à ferida original:
# mexeu num método, o smoke do OUTRO roda também. O merge bloqueia mesmo que
# o agente "ache que terminou".
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"

# [INV-CI01] O `|| true` daqui transformava "o git falhou" em "pagamentos
# intocado" — a muralha interna da fortaleza saía verde sem ter olhado o diff.
# Falha do git agora é ERROR; SKIP só quando o git respondeu e a resposta foi
# realmente "nenhum arquivo de pagamentos mudou".
if ! DIFF="$(git diff --name-only "$BASE"...HEAD -- services/pagamentos)"; then
  echo "❌ ERROR cross-smoke: não foi possível calcular o diff de pagamentos."
  echo "   Comando: git diff --name-only $BASE...HEAD -- services/pagamentos"
  echo "   BASE_REF='$BASE' existe? O checkout tem fetch-depth: 0?"
  echo "   O cross-smoke NÃO rodou. Este resultado NÃO é um OK."
  exit 2
fi
if [[ -z "$DIFF" ]]; then
  echo "SKIP cross-smoke: o git leu o diff e pagamentos não foi tocado."
  exit 0
fi

MARKERS=()
grep -q 'methods/pix'  <<<"$DIFF" && MARKERS+=("smoke_card")
grep -q 'methods/card' <<<"$DIFF" && MARKERS+=("smoke_pix")
if grep -qE 'pagamentos/(core|providers|api)/' <<<"$DIFF"; then
  MARKERS=("smoke_pix" "smoke_card")
fi
if [[ ${#MARKERS[@]} -eq 0 ]]; then
  MARKERS=("smoke_pix" "smoke_card")   # na dúvida, os dois
fi

# IFS só aceita UM caractere separador — "IFS=' or '" vira um CONJUNTO de
# separadores (espaço, "o", "r"), nunca a string " or ". printf + strip do
# sufixo é o jeito correto de fazer join com separador multi-caractere em bash.
EXPR=$(printf '%s or ' "${MARKERS[@]}")
EXPR="${EXPR% or }"
echo "▶ Cross-smoke: pytest -m \"$EXPR\" (diff tocou pagamentos)"
cd services/pagamentos
python -m pytest -m "$EXPR" -q
