#!/usr/bin/env bash
# =============================================================================
# O QUE RODA DENTRO DA VPS quando uma célula é entregue.
#
# Vive num arquivo, e não embutido no YAML do workflow, desde 28/08/2026 — por
# um motivo prático: a entrega passou a ser TENTADA MAIS DE UMA VEZ (a VPS
# recusou a conexão do runner cinco vezes em três dias, `armadilhas/127`), e
# repetir o corpo do script três vezes dentro do YAML seria a duplicação que
# esta casa proíbe. Com o script num arquivo, cada tentativa é uma chamada
# curta e existe UMA definição do que a entrega faz.
#
# De quebra: aqui ele é um `.sh` de verdade — revisável, com fim de linha
# travado em LF pelo `.gitattributes`, e sem escapar de YAML.
#
# ENTRADA: a variável CELULA, passada pelo workflow (`envs: CELULA`).
#
# IDEMPOTENTE POR CONSTRUÇÃO, e isso é requisito e não sorte: se a conexão cair
# no meio, a tentativa seguinte roda tudo de novo. `pull` e `up -d` sobre o
# estado já correto não fazem nada.
# =============================================================================
set -eu

cd /opt/plataforma

if [ -z "${CELULA:-}" ]; then
  echo "PAROU POR SEGURANÇA: a variável CELULA chegou vazia."
  echo "Sem ela, os comandos abaixo agiriam sobre a plataforma inteira."
  exit 1
fi

# A célula não é mais UM container: os consumers de evento e o worker Huey vivem
# em serviços "<celula>-<papel>" (infra/docker-compose.yml). Subir só "<celula>"
# deixaria o auxiliar rodando a IMAGEM ANTIGA, em silêncio — duas versões do
# mesmo código no ar, sem alarme nenhum. A lista sai do PRÓPRIO compose, não de
# uma lista fixa aqui: a célula que ganhar um auxiliar amanhã já entra sozinha,
# sem editar este arquivo.
SERVICOS=$(docker compose config --services | grep -E "^${CELULA}(-|\$)" || true)
if [ -z "$SERVICOS" ]; then
  echo "ERRO: '$CELULA' não tem serviço algum em /opt/plataforma/docker-compose.yml."
  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
  exit 1
fi
echo "Serviços desta célula: $SERVICOS"

docker compose pull $SERVICOS

# --wait reprova o deploy se algum container não ficar de pé (ou não ficar
# HEALTHY — os healthchecks do compose, entregues pelo PR #45, são a sonda
# pós-deploy F5 do PROJETO-PORTAO-DEPLOY). Sem ele, 'ps' devolve sucesso com
# container em crash-loop (ARMADILHAS §3.13).
docker compose up -d --wait --wait-timeout 180 $SERVICOS
docker compose ps $SERVICOS
