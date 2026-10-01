#!/usr/bin/env bash
# Publica uma célula sob trava, com backup antes do boot/migrations e prova da imagem.
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

# Publicacao de celula: convive com outras celulas, exclui a mesma celula e espera os mutadores comuns.
TRAVA_PUBLICACAO="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux na VPS antes de publicar." >&2; exit 1; }
case "${CELULA:-}" in ''|[!a-z]*|*[!a-z0-9_]*) echo "PAROU POR SEGURANÇA: a variável CELULA chegou vazia ou inválida." >&2; exit 1 ;; esac
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: nao criei a trava comum; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: nao li a trava comum; o dono deve liberar leitura sem remover o arquivo." >&2; exit 1; }
fi
flock --shared 8 || { echo "ERRO: nao obtive a trava comum; confira o mutador em andamento antes de repetir." >&2; exit 1; }
TRAVA_CELULA="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao-$CELULA.lock"
if ! [ "$TRAVA_CELULA" -ef "/proc/$$/fd/9" ]; then
  if [ ! -f "$TRAVA_CELULA" ]; then
    (umask 022; : >>"$TRAVA_CELULA") || { echo "ERRO: nao criei a trava da celula; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 9<"$TRAVA_CELULA" || { echo "ERRO: nao li a trava da celula." >&2; exit 1; }
fi
flock --exclusive 9 || { echo "ERRO: nao obtive a trava da celula; confira a publicacao em andamento antes de repetir." >&2; exit 1; }
unset TRAVA_PUBLICACAO TRAVA_CELULA

ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. Nada foi tocado: nenhuma imagem"
    echo "subiu e nenhuma migração rodou."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e peça um run novo. O valor não se descobre daqui, e este script"
    echo "nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

if [ "${MODO:-publicar}" = "inicializar" ]; then
  if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
    export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
  fi
  [ -n "${IMAGEM:-}" ] || docker pull "ghcr.io/abundanciabr/plataforma-$CELULA:$TAG"
  python3 "${PUBLICACAO_LOCAL:-$RAIZ/publicacao-local.py}" inicializar
  echo "INICIALIZACAO-CONCLUIDA: $CELULA:$TAG"
  exit 0
fi

SERVICOS_DO_COMPOSE=$(docker compose config --services) || {
  echo "PAROU POR SEGURANÇA: o 'docker compose config' não conseguiu LER $RAIZ/docker-compose.yml."
  echo "A célula '$CELULA' não tem nada a ver com isto. A reclamação do próprio"
  echo "compose está nas linhas logo acima desta, e ela nomeia o que falta: a causa"
  echo "quase sempre é variável obrigatória (a forma \${VAR:?mensagem} no compose)"
  echo "ausente em $RAIZ/env/ nesta VPS."
  echo "Nada foi tocado: nenhuma imagem subiu e nenhuma migração rodou."
  echo "O QUE FAZER: escreva na VPS, em $RAIZ/env/, a variável que a reclamação acima"
  echo "nomeia, e peça um run novo."
  exit 1
}

SERVICOS=$(printf '%s\n' "$SERVICOS_DO_COMPOSE" | grep -E "^${CELULA}(-|\$)" || true)
if [ -z "$SERVICOS" ]; then
  echo "ERRO: '$CELULA' não tem serviço algum em $RAIZ/docker-compose.yml."
  echo "O compose foi lido sem erro nenhum; a lista de serviços é que não tem nome"
  echo "que comece por '$CELULA'."
  echo "Abortado de propósito: 'up -d' sem argumento subiria a plataforma inteira."
  echo "O QUE FAZER: confira o nome da célula pedida no run e o nome do serviço no"
  echo "compose, e peça um run novo com os dois de acordo."
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
  echo "O QUE FAZER: conserte o que a linha acima aponta e peca um run novo."
  echo "Sem copia de seguranca do banco, esta casa nao migra."
  exit 1
}

PASTA_DOS_DUMPS="$RAIZ/backups-de-banco"
REFERENCIA_DE_PERMISSAO="${BACKUP_REFERENCIA:-$RAIZ/env}"

RETENCAO=20

BASE="${CELULA}_db"
case "$BASE" in
  *[!A-Za-z0-9_]*) parar_o_deploy "o nome de base '$BASE' tem caractere que nao e letra, numero ou sublinhado. Nada foi tocado." ;;
esac

EXISTE_A_BASE=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'") \
  || parar_o_deploy "nao consegui perguntar ao Postgres se a base '$BASE' existe. O banco pode estar fora do ar, e se ele estiver a migracao no boot da imagem nova falharia do mesmo jeito. Nada foi tocado."

if [ -z "$EXISTE_A_BASE" ]; then
  echo "BACKUP-ANTES-DA-MIGRACAO: dispensado, a celula '$CELULA' nao tem a base '$BASE' neste Postgres (celula sem banco)."
