#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `pages` NA VPS, o passo do mantenedor.
#
# `pages` é a casa das Páginas do aluno: o portfólio, a Prancheta e a vitrine
# pública que o aluno manda ao cliente (PLANO-PORTFOLIO-DO-ALUNO.md, corredor
# CS-PAGES-0001, degrau 04 da escada do §5).
#
# Ele cria o par banco+role isolado e escreve o env real da célula. Só isso.
# Ele NÃO abre par de token: os dois pares que a porta do degrau 06 usa
# (`identidade` e `alunos`) são abertos por
# `infra/provisionar-pares-da-prancheta.sh`, porque quem autoriza é sempre o
# provedor, e o valor mora no env DELE. O que este roteiro faz com as quatro
# chaves é RELER e regravar, para não as apagar ao reescrever o arquivo (passo
# 2). E ele não pergunta o site ao catálogo, porque `config/settings.py` não lê
# `SITE_ID`, e roteiro que escreve variável que a célula não lê é configuração
# inventada (`armadilhas/224`: declare o presente, nunca o roadmap).
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pages.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha,
# os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor. Script versionado mais uma linha curta de invocação
# elimina os dois modos de falha (H18/H19/H20).
#
# QUANDO ELE RODA, e a ordem não é preferência: ANTES do PR que põe a célula no
# `infra/docker-compose.yml` (o degrau 05). Sem o banco, o container entra em
# crashloop assim que o compose a conhecer, porque `DATABASE_URL` é fail-hard.
# É a lição H18 e a `armadilhas/088`. E o compose vai sozinho num PR próprio,
# porque célula nova com o compose junto trava os DOIS deploys e nenhum rerun
# sai disso (`armadilhas/134`).
#
# ELE NÃO CHEGA AQUI PELO PIPELINE, e isso é decisão da casa: o `deploy-infra`
# sincroniza apenas o compose, o Traefik e o registro de sites, e nunca toca
# `env/` nem os roteiros de provisionamento, que são de execução única, pelo
# humano. É por isso que a invocação acima baixa o arquivo da `main` com
# `curl`.
#
# SEGREDOS: a senha do banco e a chave do Django são geradas AQUI, dentro da
# VPS, e gravadas direto no arquivo. Nenhuma aparece na tela, nenhuma passa por
# agente, nenhuma entra no Git (INV-P8, Lei 5).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só
# nasce se faltar, o prefixo público é PRESERVADO do arquivo vivo, e o env
# antigo vira `.bak-<epoch>` antes de ser reescrito. ATENÇÃO: re-rodar
# ROTACIONA a chave do Django e a senha do banco desta célula. O portfólio, as
# peças e as marcações continuam intactos (estão no banco, não na chave), mas a
# célula reinicia.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source` (ou `.`), um `exit`
# daqui derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no
# processo filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_PAGES="env/pages.env"
# A referência de dono e permissão: um env que JÁ funciona nesta máquina. Dono e
# modo se COPIAM, nunca se escolhem (`armadilhas/091`): rodando como root, um
# arquivo novo sai root:root, e o usuário `deploy`, que é quem o pipeline usa,
# não lê um 600 de root.
ENV_REF="env/identidade.env"

# O prefixo público de fábrica, usado só quando o arquivo ainda não existe.
# Nome da célula igual a nome da rota, de propósito (plano §4).
PREFIXO_DE_FABRICA="/pages"

# Os env dos dois provedores da Prancheta. Este roteiro só LÊ os dois: quem
# escreve neles é `infra/provisionar-pares-da-prancheta.sh`, porque quem
# autoriza é sempre o provedor.
ENV_IDENTIDADE="env/identidade.env"
ENV_ALUNOS="env/alunos.env"

# Os endereços internos saem do `servers:` dos contratos congelados
# (`contracts/identidade.openapi.yaml`, `contracts/alunos.openapi.yaml`), e não
# são escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE, tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF, e é dele que eu copio dono e permissão. Nada foi criado."

