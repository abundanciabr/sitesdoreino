#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `sugestoes` NA VPS — o passo do mantenedor (Lote 2 da
# Caixa de Sugestões). Cria o par banco+role isolado, escreve o env real da
# célula e registra o token do par sugestoes→alunos.
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal:
# em 24/08/2026 o console da VPS embaralhou DUAS colagens seguidas de um bloco
# multi-linha — os pedaços se sobrepuseram e o script rodou pela metade. Um
# deles ainda derrubou a sessão do mantenedor, porque usava `set -e` + `exit`
# dentro de um shell interativo de login. Script versionado + uma linha curta
# de invocação elimina os dois modos de falha: a colagem é curta demais para
# quebrar, e o `exit` acontece dentro de um bash filho.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-sugestoes.sh -o /tmp/p.sh && bash /tmp/p.sh "ID_DO_GOOGLE" "email@staff"
#
# O SEGREDO DO GOOGLE **NÃO** É ARGUMENTO — o script pergunta, e a digitação é
# invisível. Foi assim que a primeira versão vazou um segredo em 24/08/2026:
# argumento de linha de comando aparece na TELA, no `~/.bash_history`, na saída
# de `ps` enquanto roda, e em qualquer print do terminal que a pessoa mande
# para alguém. O id do cliente pode ser argumento — ele é público por desenho
# (vai no HTML da página de login). O segredo, não.
#
# SEGREDOS: as três senhas (banco, Django, token do par) são geradas AQUI,
# dentro da VPS, e gravadas direto nos arquivos. Nenhuma aparece na tela,
# nenhuma passa por agente, nenhuma entra no Git (INV-P8, Lei 5). Os dois
# valores do Google vêm do mantenedor porque só ele tem acesso ao console de lá
# (DECISAO-EVO-01 §6).
#
# IDEMPOTENTE, COM UMA RESSALVA QUE PRECISA SER LIDA: rodar de novo é seguro
# ENQUANTO o heredoc lá embaixo souber gerar todas as chaves que o env vivo
# tem. O role ganha senha nova, o banco só nasce se faltar, o env antigo vira
# `.bak-<epoch>` antes de ser reescrito, e a linha do `alunos.env` é atualizada
# em vez de duplicada. **Mas o arquivo é reescrito INTEIRO**: chave que a célula
# ganhou depois deste script seria apagada em silêncio. Por isso existe a TRAVA
# DE DERIVA logo abaixo do `cd`, que PARA em vez de escrever por cima. Rodar
# de novo também ROTACIONA a chave do Django (todo mundo é deslogado) e a senha
# do banco — seguro, mas não invisível.
# =============================================================================
set -u

ID="${1:-}"; STAFF="${2:-}"

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

[ $# -eq 2 ] || parar "esperava 2 valores (id do cliente do Google, e-mail de staff); vieram $#. O SEGREDO não é argumento — eu pergunto."
case "$ID$STAFF" in
  *COLE_*|*ID_DO_GOOGLE*|"") parar "os dois valores não foram preenchidos de verdade." ;;
esac

# O segredo entra aqui, com a digitação invisível: nunca na linha de comando,
# nunca no histórico, nunca num print de tela. `read -s` não ecoa; o `echo`
# depois existe só para a quebra de linha que o -s engole.
printf 'Cole o SEGREDO do cliente do Google (nada vai aparecer na tela): '
read -r -s SEGREDO
echo
[ -n "$SEGREDO" ] || parar "o segredo veio vazio."
case "$SEGREDO" in
  *SEGREDO_DO_GOOGLE*|*COLE_*) parar "o segredo ainda é o texto de exemplo." ;;
esac

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa?"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
[ -f env/alunos.env ]     || parar "não achei env/alunos.env — a plataforma não parece provisionada."