else
  mkdir -p "$PASTA_DOS_DUMPS"
  if [ -d "$REFERENCIA_DE_PERMISSAO" ]; then
    chown --reference="$REFERENCIA_DE_PERMISSAO" "$PASTA_DOS_DUMPS" 2>/dev/null || true
    chmod --reference="$REFERENCIA_DE_PERMISSAO" "$PASTA_DOS_DUMPS" \
      || parar_o_deploy "nao consegui copiar as permissoes de $REFERENCIA_DE_PERMISSAO para $PASTA_DOS_DUMPS. Um dump e dado pessoal, e eu nao o gravo numa pasta com permissao que eu mesmo escolhi. Nada foi tocado."
  else
    parar_o_deploy "nao achei $REFERENCIA_DE_PERMISSAO para copiar dono e modo da pasta de dumps. Nada foi tocado."
  fi

  rm -f "$PASTA_DOS_DUMPS/$BASE"-*.dump.parcial

  EXISTENTES=$(ls -1 "$PASTA_DOS_DUMPS/$BASE"-*.dump 2>/dev/null || true)
  if [ -n "$EXISTENTES" ]; then
    A_APAGAR=$(printf '%s\n' "$EXISTENTES" | sort -r | tail -n +"$RETENCAO")
    if [ -n "$A_APAGAR" ]; then
      QUANTOS=$(printf '%s\n' "$A_APAGAR" | wc -l)
      echo "Retencao: a pasta fica com no maximo $RETENCAO copias de $BASE (as mais recentes, mais a desta entrega); apagando $QUANTOS antiga(s)."
      printf '%s\n' "$A_APAGAR" | while IFS= read -r velho; do
        if [ -n "$velho" ]; then rm -f "$velho"; fi
      done
    fi
  fi

  TAMANHO_DA_BASE=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT pg_database_size('$BASE')") \
    || parar_o_deploy "nao consegui medir o tamanho da base '$BASE'. Nada foi tocado."
  TAMANHO_DA_BASE=$(printf '%s' "$TAMANHO_DA_BASE" | tr -d '[:space:]')
  case "$TAMANHO_DA_BASE" in
    ''|*[!0-9]*) parar_o_deploy "o Postgres respondeu algo que nao e um numero ao tamanho da base '$BASE'. 'Nao consegui medir' nunca vira 'pode seguir'. Nada foi tocado." ;;
  esac

  SAIDA_DO_DF=$(df -Pk "$PASTA_DOS_DUMPS") \
    || parar_o_deploy "nao consegui medir o espaco livre em $PASTA_DOS_DUMPS. Nada foi tocado."
  LIVRE_KB=$(printf '%s\n' "$SAIDA_DO_DF" | awk 'NR==2 {print $4}')
  case "$LIVRE_KB" in
    ''|*[!0-9]*) parar_o_deploy "nao consegui ler o espaco livre em $PASTA_DOS_DUMPS a partir do df. Nada foi tocado." ;;
  esac

  FOLGA_KB=262144
  PRECISO_KB=$(( TAMANHO_DA_BASE / 1024 + FOLGA_KB ))
  if [ "$LIVRE_KB" -lt "$PRECISO_KB" ]; then
    parar_o_deploy "nao ha espaco em disco para a copia de seguranca de '$BASE'. Livre: $((LIVRE_KB / 1024)) MB. Necessario com folga: $((PRECISO_KB / 1024)) MB. A pasta dos dumps e $PASTA_DOS_DUMPS e ela ja foi limpa ate as $RETENCAO copias mais recentes por base, entao o disco da VPS esta cheio por outro motivo, e isso e para o dono olhar. Nada foi tocado."
  fi

  CARIMBO=$(date -u +%Y%m%d-%H%M%SZ)
  ARQUIVO_FINAL="$PASTA_DOS_DUMPS/$BASE-$CARIMBO.dump"
  ARQUIVO_PARCIAL="$ARQUIVO_FINAL.parcial"

  docker compose exec -T postgres pg_dump -U postgres -Fc -d "$BASE" > "$ARQUIVO_PARCIAL" \
    || { rm -f "$ARQUIVO_PARCIAL"; parar_o_deploy "o pg_dump da base '$BASE' falhou. O arquivo incompleto foi descartado e nada mudou em producao."; }

  TAMANHO_DO_DUMP=$(wc -c < "$ARQUIVO_PARCIAL")
  if [ "$TAMANHO_DO_DUMP" -le 0 ]; then
    rm -f "$ARQUIVO_PARCIAL"
    parar_o_deploy "o dump de '$BASE' saiu VAZIO. Arquivo vazio que se chama backup e a pior coisa que existe aqui, e por isso ele foi descartado."
  fi

  docker compose exec -T postgres pg_restore -l < "$ARQUIVO_PARCIAL" > /dev/null \
    || { rm -f "$ARQUIVO_PARCIAL"; parar_o_deploy "o dump de '$BASE' foi escrito mas NAO ABRE: esta truncado ou corrompido. Ele foi descartado de proposito, porque um arquivo pela metade que se chama backup mente no dia em que alguem precisar dele."; }

  mv "$ARQUIVO_PARCIAL" "$ARQUIVO_FINAL" \
    || parar_o_deploy "nao consegui renomear a copia de seguranca para o nome final. Nada foi tocado."

  echo "BACKUP-ANTES-DA-MIGRACAO: $BASE-$CARIMBO.dump ($((TAMANHO_DO_DUMP / 1024)) KB) em $PASTA_DOS_DUMPS"
  echo "BACKUP-ANTES-DA-MIGRACAO: o carimbo do nome e UTC; em Brasilia sao tres horas a menos."
  echo "BACKUP-ANTES-DA-MIGRACAO: o caminho de volta e infra/restaurar-backup.sh"
fi

# --wait reprova o deploy se algum container não ficar de pé (ou não ficar
python3 "$PUBLICACAO_LOCAL" aplicar
export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
echo "CANDIDATA-APLICADA: $TAG"
docker compose up -d --wait --wait-timeout 180 $SERVICOS
docker compose ps $SERVICOS

if [ "$CELULA" = "cursos" ]; then
  docker compose exec -T cursos python manage.py marcar_bosses_primeiros_dolares \
    || parar_o_deploy "nao consegui marcar os Bosses de Primeiros Dolares. Nada foi considerado publicado."
fi

python3 "$PUBLICACAO_LOCAL" aprovar
echo "ENTREGA-CONCLUIDA: $CELULA"