# -----------------------------------------------------------------------------
# 2. TRAVA DE DERIVA: este script REESCREVE `env/pages.env` inteiro.
#    Só pode rodar enquanto souber gerar TODAS as chaves que o arquivo vivo tem.
#    Sem isto, o dia em que alguém acrescentar uma variável aqui, re-rodar o
#    script a apagaria em silêncio, com o deploy verde (`armadilhas/111`).
#
#    A data era previsível, e CHEGOU em 06/09/2026: o degrau 06 pôs a porta de
#    pé, e ela pede quatro variáveis a este env — `IDENTIDADE_API_URL` e
#    `IDENTIDADE_API_TOKEN` (a pergunta de quem é a pessoa) e `ALUNOS_API_URL` e
#    `ALUNOS_API_TOKEN` (a pergunta da matrícula ativa). Elas entram no arquivo
#    vivo por `infra/provisionar-pares-da-prancheta.sh`, e sem a lista abaixo
#    aprendê-las este roteiro passaria a PARAR em toda execução na VPS: a
#    promessa de idempotência do cabeçalho viraria mentira, e o mantenedor
#    descobriria isso na tela dele.
#
#    Aprender uma chave aqui é assumir a obrigação de SABER ESCREVÊ-LA. As
#    quatro estão no heredoc do passo 4: os endereços são constantes dos
#    contratos congelados, e os dois tokens são RELIDOS da lista de aceitos de
#    cada provedor. É o mesmo desenho de `infra/provisionar-cursos.sh`.
#
#    O QUE AINDA NÃO ESTÁ NESTA LISTA, e é dito na cara para ninguém descobrir
#    pela recusa: `TOKENS_ACEITOS_ADMIN`, que a tela da equipe do degrau 11 vai
#    pedir a este env. Quando ela existir, esta lista e o heredoc ganham a chave
#    na MESMA edição.
# -----------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="ALUNOS_API_TOKEN ALUNOS_API_URL DATABASE_URL DEBUG DJANGO_SECRET_KEY IDENTIDADE_API_TOKEN IDENTIDADE_API_URL SCRIPT_NAME"

