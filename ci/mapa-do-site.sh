#!/usr/bin/env bash
# =============================================================================
# MURALHA DO MAPA DO SITE — a tela `/admin/mapa/` não pode mentir sobre o site.
#
# Roda em todo PR (ci/ci.py --apenas muralhas). O trabalho de verdade está em
# `ci/mapa_do_site.py --verificar`, em Python, que compara o mapa escrito
# (`painel/mapa-do-site.json`) com o roteamento do Traefik e os `urls.py` das
# células — nos DOIS sentidos. Este script existe só para a muralha ter um
# portão com nome e para o veredito (0/1/2) chegar inteiro ao runner.
#
# O que ele impede: uma página nova entrar no site sem o dono saber que ela
# existe, e uma linha do mapa sobreviver à página que ela descrevia. Mapa velho
# não quebra nada visivelmente — ele só é consultado com confiança justamente
# quando já está errado. É a Classe 8 do PLANO-MESTRE-ROBOS-SEM-COLISAO, a
# mesma doença que `celulas.yml` cura do outro lado.
#
# Por que NÃO nasce em sombra: sombra existe para regra em que o sósia legítimo
# existe e o detector precisa provar que sabe excluí-lo. Aqui o mapa cobre
# TODAS as rotas — inclusive `/healthz`, estáticos e portas de máquina —, então
# não há sósia: o que aparece é a falha, e a recusa entrega o conserto na hora
# (`python ci/mapa_do_site.py --faltando` lista o que escrever).
#
# Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
# =============================================================================
set -uo pipefail

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "❌ ERROR mapa-do-site: 'python' não está disponível nesta máquina."
  echo "   O mapa do site NÃO foi verificado. Este resultado NÃO é um OK."
  exit 2
fi
PY_BIN="$(command -v python3 || command -v python)"

saida="$("$PY_BIN" ci/mapa_do_site.py --verificar 2>&1)"
codigo=$?
echo "$saida"
exit $codigo