# ---------------------------------------------------------------------------
# TRAVA DE DERIVA — este script REESCREVE o env inteiro (o `cat >` lá embaixo),
# e por isso ele só pode rodar enquanto o heredoc souber gerar TODAS as chaves
# que o arquivo vivo já tem. Se a célula ganhou uma variável depois que este
# script foi escrito, reescrever apagaria essa variável em silêncio.
#
# Não é hipótese: medido em 25/08/2026. O login do site nasceu no dia anterior e
# pôs `IDENTIDADE_API_URL` e `IDENTIDADE_API_TOKEN` no env vivo; o heredoc daqui
# nunca soube delas. `apps/core/clients.py` lê as duas com `exigir()` FORA do
# bloco que traduz falha em tela amigável — sem elas, a porta da Caixa devolve
# **500 em toda visita**, com o deploy verde (é a família da `armadilhas/097`).
# O cabeçalho deste arquivo dizia "IDEMPOTENTE: rodar de novo é seguro", e
# aquilo tinha deixado de ser verdade sem ninguém perceber.
#
# A resposta certa NÃO é o script adivinhar os valores que faltam: o token do
# par `sugestoes↔identidade` é gerado pelo `provisionar-identidade.sh`, que é o
# dono dele. Aqui a resposta é PARAR — e dizer exatamente qual chave sobrou e
# quem sabe gerá-la. "Não sei reproduzir este arquivo" nunca pode virar
# "então escrevo por cima".
#
# A lista abaixo tem de acompanhar o heredoc. Ela é conferida de fora, a cada
# `make ci`, por `ci/tests/test_provisionamento_nao_perde_variavel.py`: se o
# heredoc ganhar (ou perder) uma chave e esta lista não acompanhar, o teste
# reprova. Duplicação consciente é aceitável; duplicação sem guarda é armadilha
# com data marcada.
# ---------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="ALUNOS_API_TOKEN ALUNOS_API_URL DATABASE_URL DEBUG DJANGO_SECRET_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET HUEY_REDIS_URL REDIS_STREAMS_URL SCRIPT_NAME SUGESTOES_STAFF_EMAILS"

if [ -f env/sugestoes.env ]; then
  SOBRANDO=""
  # `grep -oE` pega só o nome da chave; comentários e linhas em branco não casam.
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' env/sugestoes.env | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o env/sugestoes.env desta máquina tem variável que"
    echo "eu NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
    for CHAVE in $SOBRANDO; do echo "   - $CHAVE"; done
    echo
    echo "NADA foi alterado. O que fazer, conforme o caso:"
    echo "  · IDENTIDADE_API_*  -> é do infra/provisionar-identidade.sh, rode aquele."
    echo "  · SUGESTOES_APROVADORES -> é do infra/provisionar-aprovadores.sh."
    echo "  · outra coisa -> mande esta tela ao agente; o script precisa aprender a chave."
    exit 1
  fi
fi

psql_super() { docker compose exec -T postgres psql -U postgres "$@"; }

docker compose ps postgres >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='sugestoes_db'" 2>/dev/null | grep -q 1
then echo "  banco sugestoes_db ....... já existe"; else echo "  banco sugestoes_db ....... não existe"; fi
if [ -f env/sugestoes.env ]
then echo "  env/sugestoes.env ........ já existe (guardo cópia antes de reescrever)"
else echo "  env/sugestoes.env ........ não existe"; fi
if grep -q '^TOKENS_ACEITOS_SUGESTOES=' env/alunos.env
then echo "  linha no alunos.env ...... já existe (atualizo o valor)"
else echo "  linha no alunos.env ...... não existe"; fi
echo

SENHA_DB="$(openssl rand -hex 24)"
CHAVE_DJANGO="$(openssl rand -hex 32)"
TOKEN_PAR="$(openssl rand -hex 32)"

# Role: ALTER primeiro (caso de re-execução), CREATE se ainda não existir.
psql_super -c "ALTER ROLE sugestoes_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE sugestoes_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário sugestoes_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='sugestoes_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE sugestoes_db OWNER sugestoes_user" >/dev/null \
  || parar "não consegui criar o banco sugestoes_db."

