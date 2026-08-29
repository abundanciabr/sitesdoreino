#!/usr/bin/env bash
# =============================================================================
# MURALHA DAS LEIS — toda regra declara quem a faz valer.
#
# Onda 6 (B10, "a melhor ideia estrutural da rodada" segundo o plano mestre). O
# trabalho está em `ci/leis_sem_mecanismo.py`; este script existe para a muralha
# ter um portão com nome e para o veredito (0/1/2) chegar inteiro ao runner.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR leis-sem-mecanismo: 'python' não está disponível nesta máquina."
  echo "   O censo NÃO foi feito. Isto NÃO é 'está tudo imposto'."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/leis_sem_mecanismo.py 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
