#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `identidade` NA VPS — o passo do mantenedor (H20).
# Cria o par banco+role isolado, escreve o env real da célula e registra os
# tokens dos DOIS pares consumidores (funil→identidade, sugestoes→identidade).
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal:
# em 24/08/2026 o console da VPS embaralhou DUAS colagens seguidas de um bloco
# multi-linha — os pedaços se sobrepuseram e o script rodou pela metade. Um
# deles ainda derrubou a sessão do mantenedor. Script versionado + uma linha
# curta de invocação elimina os dois modos de falha. A auditoria de duas
# bancas (25/08/2026) apontou que o H20 estava indo pelo caminho antigo — e que
# o texto dele só existia dentro de uma conversa, não no repositório.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-identidade.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA, e isso é de propósito: as credenciais do Google já estão
# em `env/sugestoes.env` desde 24/08 — o aplicativo OAuth é o MESMO, e o
# endereço de retorno neutro já está cadastrado no console desde aquele dia
# (DECISAO-onde-mora-a-sessao §5.2). Copiar de lá é mais seguro do que pedir
# para digitar de novo: nada aparece na tela, nada entra no histórico, nada
# pode ser digitado errado. É o oposto do que o script da Caixa precisou
# fazer, e o motivo é que aquele script CRIOU o que este aqui apenas herda.
#
# SEGREDOS: as quatro senhas (banco, Django, token do par do funil, token do
# par da Caixa) são geradas AQUI, dentro da VPS, e gravadas direto nos
# arquivos. Nenhuma aparece na tela, nenhuma passa por agente, nenhuma entra no
# Git (INV-P8, Lei 5).
#
# UM TOKEN POR PAR, NUNCA O MESMO NOS DOIS: o degrau que decide quem pode ver
# e-mail (`TOKENS_COMPLETOS_*`) compara VALORES de token. Se o funil e a Caixa
# tivessem o mesmo valor, o site inteiro passaria a receber o e-mail das
# pessoas sem que nada acusasse — achado da cadeira de IAM, 25/08/2026.
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só
# nasce se faltar, o env antigo vira `.bak-<epoch>` antes de ser reescrito, e
# as linhas dos consumidores são ATUALIZADAS em vez de duplicadas — uma chave
# repetida num env_file faz o Docker Compose usar a última, e um consumidor
# ficaria com o token velho enquanto a identidade só aceita o novo, dando 401
# silencioso.
# =============================================================================
set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt tem de começar com deploy@srv…)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
[ -f env/sugestoes.env ]  || parar "não achei env/sugestoes.env — a Caixa precisa estar provisionada antes (é dela que eu copio as credenciais do Google)."
[ -f env/funil.env ]      || parar "não achei env/funil.env."

# ---------------------------------------------------------------------------
# TRAVA DE DERIVA — mesma classe (e mesmo remédio) da que existe no
# `provisionar-sugestoes.sh`. Este script REESCREVE `env/identidade.env` inteiro
# (o `cat >` lá embaixo); logo, só pode rodar enquanto o heredoc souber gerar
# TODAS as chaves que o arquivo vivo já tem.
#
# Aqui a trava chega ANTES do primeiro caso, e não depois: em 25/08/2026 o
# script irmão foi flagrado com exatamente este buraco — o env vivo da Caixa
# tinha ganho `IDENTIDADE_API_URL`/`IDENTIDADE_API_TOKEN`, o heredoc de lá nunca
# soube delas, e re-rodar teria derrubado a porta da Caixa (500 em toda visita)
# com o deploy verde. `env/identidade.env` é novo e ainda não divergiu; esperar
# ele divergir para então guardá-lo seria esperar um incidente cujo mecanismo já
# conhecemos — "documento que generaliza a partir de dois é armadilha esperando
# o terceiro caso".
#
# A lista abaixo acompanha o heredoc, e
# `ci/tests/test_provisionamento_nao_perde_variavel.py` reprova se divergirem.
# ---------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="DATABASE_URL DEBUG DJANGO_SECRET_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET IDENTIDADE_STAFF_EMAILS TOKENS_ACEITOS_FUNIL TOKENS_ACEITOS_SUGESTOES TOKENS_COMPLETOS_SUGESTOES"

