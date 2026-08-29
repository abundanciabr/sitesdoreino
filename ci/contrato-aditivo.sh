#!/usr/bin/env bash
# =============================================================================
# MURALHA DO CONTRATO ADITIVO — acrescentar é livre; remover exige autorização.
#
# Roda em todo PR (ci/ci.py --apenas muralhas). O trabalho está em
# `ci/contrato_aditivo.py`; este script existe para a muralha ter um portão com
# nome e para o veredito (0/1/2) chegar inteiro ao runner.
#
# NÃO confundir com `contract_freeze`: aquele pergunta "o código derivou do
# contrato?"; este pergunta "a mudança do contrato quebra quem já o consome?".
# As duas falham em direções opostas, e nenhuma cobre a outra.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS/SKIP · 1 FAIL · 2 ERROR.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR contrato-aditivo: 'python' não está disponível nesta máquina."
  echo "   A compatibilidade NÃO foi medida. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/contrato_aditivo.py 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
