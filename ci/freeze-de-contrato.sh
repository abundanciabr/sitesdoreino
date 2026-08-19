#!/usr/bin/env bash
# =============================================================================
# MURALHA DE CONTRATO — wrapper fino. A lógica vive em ci/contract_freeze.py.
#
# Uso (compatível com o `make contrato-check` das células):
#   freeze-de-contrato.sh <celula> [<caminho-do-openapi-exportado>]
#   freeze-de-contrato.sh                     # todas as células do manifesto
#
# Exit codes: 0 = PASS/SKIP · 1 = contrato divergiu · 2 = não foi possível medir.
#
# Este arquivo já foi o portão inteiro em Bash — e produziu o falso positivo que
# originou o INV-CI01: chamava `python3` (inexistente na máquina do dono), as
# duas pontas de `diff <(norm A) <(norm B)` viraram vazio, `diff` deu igualdade
# e o script imprimiu "✅ OK". Bash aqui é wiring, nunca medição.
# =============================================================================
set -euo pipefail

# Expansão de parâmetro em vez de `dirname`: assim o wrapper não depende de
# NENHUM executável externo antes de ter provado que existe um Python. Um PATH
# quebrado precisa chegar até a mensagem de ERROR abaixo — não morrer com 127
# num utilitário auxiliar, que é ruído sem diagnóstico.
# A troca de "\" por "/" é o que faz o wrapper sobreviver a ser invocado com
# caminho no formato do Windows (`bash C:\...\ci\freeze-de-contrato.sh`): o
# Git Bash aceita "C:/..." no cd, mas trata "\" como escape. No Linux não há
# barra invertida em caminho, então a substituição é inócua.
ORIGEM="${BASH_SOURCE[0]//\\//}"
DIR_DO_SCRIPT="${ORIGEM%/*}"
[[ "$DIR_DO_SCRIPT" == "$ORIGEM" ]] && DIR_DO_SCRIPT="."
AQUI="$(cd -- "$DIR_DO_SCRIPT" && pwd)"

# `python` primeiro (é o que existe no venv e no Windows desta máquina); só então
# `python3`. Isto é BUSCA por um interpretador, não fallback silencioso: se
# nenhum dos dois existir o script morre com ERROR — nunca com sucesso.
PY=""
for candidato in python python3; do
  if command -v "$candidato" > /dev/null 2>&1 && "$candidato" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" > /dev/null 2>&1; then
    PY="$candidato"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo "ERROR freeze-de-contrato"
  echo
  echo "Nenhum interpretador Python >= 3.10 utilizável foi encontrado."
  echo "Procurados no PATH, nesta ordem: python, python3"
  echo
  echo "A CI NÃO comparou os contratos. Este resultado NÃO é um PASS."
  exit 2
fi

exec "$PY" "$AQUI/contract_freeze.py" "$@"
