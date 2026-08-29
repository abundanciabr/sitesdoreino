#!/usr/bin/env bash
# =============================================================================
# MURALHA DA CATRACA DE TESTES — teste não some em silêncio (Onda 6, O11/B15).
#
# O trabalho está em `ci/catraca_de_testes.py`. Este script existe para a
# muralha ter um portão com nome e para o veredito (0/1/2) chegar inteiro.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS/SKIP · 1 FAIL · 2 ERROR.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR catraca-de-testes: 'python' não está disponível nesta máquina."
  echo "   A catraca NÃO mediu nada. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/catraca_de_testes.py 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
