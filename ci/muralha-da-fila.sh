#!/usr/bin/env bash
# =============================================================================
# MURALHA DA FILA — a fila de trabalho só entra na main VÁLIDA.
#
# Roda em todo PR (via ci/ci.py --apenas muralhas). A fila (`fila/`) é a fonte
# que responde "a tarefa X existe, quem pegou, em que pé está" — nascida na
# fase 2 do plano de 29/08/2026 (veredito em
# docs/consultorias/central-de-orquestracao/VEREDITO.md). Ela segue o molde do
# livro: um arquivo por tarefa, um arquivo por evento, nada se edita, estado é
# sempre calculado. O que esta muralha garante:
#
#   1. todo arquivo de tarefa e de evento parseia e segue o molde (campo
#      obrigatório presente, campo desconhecido recusado);
#   2. número de tarefa não se repete (o número vem do almoxarife);
#   3. dependência aponta para tarefa que existe, e não há ciclo;
#   4. evento "concluida" SEM evidência conferida não existe — a mesma lei
#      do verde do livro;
#   5. evento depois do fim (concluída/cancelada) não reescreve a história;
#   6. NENHUMA tarefa que já existia foi editada — o arquivo da tarefa nunca
#      muda depois de criado, e a única exceção é o campo `depende_de`
#      (armadilhas/356, com mandato do mantenedor de 05/09/2026).
#
# São duas conferências, e elas medem coisas diferentes de propósito. A 1 a 5 é
# `python ci/fila.py validar`, que olha cada arquivo EM SI — o mesmo código que
# o balcão roda antes de qualquer gesto, para uma única definição de "válido".
# A 6 é `python ci/fila.py imutabilidade`, que olha o DIFF contra a base: ela
# precisa da versão anterior, que o balcão não tem e o CI tem. Foi exatamente
# essa distância que deixou a lei "nada se edita" sem ninguém que a fizesse
# valer do dia 29/08/2026 ao dia 05/09/2026.
#
# Por que ela NÃO nasce em sombra (o rito do Sistema Imunológico para regra
# nova): a superfície que ela mede nasce no MESMO PR que ela — não existe
# fluxo antigo para ela quebrar por engano. Regra nova sobre superfície nova
# é fail-closed desde o primeiro dia, como a muralha do painel foi.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# ERROR nunca vira PASS: "não consegui medir" é resultado, não silêncio.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR muralha-da-fila: 'python' não está disponível nesta máquina."
  echo "   A muralha NÃO inspecionou a fila. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

# Veredito lido da fonte, nunca de algo que passou por outro operador (§5.10).
saida="$("$PY_BIN" ci/fila.py validar 2>&1)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  echo "❌ MURALHA DA FILA — reprovou (exit $codigo)"
  echo "$saida" | tail -n 30 | sed 's/^/   /'
  if [[ $codigo -eq 2 ]]; then
    echo "   ⚠️ exit 2 = ERROR: a muralha NÃO conseguiu inspecionar a fila. Isto NÃO é um OK."
    exit 2
  fi
  exit 1
fi
echo "$saida" | tail -n 1

# PASSO 2 — a imutabilidade, que só o CI consegue medir (precisa da base).
saida_imutavel="$("$PY_BIN" ci/fila.py imutabilidade --base "${BASE_REF:-origin/main}" 2>&1)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  echo "❌ MURALHA DA FILA — reprovou na imutabilidade (exit $codigo)"
  echo "$saida_imutavel" | tail -n 30 | sed 's/^/   /'
  if [[ $codigo -ne 1 ]]; then
    echo "   ⚠️ exit $codigo = ERROR: a muralha NÃO conseguiu comparar a fila com a base. Isto NÃO é um OK."
    exit 2
  fi
  exit 1
fi
echo "$saida_imutavel" | tail -n 1