if [ -f env/identidade.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' env/identidade.env | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o env/identidade.env desta máquina tem variável que"
    echo "eu NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
    for CHAVE in $SOBRANDO; do echo "   - $CHAVE"; done
    echo
    echo "NADA foi alterado. O caminho de volta, por tipo de chave:"
    # `TOKENS_ACEITOS_<CELULA>` / `TOKENS_COMPLETOS_<CELULA>` são o par que CADA
    # célula consumidora registra aqui pelo provisionamento DELA — o `funil` e a
    # `sugestoes` no H20, o `admin` no H21, e assim por diante. Ou seja: esta
    # lista cresce sozinha a cada célula nova, e esbarrar nela é o caso ESPERADO
    # deste script, não a exceção. Por isso a recuperação vem nomeada, e não
    # como "fale com um agente": quem está na VPS precisa saber o que rodar.
    for CHAVE in $SOBRANDO; do
      case "$CHAVE" in
        TOKENS_ACEITOS_*|TOKENS_COMPLETOS_*)
          CELULA=$(echo "$CHAVE" | sed -E 's/^TOKENS_(ACEITOS|COMPLETOS)_//' | tr '[:upper:]' '[:lower:]')
          echo "   · $CHAVE -> é o par da célula '$CELULA'. Rode-me primeiro e"
          echo "     DEPOIS o infra/provisionar-$CELULA.sh, que regrava os dois lados."
          ;;
        *)
          echo "   · $CHAVE -> não sei de quem é. Mande esta tela ao agente."
          ;;
      esac
    done
    echo
    echo "Atenção: re-rodar este script ROTACIONA a chave do Django e a senha do"
    echo "banco da identidade — todo mundo é deslogado. Só re-rode se for isso mesmo."
    exit 1
  fi
fi

docker compose ps postgres >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."
psql_super() { docker compose exec -T postgres psql -U postgres "$@"; }

# --- herda do env da Caixa (o aplicativo OAuth é o mesmo) --------------------
ler_de() { grep "^$2=" "$1" | head -1 | cut -d= -f2-; }
ID="$(ler_de env/sugestoes.env GOOGLE_CLIENT_ID)"
SEGREDO="$(ler_de env/sugestoes.env GOOGLE_CLIENT_SECRET)"
STAFF="$(ler_de env/sugestoes.env SUGESTOES_STAFF_EMAILS)"

[ -n "$ID" ]      || parar "env/sugestoes.env não tem GOOGLE_CLIENT_ID preenchido."
[ -n "$SEGREDO" ] || parar "env/sugestoes.env não tem GOOGLE_CLIENT_SECRET preenchido."
case "$ID$SEGREDO" in
  *TROQUE_*|*COLE_*) parar "as credenciais do Google em env/sugestoes.env ainda são o texto de exemplo." ;;
esac

echo "== estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='identidade_db'" 2>/dev/null | grep -q 1
then echo "  banco identidade_db ...... já existe"; else echo "  banco identidade_db ...... não existe"; fi
if [ -f env/identidade.env ]
then echo "  env/identidade.env ....... já existe (guardo cópia antes de reescrever)"
else echo "  env/identidade.env ....... não existe"; fi
if grep -q "^IDENTIDADE_API_TOKEN=" env/funil.env
then echo "  linha no funil.env ....... já existe (atualizo o valor)"
else echo "  linha no funil.env ....... não existe"; fi
if grep -q "^IDENTIDADE_API_TOKEN=" env/sugestoes.env
then echo "  linha no sugestoes.env ... já existe (atualizo o valor)"
else echo "  linha no sugestoes.env ... não existe"; fi
echo "  credenciais do Google .... herdadas de env/sugestoes.env (não digitei nada)"
echo

SENHA_DB="$(openssl rand -hex 24)"
CHAVE_DJANGO="$(openssl rand -hex 32)"
TOKEN_FUNIL="$(openssl rand -hex 32)"
TOKEN_CAIXA="$(openssl rand -hex 32)"

# Role: ALTER primeiro (caso de re-execução), CREATE se ainda não existir.
psql_super -c "ALTER ROLE identidade_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE identidade_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário identidade_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='identidade_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE identidade_db OWNER identidade_user" >/dev/null \
  || parar "não consegui criar o banco identidade_db."

# A muralha de dados: nenhuma outra célula enxerga este banco — e aqui vale
# dobrado, porque é ELE que guarda o e-mail de todo mundo (golpe nº 7).
psql_super -c "REVOKE ALL ON DATABASE identidade_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."

umask 077
[ -f env/identidade.env ] && cp -a env/identidade.env "env/identidade.env.bak-$(date +%s)"

