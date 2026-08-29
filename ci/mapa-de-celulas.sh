#!/usr/bin/env bash
# =============================================================================
# MURALHA DO MAPA — `celulas.yml` não pode mentir sobre o código.
#
# Roda em todo PR (ci/ci.py --apenas muralhas). O mapa diz a quem pertence cada
# arquivo e quem consome quem; a partir da Onda 5 é ele que decide o que a CI
# roda e em que ordem o deploy publica. Mapa errado não quebra nada
# visivelmente — ele só faz o CI testar a coisa errada e o deploy publicar fora
# de ordem, em silêncio. É a Classe 8 (mapa velho), a doença que este plano
# existe para curar.
#
# O trabalho de verdade está em `ci/mapa_de_celulas.py --verificar`, em Python,
# que compara o escrito com o medido nos dois sentidos. Este script existe só
# para a muralha ter um portão com nome — e para o veredito (0/1/2) chegar
# inteiro ao runner.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR mapa-de-celulas: 'python' não está disponível nesta máquina."
  echo "   O mapa NÃO foi verificado. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/mapa_de_celulas.py --verificar 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
