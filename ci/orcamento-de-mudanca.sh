#!/usr/bin/env bash
# =============================================================================
# ALARME DE ESCOPO — "corrigir o Pix" não volta com 42 arquivos.
# fix: 1–5 arquivos · feature: 5–15 · acima disso: rito arquitetural (label).
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

N=$(git diff --name-only "$BASE"...HEAD | wc -l | tr -d ' ')
echo "Arquivos alterados: $N  (fix: 1–5 · feature: 5–15 · >15: mudança arquitetural)"

if (( N > 15 )) && [[ ",$PR_LABELS," != *",arquitetural,"* ]]; then
  echo "❌ ORÇAMENTO: $N arquivos sem a label 'arquitetural'."
  echo "   Ou o escopo vazou (o caso mais provável — reveja o diff contra o brief),"
  echo "   ou é mudança estrutural de verdade — e ela tem PR e rito próprios."
  exit 1
fi
echo "✅ Orçamento de mudança: OK"
