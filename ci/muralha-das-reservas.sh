#!/usr/bin/env bash
# =============================================================================
# MURALHA DAS RESERVAS — número de armadilha nova se PEDE, não se escolhe.
#
# Roda em todo PR (via ci/ci.py --apenas muralhas). O trabalho está em
# `ci/reservas_das_armadilhas.py`; este script existe para a muralha ter um
# portão com nome e para o veredito (0/1/2) chegar inteiro ao runner.
#
# O que ela garante: todo número de `armadilhas/` que aparece pela PRIMEIRA vez
# neste PR foi alocado por `python ci/reservar.py numero armadilha` — uma
# referência criada no servidor do GitHub, comparar-e-trocar. Escolher à mão
# não tem trava nenhuma: duas sessões listam a pasta no mesmo minuto, veem o
# mesmo livre, e o `git merge` junta os dois arquivos sem ter o que reclamar.
#
# Por que ela NÃO nasce em sombra: sombra existe para regra de confiança ALTA,
# em que o sósia legítimo existe e o detector precisa provar que sabe excluí-lo.
# Aqui o recorte "número NOVO em relação à base" já exclui os dois sósias que
# existem — as ~170 entradas históricas e o renomear-slug de entrada antiga. O
# que sobra É a falha, e a recusa entrega o conserto executável na hora.
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# ERROR nunca vira PASS: sem falar com o servidor não há como saber se a
# reserva existe, e supor que existe seria a trava que parece funcionar.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR muralha-das-reservas: 'python' não está disponível nesta máquina."
  echo "   As reservas NÃO foram conferidas. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/reservas_das_armadilhas.py 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
