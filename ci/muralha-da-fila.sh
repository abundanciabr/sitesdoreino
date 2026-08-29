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
#   5. evento depois do fim (concluída/cancelada) não reescreve a história.
#
# Quem valida é `python ci/fila.py validar` — o mesmo código que o balcão usa
# antes de qualquer gesto, para uma única definição de "válido".
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
