#!/usr/bin/env bash
# =============================================================================
# ALARME DE ESCOPO — "corrigir o Pix" não volta com 42 arquivos.
# fix: 1–5 arquivos · feature: 5–15 · acima disso: rito arquitetural (label).
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

# `set -euo pipefail` já derrubava o script quando o git falhava aqui — mas com
# exit 128 e sem uma linha sequer explicando o que aconteceu. Falhar fechado sem
# diagnóstico manda o próximo agente investigar do zero (§19).
if ! DIFF_BRUTO="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR orcamento-de-mudanca: não foi possível calcular o diff."
  echo "   Comando: git diff --name-only $BASE...HEAD"
  echo "   BASE_REF='$BASE' existe? O checkout tem fetch-depth: 0?"
  echo "   O orçamento NÃO foi medido. Este resultado NÃO é um OK."
  exit 2
fi
if [[ -z "$DIFF_BRUTO" ]]; then N=0; else N=$(printf '%s\n' "$DIFF_BRUTO" | wc -l | tr -d ' '); fi
echo "Arquivos alterados: $N  (fix: 1–5 · feature: 5–15 · >15: mudança arquitetural)"

if (( N > 15 )) && [[ ",$PR_LABELS," != *",arquitetural,"* ]]; then
  echo "❌ ORÇAMENTO: $N arquivos sem a label 'arquitetural'."
  echo "   Ou o escopo vazou (o caso mais provável — reveja o diff contra o brief),"
  echo "   ou é mudança estrutural de verdade — e ela tem PR e rito próprios."
  exit 1
fi
echo "✅ Orçamento de mudança: OK"