# O molde é infra/env/identidade.env.exemplo — se aquele arquivo ganhar
# variável nova, este bloco precisa ganhar junto, senão a célula sobe sem ela.
cat > env/identidade.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://identidade_user:$SENHA_DB@postgres:5432/identidade_db
DEBUG=0
GOOGLE_CLIENT_ID=$ID
GOOGLE_CLIENT_SECRET=$SEGREDO
IDENTIDADE_STAFF_EMAILS=$STAFF
TOKENS_ACEITOS_FUNIL=$TOKEN_FUNIL
TOKENS_ACEITOS_SUGESTOES=$TOKEN_CAIXA
TOKENS_COMPLETOS_SUGESTOES=$TOKEN_CAIXA
ENV

# DONO E MODO copiados de um env que JÁ FUNCIONA, em vez de escolhidos por mim:
# `umask 077` cria o arquivo do dono que rodou o script — e se isso for `root`,
# o usuário `deploy` (que o pipeline usa) NÃO consegue ler, e o `deploy-infra`
# reprova com "permission denied". Medido em 24/08/2026, no primeiro deploy da
# Caixa.
chown --reference=env/sugestoes.env env/identidade.env 2>/dev/null || parar "não consegui ajustar o dono de env/identidade.env — rode como root ou como o dono dos outros env."
chmod --reference=env/sugestoes.env env/identidade.env 2>/dev/null || parar "não consegui ajustar as permissões de env/identidade.env."

# --- o outro lado dos dois pares --------------------------------------------
# ATUALIZA se existe, ACRESCENTA se não — nunca duplica (ver o cabeçalho).
por_linha() {  # arquivo, chave, valor
  if grep -q "^$2=" "$1"; then
    sed -i "s|^$2=.*|$2=$3|" "$1"
  else
    printf '%s=%s\n' "$2" "$3" >> "$1"
  fi
}

grep -q "^# identidade" env/funil.env || printf '\n# identidade — o login do site (H20)\n' >> env/funil.env
por_linha env/funil.env IDENTIDADE_API_URL   "http://identidade:8000/interno"
por_linha env/funil.env IDENTIDADE_API_TOKEN "$TOKEN_FUNIL"
por_linha env/funil.env URL_DE_ENTRADA       "/entrar/google"

grep -q "^# identidade" env/sugestoes.env || printf '\n# identidade — o login do site (H20)\n' >> env/sugestoes.env
por_linha env/sugestoes.env IDENTIDADE_API_URL   "http://identidade:8000/interno"
por_linha env/sugestoes.env IDENTIDADE_API_TOKEN "$TOKEN_CAIXA"

echo "== estado DEPOIS =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='identidade_db'" 2>/dev/null | grep -q 1
then echo "  banco identidade_db ...... OK"; else echo "  banco identidade_db ...... FALTANDO"; fi
echo "  linhas em identidade.env . $(wc -l < env/identidade.env)  (esperado 9)"
echo "  dono/modo do env ......... $(stat -c '%U:%G %a' env/identidade.env) (igual ao sugestoes.env: $(stat -c '%U:%G %a' env/sugestoes.env))"

# A CONFERÊNCIA QUE IMPORTA: os dois consumidores precisam ter as DUAS linhas.
# Faltar uma no funil derrubava toda página do site até o PR da auditoria
# (hoje o funil falha aberto, mas o login some); faltar uma na Caixa fecha a
# Caixa inteira com a tela de indisponibilidade.
faltou=0
for par in funil sugestoes; do
  for chave in IDENTIDADE_API_URL IDENTIDADE_API_TOKEN; do
    if grep -q "^$chave=..*" "env/$par.env"
    then echo "  $par.env / $chave ... OK"
    else echo "  $par.env / $chave ... FALTANDO"; faltou=1; fi
  done
done

# E os tokens TÊM de ser diferentes entre os pares (ver o cabeçalho).
if [ "$(ler_de env/funil.env IDENTIDADE_API_TOKEN)" = "$(ler_de env/sugestoes.env IDENTIDADE_API_TOKEN)" ]; then
  echo "  tokens dos dois pares .... IGUAIS (ERRADO)"; faltou=1
else
  echo "  tokens dos dois pares .... diferentes, como deve ser"
fi
echo

[ "$faltou" -eq 0 ] || parar "algo acima ficou FALTANDO — me mande esta tela inteira e não mergeie nada ainda."

echo "PRONTO: identidade provisionada."
echo
echo "Nenhum segredo apareceu na tela, e você não precisou digitar nada — as"
echo "credenciais do Google vieram do env da Caixa, que já as tinha."
echo "Nenhum container foi reiniciado: quem faz isso é o deploy do próximo merge."
echo
echo "AGORA: volte ao chat e diga 'colei'. O agente mergeia a escada e confere."
