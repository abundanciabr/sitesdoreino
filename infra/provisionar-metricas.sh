#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `metricas` NA VPS — o passo do mantenedor.
# Cria o par banco+role isolado e escreve o env real da célula. Só isso: esta
# célula não conversa com nenhuma outra por API, então não há par de token para
# abrir, e não pergunta o site ao catálogo, porque o site de cada fato vem
# DENTRO do próprio evento.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-metricas.sh -o /tmp/m.sh && bash /tmp/m.sh
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha —
# os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor. Script versionado + uma linha curta de invocação elimina
# os dois modos de falha (H18/H19/H20).
#
# QUANDO ELE RODA, e a ordem não é preferência: ANTES do PR que põe a célula no
# `infra/docker-compose.yml`. Sem o banco, o container entra em crashloop assim
# que o compose a conhecer, porque `DATABASE_URL` é fail-hard — é a lição H18 e
# a `armadilhas/088`.
#
# SEGREDOS: a senha do banco e a chave do Django são geradas AQUI, dentro da
# VPS, e gravadas direto no arquivo. Nenhuma aparece na tela, nenhuma passa por
# agente, nenhuma entra no Git (INV-P8, Lei 5).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só nasce
# se faltar, e o env antigo vira `.bak-<epoch>` antes de ser reescrito. ATENÇÃO:
# re-rodar ROTACIONA a chave do Django e a senha do banco desta célula — os
# fatos continuam intactos (estão no banco, não na chave), mas a célula
# reinicia, e o consumidor de eventos junto. Nada se perde nisso: o que estiver
# no stream é reentregue quando ele voltar.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/m.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/m.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_METRICAS="env/metricas.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="env/identidade.env"

# -----------------------------------------------------------------------------
# 1. ONDE — tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF, e é dele que eu copio dono e permissão. Nada foi criado."

# -----------------------------------------------------------------------------
# 2. TRAVA DE DERIVA — este script REESCREVE `env/metricas.env` inteiro.
#    Só pode rodar enquanto souber gerar TODAS as chaves que o arquivo vivo tem.
#    Sem isto, o dia em que alguém acrescentar uma variável aqui, re-rodar o
#    script a apagaria em silêncio, com o deploy verde (`armadilhas/111`).
#    Guarda: `ci/tests/test_provisionamento_nao_perde_variavel.py`.
#
#    E aqui a data é previsível: o degrau 7.4 da escada vai pedir
#    `TOKENS_ACEITOS_ADMIN` a este env, quando a `admin` passar a ler os números
#    daqui. É exatamente aí que esta trava precisa já existir.
# -----------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="DATABASE_URL DEBUG DJANGO_SECRET_KEY"

# LITERAL, e não `$ENV_METRICAS`, de propósito: quem confere esta trava é
# `ci/tests/test_provisionamento_nao_perde_variavel.py`, e ele lê o script como
# TEXTO — na VPS não há Python nem este repositório para interpretar variável.
if [ -f env/metricas.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_METRICAS" | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o $ENV_METRICAS desta máquina tem variável que eu"
    echo "NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
    for CHAVE in $SOBRANDO; do echo "   - $CHAVE"; done
    echo
    echo "NADA foi alterado. Mande esta tela ao agente."
    exit 1
  fi
fi

docker compose ps postgres >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."
psql_super() { docker compose exec -T postgres psql -U postgres "$@"; }

gerar_segredo() {
  # `openssl` primeiro; `/dev/urandom` como caminho alternativo MEDIDO, nunca
  # silencioso — se nenhum dos dois existir, o script para em vez de gravar um
  # valor fraco.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

echo "== 1/3 — estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='metricas_db'" 2>/dev/null | grep -q 1
then echo "  banco metricas_db ... já existe"; else echo "  banco metricas_db ... não existe"; fi
if [ -f "$ENV_METRICAS" ]
then echo "  env/metricas.env .... já existe (guardo cópia antes de reescrever)"
else echo "  env/metricas.env .... não existe"; fi
echo

# -----------------------------------------------------------------------------
# 3. OS SEGREDOS E O BANCO — par isolado, como manda a Lei 2.
# -----------------------------------------------------------------------------
echo "== 2/3 — banco e senha próprios da célula =="
SENHA_DB="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
CHAVE_DJANGO="$(gerar_segredo)" || parar "não consegui gerar a chave do Django. Nada foi alterado."
[ ${#SENHA_DB} -ge 32 ] || parar "a senha do banco ficou curta demais. Nada foi alterado."

psql_super -c "ALTER ROLE metricas_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE metricas_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário metricas_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='metricas_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE metricas_db OWNER metricas_user" >/dev/null \
  || parar "não consegui criar o banco metricas_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE metricas_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."
echo "  banco e usuário ........ prontos, fechados ao público"
echo

# -----------------------------------------------------------------------------
# 4. O ENV DA CÉLULA — reescrito inteiro, com cópia do anterior.
# -----------------------------------------------------------------------------
echo "== 3/3 — escrevendo o env da célula =="
umask 077
[ -f "$ENV_METRICAS" ] && cp -a "$ENV_METRICAS" "$ENV_METRICAS.bak-$(date +%s)"

# O molde é infra/env/metricas.env.exemplo — se aquele arquivo ganhar variável
# nova, este bloco e a lista CHAVES_QUE_EU_GERO precisam ganhar junto.
# LITERAL pelo mesmo motivo da trava acima: o guarda procura este heredoc por
# texto para comparar as chaves com a lista `CHAVES_QUE_EU_GERO`.
cat > env/metricas.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://metricas_user:$SENHA_DB@postgres:5432/metricas_db
DEBUG=0
ENV

chown --reference="$ENV_REF" "$ENV_METRICAS" 2>/dev/null \
  || parar "não consegui ajustar o dono de $ENV_METRICAS — rode como root."
chmod --reference="$ENV_REF" "$ENV_METRICAS" 2>/dev/null \
  || parar "não consegui ajustar as permissões de $ENV_METRICAS — rode como root."
echo "  $ENV_METRICAS ... escrito ($(grep -c '=' "$ENV_METRICAS") variáveis)"
echo

echo "=============================================================="
echo " PRONTO. O banco da medição existe e o env está escrito."
echo
echo " O que NÃO aconteceu ainda, e é o próximo passo do agente:"
echo " esta célula ainda não está no docker-compose.yml, então ela"
echo " NÃO está rodando. Isso entra num PR próprio, depois desta"
echo " tela (armadilhas/134: o compose de célula nova vai sozinho)."
echo
echo " Nada mais depende de você. Pode mandar esta tela ao agente."
echo "=============================================================="