# A muralha de dados: nenhuma outra célula enxerga este banco (golpe nº 7 do red-team).
psql_super -c "REVOKE ALL ON DATABASE sugestoes_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."

umask 077
[ -f env/sugestoes.env ] && cp -a env/sugestoes.env "env/sugestoes.env.bak-$(date +%s)"

# O molde é infra/env/sugestoes.env.exemplo — se aquele arquivo ganhar variável
# nova, esta função precisa ganhar junto, senão a célula sobe sem ela.
cat > env/sugestoes.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://sugestoes_user:$SENHA_DB@postgres:5432/sugestoes_db
DEBUG=0
SCRIPT_NAME=/forms/sugestoes
REDIS_STREAMS_URL=redis://redis:6379/0
HUEY_REDIS_URL=redis://redis:6379/8
GOOGLE_CLIENT_ID=$ID
GOOGLE_CLIENT_SECRET=$SEGREDO
ALUNOS_API_URL=http://alunos:8000/api/alunos
ALUNOS_API_TOKEN=$TOKEN_PAR
SUGESTOES_STAFF_EMAILS=$STAFF
ENV

# DONO E MODO: copiados de um env que JÁ FUNCIONA, em vez de escolhidos por
# mim. O `umask 077` acima cria o arquivo 600 e do dono que rodou o script — e
# se isso for `root`, o usuário `deploy` (que é quem o pipeline usa) NÃO
# consegue ler, e o `deploy-infra` reprova com "permission denied" na validação
# do compose. Medido em 24/08/2026, no primeiro deploy da Caixa. `--reference`
# não exige que este script adivinhe dono nem modo certos: ele copia os do
# `alunos.env`, que é a definição de "certo" nesta máquina.
chown --reference=env/alunos.env env/sugestoes.env 2>/dev/null   || parar "não consegui ajustar o dono de env/sugestoes.env — rode como root ou como o dono dos outros env."
chmod --reference=env/alunos.env env/sugestoes.env 2>/dev/null   || parar "não consegui ajustar as permissões de env/sugestoes.env."

# O outro lado do par: `alunos` monta TOKENS_ACEITOS de QUALQUER variável
# TOKENS_ACEITOS_*, então isto não exige uma linha de código naquela célula.
if grep -q '^TOKENS_ACEITOS_SUGESTOES=' env/alunos.env; then
  sed -i "s|^TOKENS_ACEITOS_SUGESTOES=.*|TOKENS_ACEITOS_SUGESTOES=$TOKEN_PAR|" env/alunos.env
else
  printf '\nTOKENS_ACEITOS_SUGESTOES=%s\n' "$TOKEN_PAR" >> env/alunos.env
fi

# `alunos` precisa reler o env para o token novo valer. Segundos, e a célula
# não tem rota pública direta.
docker compose up -d alunos >/dev/null 2>&1 || echo "  (aviso: não consegui reiniciar o alunos — avise a sessão do agente)"

echo "== estado DEPOIS =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='sugestoes_db'" 2>/dev/null | grep -q 1
then echo "  banco sugestoes_db ....... OK"; else echo "  banco sugestoes_db ....... FALTANDO"; fi
ESPERADAS=$(printf '%s
' $CHAVES_QUE_EU_GERO | wc -l | tr -d ' ')
echo "  linhas em sugestoes.env .. $(wc -l < env/sugestoes.env)  (esperado $ESPERADAS)"
echo "  dono/modo do env ......... $(stat -c '%U:%G %a' env/sugestoes.env) (igual ao alunos.env: $(stat -c '%U:%G %a' env/alunos.env))"
if grep -q '^TOKENS_ACEITOS_SUGESTOES=' env/alunos.env
then echo "  linha no alunos.env ...... OK"; else echo "  linha no alunos.env ...... FALTANDO"; fi
echo
echo "PRONTO. Nenhum segredo apareceu na tela — nem os gerados, nem o do Google"
echo "e gravadas direto nos arquivos. Avise a sessão do agente para ela mergear"
echo "o PR da infraestrutura e conferir o deploy."