# LITERAL, e não `$ENV_PAGES`, de propósito: quem confere esta trava é um teste
# que lê o script como TEXTO, e na VPS não há Python nem este repositório para
# interpretar variável. A forma literal é o que torna o guarda possível.
if [ -f env/pages.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_PAGES" | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o $ENV_PAGES desta máquina tem variável que eu"
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
  # silencioso. Se nenhum dos dois existir, o script para em vez de gravar um
  # valor fraco.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

ler_de() {  # arquivo, chave: devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

echo "== 1/3: estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='pages_db'" 2>/dev/null | grep -q 1
then echo "  banco pages_db ... já existe"; else echo "  banco pages_db ... não existe"; fi
if [ -f "$ENV_PAGES" ]
then echo "  env/pages.env .... já existe (guardo cópia antes de reescrever)"
else echo "  env/pages.env .... não existe"; fi
echo

# O PREFIXO PÚBLICO, preservado do arquivo vivo quando a linha já existe.
#
# Como os DOIS endereços desta célula entram (`/pages` para o aluno logado e
# `/estudio/<apelido>` para o link que ele manda ao cliente) é decisão do degrau
# 05, o PR do compose e do Traefik, e `FORCE_SCRIPT_NAME` carrega um prefixo só.
# Se aquele degrau mudar esta linha, re-rodar este roteiro não pode desfazer a
# escolha dele em silêncio, que seria a `armadilhas/111` aplicada a um valor em
# vez de a uma chave.
#
# A pergunta é "a CHAVE existe no arquivo?", nunca "o valor está preenchido?":
# vazio é uma escolha legítima aqui (`settings.py` lê `os.environ.get(...) or
# None`, e vazio significa sem prefixo).
if [ -f "$ENV_PAGES" ] && grep -q '^SCRIPT_NAME=' "$ENV_PAGES"; then
  PREFIXO=$(grep '^SCRIPT_NAME=' "$ENV_PAGES" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]')
  echo "  prefixo público .. preservado do arquivo vivo: '${PREFIXO}'"
else
  PREFIXO="$PREFIXO_DE_FABRICA"
  echo "  prefixo público .. primeira escrita: '${PREFIXO}'"
fi
echo

# -----------------------------------------------------------------------------
# 3. OS SEGREDOS E O BANCO: par isolado, como manda a Lei 2.
# -----------------------------------------------------------------------------
echo "== 2/3: banco e senha próprios da célula =="

# ── OS DOIS TOKENS QUE ESTE SCRIPT NÃO INVENTA, e por isso RELÊ ─────────────
# Reescrever o arquivo inteiro sem estas quatro linhas as apagaria em silêncio,
# com o container de pé e o deploy verde (`armadilhas/111`). O efeito seria a
# Prancheta voltar a responder 503 para TODO MUNDO, sem erro em lugar nenhum:
# fail-closed por falta de valor é indistinguível de fail-closed por decisão, e
# é isso que torna esta classe de defeito cara.
#
# QUEM MANDA É O PROVEDOR, e a direção importa: o valor sai da lista de aceitos
# do env dele, e não do env desta célula. Alinhar pelo consumidor deixaria uma
# célula qualquer mudar o que o provedor aceita. Faltando dos dois lados, gero
# um valor para o arquivo não nascer com linha vazia; ele vale como marcador até
# `infra/provisionar-pares-da-prancheta.sh` rodar, que é quem abre o par nos
# DOIS lados de uma vez. É o mesmo desenho de `infra/provisionar-cursos.sh`.
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_PAGES)"
[ -n "$T_IDENTIDADE" ] || T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par pages->identidade ficou curto demais. Nada foi alterado."

T_ALUNOS="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_PAGES)"
[ -n "$T_ALUNOS" ] || T_ALUNOS="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_ALUNOS} -ge 32 ] || parar "o token do par pages->alunos ficou curto demais. Nada foi alterado."

SENHA_DB="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
CHAVE_DJANGO="$(gerar_segredo)" || parar "não consegui gerar a chave do Django. Nada foi alterado."
[ ${#SENHA_DB} -ge 32 ] || parar "a senha do banco ficou curta demais. Nada foi alterado."
[ ${#CHAVE_DJANGO} -ge 32 ] || parar "a chave do Django ficou curta demais. Nada foi alterado."

psql_super -c "ALTER ROLE pages_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE pages_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário pages_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='pages_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE pages_db OWNER pages_user" >/dev/null \
  || parar "não consegui criar o banco pages_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE pages_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."
echo "  banco e usuário ........ prontos, fechados ao público"

# A OUTRA METADE DA PROMESSA, e ela precisa ser MEDIDA para não ser prosa.
# A constituição desta célula diz que `pages_user` não enxerga nenhum outro
# database. A linha acima fecha `pages_db` aos outros; o contrário, `pages_user`
# alcançando o banco do fórum ou da identidade, depende de CADA um daqueles
# bancos já ter sido fechado ao público pelo roteiro DELE, e nenhum roteiro
# desta casa mediu isso até hoje.
#
# Este bloco não CONSERTA: mexer no banco de outra célula é atravessar a cerca.
# Ele mede e conta, porque garantia sem mecanismo é a doença-mãe desta casa.
# `postgres` e os `template*` ficam de fora de propósito: eles vêm abertos de
# fábrica, não guardam dado de célula nenhuma, e um alarme que dispara sempre
# é um alarme que ninguém lê.
VIZINHOS=$(psql_super -tAc "SELECT datname FROM pg_database WHERE datallowconn AND datname <> 'pages_db' AND datname ~ '_db\$' AND has_database_privilege('pages_user', datname, 'CONNECT') ORDER BY datname" 2>/dev/null | tr -d '\r' | grep -v '^$' || true)
if [ -n "$VIZINHOS" ]; then
  echo
  echo "  ATENÇÃO: o usuário pages_user ainda alcança banco de outra célula:"
  for BANCO in $VIZINHOS; do echo "     - $BANCO"; done
  echo "  Isso NÃO foi causado por este roteiro e nada aqui foi desfeito: aqueles"
  echo "  bancos estão abertos ao público desde antes. Mande esta tela ao agente,"
  echo "  que é quem fecha cada um pelo roteiro da célula dona dele."
else
  echo "  isolamento do usuário .. conferido, nenhum outro banco de célula alcançável"
fi
echo

# -----------------------------------------------------------------------------
# 4. O ENV DA CÉLULA: reescrito inteiro, com cópia do anterior.
# -----------------------------------------------------------------------------
echo "== 3/3: escrevendo o env da célula =="
umask 077
[ -f "$ENV_PAGES" ] && cp -a "$ENV_PAGES" "$ENV_PAGES.bak-$(date +%s)"

# O molde é infra/env/pages.env.exemplo. Se aquele arquivo ganhar variável nova,
# este bloco e a lista CHAVES_QUE_EU_GERO precisam ganhar junto.
# LITERAL pelo mesmo motivo da trava acima: o guarda procura este heredoc por
# texto para comparar as chaves com a lista `CHAVES_QUE_EU_GERO`.
cat > env/pages.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://pages_user:$SENHA_DB@postgres:5432/pages_db
DEBUG=0
SCRIPT_NAME=$PREFIXO
IDENTIDADE_API_URL=$IDENTIDADE_URL
IDENTIDADE_API_TOKEN=$T_IDENTIDADE
ALUNOS_API_URL=$ALUNOS_URL
ALUNOS_API_TOKEN=$T_ALUNOS
ENV

chown --reference="$ENV_REF" "$ENV_PAGES" 2>/dev/null \
  || parar "não consegui ajustar o dono de $ENV_PAGES. Rode como root."
chmod --reference="$ENV_REF" "$ENV_PAGES" 2>/dev/null \
  || parar "não consegui ajustar as permissões de $ENV_PAGES. Rode como root."
echo "  $ENV_PAGES ... escrito ($(grep -c '=' "$ENV_PAGES") variáveis)"
echo

echo "=============================================================="
echo " PRONTO. O banco das Páginas do aluno existe e o env está"
echo " escrito, com a chave e a senha geradas aqui dentro."
echo
echo " O QUE FALTA para a Prancheta abrir, se você ainda não fez:"
echo " esta tela NÃO liga as duas conversas dela (quem é a pessoa"
echo " e se a matrícula está ativa). Sem elas, /pages responde"
echo " 'Não conseguimos conferir o seu acesso agora' para todo"
echo " mundo. Quem as liga é a outra linha, e ela é uma só:"
echo
echo "   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pares-da-prancheta.sh -o /tmp/s.sh && bash /tmp/s.sh"
echo
echo " Pode mandar esta tela ao agente."
echo "=============================================================="
