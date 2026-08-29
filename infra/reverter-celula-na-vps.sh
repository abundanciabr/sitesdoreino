#!/usr/bin/env bash
# =============================================================================
# O QUE RODA DENTRO DA VPS para VOLTAR uma célula a uma imagem anterior.
#
# UMA definição, dois chamadores — e é o ponto deste arquivo existir:
#   .github/workflows/rollback.yml       o rollback MANUAL (RITOS §4)
#   .github/workflows/deploy-celula.yml  a reversão AUTOMÁTICA (Onda 4, fatia 2)
#
# Duas cópias divergiriam no primeiro dia em que alguém mexesse numa delas, e a
# que rodaria às 2h da manhã seria, por lei de Murphy, a que ficou para trás.
# Guarda: `ci/tests/test_reversao.py::test_a_reversao_e_o_rollback_usam_o_MESMO_script_na_vps`.
#
# ENTRADA (por `envs:`, nunca por interpolação no YAML — texto vindo de fora
# dentro de um script é injeção esperando acontecer):
#   CELULA   nome já provado contra o manifesto por ci/rollback.py ou ci/reversao.py
#   VAR_TAG  ex.: QUIZ_TAG
#   TAG      sha de 40 hex de uma imagem que EXISTE no registry, ou `main`
#
# IDEMPOTENTE POR CONSTRUÇÃO: `pull` e `up -d` sobre o estado já correto não
# fazem nada. Repetir é seguro, e é o que permite tentar de novo sem medo.
#
# O PIN NÃO PERSISTE, DE PROPÓSITO: a variável é exportada só para este `up`.
# O próximo deploy da célula volta para `:main` (RITOS §4 item 3 — estado manual
# jamais persiste como fonte de verdade).
# =============================================================================
set -eu

cd /opt/plataforma

if [ -z "${CELULA:-}" ] || [ -z "${VAR_TAG:-}" ] || [ -z "${TAG:-}" ]; then
  echo "PAROU POR SEGURANÇA: CELULA, VAR_TAG ou TAG chegou vazia."
  echo "Sem as três, os comandos abaixo agiriam sobre a plataforma inteira,"
  echo "ou sobre uma imagem que ninguém escolheu."
  exit 1
fi

# A célula não é UM container: consumers de evento e worker Huey vivem em
# "<celula>-<papel>". Voltar só "<celula>" deixaria o auxiliar na imagem nova,
# em silêncio — duas versões do mesmo código no ar durante uma emergência. A
# lista sai do PRÓPRIO compose da VPS, como no deploy.
SERVICOS=$(docker compose config --services | grep -E "^${CELULA}(-|\$)" || true)
if [ -z "$SERVICOS" ]; then
  echo "ERRO: '$CELULA' não tem serviço algum em /opt/plataforma/docker-compose.yml."
  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
  exit 1
fi
echo "Serviços desta célula: $SERVICOS"

echo "Imagens ANTES:"
docker compose images $SERVICOS

# export com name=value: o nome da variável é indireto, e `$VAR_TAG=$TAG` sem as
# aspas não é atribuição em sh nenhum.
export "${VAR_TAG}=${TAG}"
echo "Aplicando ${VAR_TAG}=${TAG}"

INICIO=$(date +%s)
docker compose pull $SERVICOS
# --wait reprova se algum container não ficar de pé/healthy. Numa reversão isso
# importa MAIS que num deploy: voltar para uma imagem que não sobe é ficar sem
# serviço nenhum, e em silêncio.
docker compose up -d --wait --wait-timeout 180 $SERVICOS
FIM=$(date +%s)

echo "Imagens DEPOIS:"
docker compose images $SERVICOS
docker compose ps $SERVICOS
echo "SEGUNDOS_NA_VPS=$((FIM - INICIO))"

# A PROVA DE QUE ESTE SCRIPT RODOU ATE O FIM — a mesma trava do deploy, pelo
# mesmo motivo medido em 28/08/2026: a acao de SSH ja conectou sem executar
# nada e devolveu sucesso. Numa reversao isso seria pior que no deploy: o run
# anunciaria "revertido" com a imagem doente ainda no ar.
# ASCII de proposito: acento numa sentinela e um jeito barato de o grep falhar
# por codificacao e a trava virar decoracao.
echo "REVERSAO-CONCLUIDA: $CELULA -> $TAG"
