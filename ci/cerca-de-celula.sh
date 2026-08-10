#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CÓDIGO — 1 PR = 1 célula. Contratos mudam sozinhos e com rito.
# Roda em todo PR (workflow muralhas.yml). Sem exceções, sem "só dessa vez".
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

mapfile -t FILES < <(git diff --name-only "$BASE"...HEAD)

CELULAS=()
TEM_CONTRATO=0
for f in "${FILES[@]}"; do
  case "$f" in
    services/*)  CELULAS+=("$(echo "$f" | cut -d/ -f2)") ;;
    contracts/*) TEM_CONTRATO=1 ;;
  esac
done

UNICAS=$(printf '%s\n' "${CELULAS[@]:-}" | sed '/^$/d' | sort -u)
N=$(printf '%s' "$UNICAS" | grep -c . || true)

if (( N > 1 )); then
  echo "❌ MURALHA: este PR toca $N células — o limite é 1."
  echo "$UNICAS" | sed 's/^/   - /'
  echo "   Abra um PR por célula, em worktrees separados (RITOS.md §1)."
  exit 1
fi

if (( TEM_CONTRATO == 1 )); then
  if (( N > 0 )); then
    echo "❌ MURALHA: contracts/ não muda junto com services/."
    echo "   Rito de Contrato (RITOS.md §3): contrato primeiro, consumidores em PRs seguintes."
    exit 1
  fi
  if [[ ",$PR_LABELS," != *",contrato,"* ]]; then
    echo "❌ MURALHA: mudança em contracts/ exige a label 'contrato' (Rito de Contrato)."
    exit 1
  fi
fi

echo "✅ Cerca de célula: OK — ${N} célula(s) tocada(s)${UNICAS:+: $(echo $UNICAS | tr '\n' ' ')}"
