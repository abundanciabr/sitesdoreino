#!/usr/bin/env bash
# =============================================================================
# MURALHA DO TRAVESSÃO — texto publicado não entra na main com travessão.
#
# Roda em todo PR (via ci/ci.py --apenas muralhas). Decisão do mantenedor em
# 30/08/2026: todo texto escrito para ser publicado online sai sem travessão —
# no lugar dele entram vírgula, parênteses, dois-pontos ou aspas, conforme o
# papel que ele fazia na frase.
#
# Por que uma MURALHA e não um conselho no CLAUDE.md: regra de escrita é o caso
# extremo da doença-mãe desta casa (`ci/leis_sem_mecanismo.py`) — quem escreve o
# texto novo é uma sessão diferente a cada vez, e nenhuma delas leu o que a
# anterior combinou. Conselho não atravessa sessão; portão atravessa.
#
# Por que ela NÃO nasce em sombra (o rito do Sistema Imunológico para regra
# nova): sombra existe para detector que pode ter sósia legítimo. Aqui não há —
# travessão em texto publicado É a coisa proibida, lida diretamente do arquivo,
# sem inferir intenção de ninguém. O que poderia dar falso vermelho (comentário
# de quem escreveu, hífen de palavra composta, texto do bastidor) sai por
# desenho no próprio detector, e cada exclusão tem teste que a prova.
#
# Quem valida é `python ci/travessao.py` — o mesmo código que a pessoa roda na
# bancada, para uma única definição de "limpo".
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# ERROR nunca vira PASS: "não consegui medir" é resultado, não silêncio.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR muralha-do-travessao: 'python' não está disponível nesta máquina."
  echo "   A muralha NÃO inspecionou o texto público. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

# Veredito lido da fonte, nunca de algo que passou por outro operador (§5.10).
saida="$("$PY_BIN" ci/travessao.py 2>&1)"
codigo=$?
if [[ $codigo -ne 0 ]]; then
  echo "❌ MURALHA DO TRAVESSÃO — reprovou (exit $codigo)"
  echo "$saida" | tail -n 60 | sed 's/^/   /'
  if [[ $codigo -eq 2 ]]; then
    echo "   ⚠️ exit 2 = ERROR: a muralha NÃO conseguiu inspecionar o texto público. Isto NÃO é um OK."
    exit 2
  fi
  exit 1
fi
echo "$saida" | tail -n 1
