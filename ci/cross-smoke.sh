#!/usr/bin/env bash
# =============================================================================
# MURALHA INTERNA DE PAGAMENTOS — a resposta mecânica à ferida original:
# mexeu num método, o smoke do OUTRO roda também. O merge bloqueia mesmo que
# o agente "ache que terminou".
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"

DIFF=$(git diff --name-only "$BASE"...HEAD -- services/pagamentos || true)
if [[ -z "$DIFF" ]]; then
  echo "ℹ Pagamentos intocado — cross-smoke dispensado."
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

EXPR=$(IFS=' or '; echo "${MARKERS[*]}")
echo "▶ Cross-smoke: pytest -m \"$EXPR\" (diff tocou pagamentos)"
cd services/pagamentos
python -m pytest -m "$EXPR" -q
