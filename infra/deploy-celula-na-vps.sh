#!/usr/bin/env bash
# Publica uma célula, com backup antes do boot/migrations e prova do endereço.
# IMAGEM e CODIGO vêm do publicador da VPS (base local + código montado); sem eles, imagem do registro.

set -eu

if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"
PUBLICACAO_LOCAL="${PUBLICACAO_LOCAL:-$RAIZ/publicacao-local.py}"

if [ -z "${CELULA:-}" ]; then
  echo "PAROU POR SEGURANÇA: a variável CELULA chegou vazia."
  echo "Sem ela, os comandos abaixo agiriam sobre a plataforma inteira."
  exit 1
fi

ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. Nada foi tocado: nenhuma imagem"
    echo "subiu e nenhuma migração rodou."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e publique de novo. O valor não se descobre daqui, e este script"
    echo "nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

SERVICOS_DO_COMPOSE=$(docker compose config --services) || {
  echo "PAROU POR SEGURANÇA: o 'docker compose config' não conseguiu LER $RAIZ/docker-compose.yml."
  echo "A célula '$CELULA' não tem nada a ver com isto. A reclamação do próprio"
  echo "compose está nas linhas logo acima desta, e ela nomeia o que falta: a causa"
  echo "quase sempre é variável obrigatória (a forma \${VAR:?mensagem} no compose)"
  echo "ausente em $RAIZ/env/ nesta VPS."
  echo "Nada foi tocado: nenhuma imagem subiu e nenhuma migração rodou."
  echo "O QUE FAZER: escreva na VPS, em $RAIZ/env/, a variável que a reclamação acima"
  echo "nomeia, e publique de novo."
  exit 1
}

SERVICOS=$(printf '%s\n' "$SERVICOS_DO_COMPOSE" | grep -E "^${CELULA}(-|\$)" || true)
if [ -z "$SERVICOS" ]; then
  echo "ERRO: '$CELULA' não tem serviço algum em $RAIZ/docker-compose.yml."
  echo "O compose foi lido sem erro nenhum; a lista de serviços é que não tem nome"
  echo "que comece por '$CELULA'."
  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
  echo "O QUE FAZER: confira o nome da célula pedida e o nome do serviço no"
  echo "compose, e publique de novo com os dois de acordo."
  exit 1
fi
echo "Serviços desta célula: $SERVICOS"

python3 "$PUBLICACAO_LOCAL" preparar
trap 'CODIGO=$?; if [ "$CODIGO" -ne 0 ]; then python3 "$PUBLICACAO_LOCAL" abortar || true; echo "ESTADO-PUBLICACAO: $(cat "$RAIZ/publicacoes/$CELULA.json")"; fi; exit "$CODIGO"' EXIT
if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
  export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
fi
[ -n "${IMAGEM:-}" ] || docker pull "ghcr.io/abundanciabr/plataforma-$CELULA:$TAG"

parar_o_deploy() {
  echo
  echo "PAROU POR SEGURANÇA: $1"
  echo
  echo "O QUE ESTA NO AR AGORA: nada mudou. A imagem nova NAO subiu e nenhuma"
  echo "migracao rodou, porque este passo vem antes de tudo isso. E por isso que"
  echo "ele para em vez de seguir. O site continua servindo a versao anterior."
  echo "O QUE FAZER: conserte o que a linha acima aponta e publique de novo."
  echo "Sem copia de seguranca do banco, esta casa nao migra."
  exit 1
}

# Cópia de segurança antes de qualquer migração: todas as bases na aplicação única,
# só a base da célula no caminho antigo. Ver infra/backup-do-banco.sh.
if [ "$CELULA" = aplicacao ]; then
  unset BASES
else
  export BASES="${CELULA}_db"
fi
bash "$(dirname "$0")/backup-do-banco.sh" "${TAG:0:12}-$$" \
  || parar_o_deploy "a cópia de segurança do banco não saiu (motivo nas linhas acima)."
echo "BACKUP-ANTES-DA-MIGRACAO: o caminho de volta é infra/restaurar-backup.sh (guia em infra/COMO-RESTAURAR.md)"

# --wait reprova o deploy se algum container não ficar de pé (ou não ficar
python3 "$PUBLICACAO_LOCAL" aplicar
export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
python3 "$PUBLICACAO_LOCAL" conferir-ultima
echo "CANDIDATA-APLICADA: $TAG"
docker compose up -d --wait --wait-timeout 180 $SERVICOS
docker compose ps $SERVICOS

if [ "$CELULA" = "cursos" ]; then
  docker compose exec -T cursos python manage.py marcar_bosses_primeiros_dolares \
    || parar_o_deploy "nao consegui marcar os Bosses de Primeiros Dolares. Nada foi considerado publicado."
fi

python3 "$PUBLICACAO_LOCAL" aprovar
echo "ENTREGA-CONCLUIDA: $CELULA"
