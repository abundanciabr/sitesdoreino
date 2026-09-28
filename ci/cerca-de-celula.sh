#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CÓDIGO — contratos mudam sozinhos e com rito.
#
# A CERCA "1 PR = 1 CÉLULA" CAIU EM 29/08/2026 (Onda 5 do
# `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). Ela existia para comprar
# uma coisa que não era largura: restringir QUANTO do sistema um PR toca não
# compra exclusividade, e o argumento que encerrou a discussão é medido — a
# cerca **não teria evitado** o pior incidente já registrado aqui (o serviço
# novo e a configuração no mesmo commit passaram por dentro dela sem encostar).
#
# O que ficou no lugar dela, e por que só agora ela pôde cair:
#
#   celulas.yml + varredor    o mapa de quem é dono do quê, verificado contra
#                             o código em toda muralha (PR #442)
#   ci-celula em MATRIZ       o CI deriva do diff e roda a suíte de CADA célula
#                             tocada, em vez de recusar por largura (PR #443)
#   contrato aditivo          crescer é livre, remover exige autorização
#                             explícita (PR #445)
#   Depende-de: #N            ordem entre PRs, cobrada por máquina
#
# Proibição virou prova. O orçamento de 15 arquivos FICA: ele é barato, mede
# outra coisa (tamanho de uma mudança revisável) e continua útil. Desde o PR
# #1167 (06/09/2026) o que ele conta é CÓDIGO: a escrituração que a casa OBRIGA
# cada PR a carregar (`painel/` e `fila/`, a lista de `PASTAS_DE_ESCRITURACAO`
# em ci/divida_do_livro.py) sai da conta, porque comia o orçamento do trabalho
# de verdade. Quem mede é ci/orcamento-de-mudanca.sh, não este arquivo.
#
# O que este script ainda faz: o Rito de Contrato (RITOS.md §3) — contrato não
# muda junto com código de célula, e mudança em `contracts/` exige a etiqueta.
# Roda em todo PR (workflow muralhas.yml).
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
