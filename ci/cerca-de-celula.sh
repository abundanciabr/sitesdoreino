#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CÓDIGO — 1 PR = 1 célula. Contratos mudam sozinhos e com rito.
# Roda em todo PR (workflow muralhas.yml). Sem exceções, sem "só dessa vez".
# =============================================================================
set -euo pipefail
BASE="${BASE_REF:-origin/main}"
PR_LABELS="${PR_LABELS:-}"

# [INV-CI01] O diff é a MEDIÇÃO desta muralha. `mapfile < <(git diff ...)` não
# propaga a falha da substituição de processo: com um BASE_REF inválido, FILES
# vinha vazia, N virava 0 e a muralha imprimia "OK — 0 células". Aqui a falha do
# git é ERROR explícito, porque "não consegui ler o diff" não é "o diff está
# limpo".
if ! DIFF_BRUTO="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR cerca-de-celula: não foi possível calcular o diff."
  echo "   Comando: git diff --name-only $BASE...HEAD"
  echo "   BASE_REF='$BASE' existe? O checkout tem fetch-depth: 0?"
  echo "   A muralha NÃO inspecionou o PR. Este resultado NÃO é um OK."
  exit 2
fi

mapfile -t FILES <<< "$DIFF_BRUTO"

CELULAS=()
TEM_CONTRATO=0
for f in "${FILES[@]}"; do
  case "$f" in
    services/*)  CELULAS+=("$(echo "$f" | cut -d/ -f2)") ;;
    contracts/*) TEM_CONTRATO=1 ;;
  esac
done

UNICAS=$(printf '%s\n' "${CELULAS[@]:-}" | sed '/^$/d' | sort -u)
# Contagem em bash puro: `grep -c . || true` mascarava tanto "zero linhas"
# (saída 1, legítima) quanto erro real do grep (saída 2) no mesmo resultado.
if [[ -z "$UNICAS" ]]; then N=0; else N=$(printf '%s\n' "$UNICAS" | wc -l); fi

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
