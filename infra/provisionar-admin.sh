#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `admin` NA VPS — o passo do mantenedor (H21).
# Cria o par banco+role isolado, escreve o env real da célula e registra o
# token do par `admin→identidade` nos DOIS lados.
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal:
# em 24/08/2026 o console da VPS embaralhou DUAS colagens seguidas de um bloco
# multi-linha — os pedaços se sobrepuseram e o script rodou pela metade, e uma
# delas derrubou a sessão do mantenedor (H18/H19). Script versionado + uma
# linha curta de invocação elimina os dois modos de falha. Foi assim que o H20
# deu certo de primeira, e é por isso que este arquivo veio num PR SÓ DELE,
# mergeado ANTES de o mantenedor ser chamado: a linha abaixo busca o script na
# `main`, e um script que ainda não está lá não pode ser executado.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-admin.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA, e isso é de propósito: a lista de quem entra na área
# administrativa é semeada a partir de `IDENTIDADE_STAFF_EMAILS`, que já está
# em `env/identidade.env` desde o H20. Copiar de lá é mais seguro do que pedir
# para digitar de novo — nada aparece na tela, nada entra no histórico, nada
# pode ser digitado errado.
#
# A SEMENTE NÃO É UM VÍNCULO: depois desta primeira escrita, `ADMIN_EMAILS` é
# lista PRÓPRIA da célula (DECISAO-celula-admin §2). Mudar quem é admin é
# editar essa linha e reiniciar — não mexe no staff da identidade, e o staff da
# identidade não muda quem é admin. As duas listas só nascem iguais.
#
# SEGREDOS: as três credenciais (senha do banco, chave do Django, token do par)
# são geradas AQUI, dentro da VPS, e gravadas direto nos arquivos. Nenhuma
# aparece na tela, nenhuma passa por agente, nenhuma entra no Git (INV-P8,
# Lei 5, `armadilhas/090`).
#
# AS DUAS CHAVES DO PAR TÊM O MESMO VALOR, e aqui é o contrário do H20:
# `TOKENS_ACEITOS_ADMIN` prova QUEM chama; `TOKENS_COMPLETOS_ADMIN` decide se
# esse par pode receber o e-mail. São dois degraus sobre o MESMO token — valores
# diferentes dariam 403 em toda pergunta da área admin, e o sintoma seria uma
# área que nunca abre para ninguém (fail-closed, mas silencioso e
# indistinguível do 404 de "você não está na lista").
# O que TEM de ser diferente é o token DESTE par em relação aos outros pares
# (funil, sugestoes) — o script confere isso no fim.
#
# E ESTA CÉLULA TAMBÉM É PROVEDORA, desde 06/09/2026: a `pages` pergunta aqui
# quem é administrador da escola, para abrir a fila da conferência do portfólio.
# Quem prova quem chama é `TOKENS_ACEITOS_PAGES`, e este roteiro a RELÊ do
# arquivo vivo em vez de regerar (o porquê está na trava de deriva, mais
# abaixo). Quem abre esse par nos dois lados, sem rotacionar nada, é
# `infra/provisionar-par-do-portfolio-com-a-admin.sh`.
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só
# nasce se faltar, o env antigo vira `.bak-<epoch>` antes de ser reescrito, e
# as linhas na identidade são ATUALIZADAS em vez de duplicadas — chave repetida
# num env_file faz o Compose usar a última, e a área admin ficaria com o token
# velho enquanto a identidade só aceita o novo, dando 401 silencioso.
# =============================================================================
set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# A pasta da plataforma, com o mesmo nome de variável dos roteiros mais novos
# desta casa. O padrão continua sendo `/opt/plataforma`, e nada muda para quem
# roda na VPS; o que ela permite é provar este roteiro numa VPS de mentira, que
# é a evidência que esta casa exige de quem mexe em provisionamento.
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv…)"
[ -f docker-compose.yml ]  || parar "não achei docker-compose.yml em $RAIZ."
[ -f env/identidade.env ]  || parar "não achei env/identidade.env — a identidade precisa estar provisionada antes (é dela que eu herdo a lista de quem entra, e é nela que registro o token do par)."

docker compose ps postgres >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."
psql_super() { docker compose exec -T postgres psql -U postgres "$@"; }

# --- herda da identidade a semente da lista de admins ------------------------
ler_de() { grep "^$2=" "$1" | head -1 | cut -d= -f2-; }
STAFF="$(ler_de env/identidade.env IDENTIDADE_STAFF_EMAILS)"

[ -n "$STAFF" ] || parar "env/identidade.env não tem IDENTIDADE_STAFF_EMAILS preenchido — sem isso a área administrativa nasceria sem ninguém podendo entrar."
case "$STAFF" in
  *TROQUE_*|*COLE_*|*voce@exemplo.com*) parar "IDENTIDADE_STAFF_EMAILS ainda é o texto de exemplo — a área admin nasceria com uma lista falsa." ;;
esac

# ---------------------------------------------------------------------------
# TRAVA DE DERIVA — porque este script reescreve `env/admin.env` INTEIRO.
#
# A lista abaixo é a cópia consciente das chaves do heredoc lá embaixo, e o
# guarda `ci/tests/test_provisionamento_nao_perde_variavel.py` reprova se as
# duas divergirem: cópia consciente é aceitável; cópia sem guarda é armadilha
# com data marcada.
#
# O modo de falha que isto evita nasceu de verdade na Caixa
# (`armadilhas/111`): o script dela reescrevia o env sem conhecer as chaves que
# o login acrescentara depois, e re-rodá-lo deixaria a porta em HTTP 500 a cada
# visita — com o deploy VERDE. Aqui a mina ainda não existe (o `env/admin.env`
# nasce neste script), e a trava entra ANTES de ela poder nascer: no dia em que
# outra célula acrescentar chave neste env, quem re-rodar recebe uma parada
# nominal em vez de um apagamento silencioso.
#
# Por que a lista mora aqui em vez de ser derivada do heredoc: este script roda
# na VPS, onde não há Python nem a suíte de testes — só shell puro.
# ---------------------------------------------------------------------------
# A OITAVA CHAVE ENTROU EM 06/09/2026, e nela esta célula é o PROVEDOR, não o
# consumidor. A `pages` passou a perguntar aqui quem é administrador da escola,
# para abrir a fila da conferência do portfólio (`contracts/admin.openapi.yaml`,
# operação `isAdministrator`), e quem prova quem chama é `TOKENS_ACEITOS_PAGES`,
# lida por `config/settings.py`.
#
# ELA É A ÚNICA DA LISTA QUE ESTE ROTEIRO NÃO REGERA: o valor é RELIDO do
# arquivo vivo e regravado igual. Regerar rotacionaria um token em uso, e a fila
# do portfólio responderia 401 até a `pages` ser reprovisionada. Aprender a
# chave sem relê-la seria a `armadilhas/111` com outro nome. Ela só nasce aqui
# quando falta dos dois lados, como marcador, até
# `infra/provisionar-par-do-portfolio-com-a-admin.sh` alinhar os dois envs.
CHAVES_QUE_EU_GERO="ADMIN_EMAILS DATABASE_URL DEBUG DJANGO_SECRET_KEY IDENTIDADE_API_TOKEN IDENTIDADE_API_URL SCRIPT_NAME TOKENS_ACEITOS_PAGES"

if [ -f env/admin.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' env/admin.env | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o env/admin.env desta máquina tem variável que"
    echo "eu NÃO sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
    for CHAVE in $SOBRANDO; do echo "   - $CHAVE"; done
    echo
    echo "NADA foi alterado. Mande esta tela ao agente: ou o script aprende a chave,"
    echo "ou ela pertence a outro script de provisionamento, que é quem deve rodar."
    exit 1
  fi
fi

echo "== estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='admin_db'" 2>/dev/null | grep -q 1
then echo "  banco admin_db ............... já existe"; else echo "  banco admin_db ............... não existe"; fi
if [ -f env/admin.env ]
then echo "  env/admin.env ................ já existe (guardo cópia antes de reescrever)"
else echo "  env/admin.env ................ não existe"; fi
if grep -q "^TOKENS_ACEITOS_ADMIN=" env/identidade.env
then echo "  par admin na identidade ...... já existe (atualizo o valor)"
else echo "  par admin na identidade ...... não existe"; fi
# O par em que esta célula é PROVEDORA: quem pergunta é a `pages`, e o valor é
# RELIDO do arquivo vivo em vez de regerado (ver a lista da trava, lá em cima).
# Faltando dos dois lados, nasce um marcador, e o roteiro do par o adota.
if [ -f env/admin.env ]; then T_PAGES="$(ler_de env/admin.env TOKENS_ACEITOS_PAGES)"; else T_PAGES=""; fi
if [ -n "$T_PAGES" ]
then echo "  par pages na admin ........... já existe (releio e regravo igual, sem rotacionar)"
else
  T_PAGES="$(openssl rand -hex 32)"
  echo "  par pages na admin ........... não existe (gravo um marcador; quem alinha os dois lados é o roteiro do par)"
fi
echo "  lista de admins .............. herdada de env/identidade.env (não digitei nada)"
echo

SENHA_DB="$(openssl rand -hex 24)"
CHAVE_DJANGO="$(openssl rand -hex 32)"
TOKEN_ADMIN="$(openssl rand -hex 32)"

# Role: ALTER primeiro (caso de re-execução), CREATE se ainda não existir.
psql_super -c "ALTER ROLE admin_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE admin_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário admin_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='admin_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE admin_db OWNER admin_user" >/dev/null \
  || parar "não consegui criar o banco admin_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco. Aqui ele
# guarda a AUDITORIA — quem mexeu em quê — e é justamente o banco que um
# invasor gostaria de editar para apagar o próprio rastro.
psql_super -c "REVOKE ALL ON DATABASE admin_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."

umask 077
[ -f env/admin.env ] && cp -a env/admin.env "env/admin.env.bak-$(date +%s)"

# O molde é infra/env/admin.env.exemplo — se aquele arquivo ganhar variável
# nova, este bloco precisa ganhar junto, senão a célula sobe sem ela.
cat > env/admin.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://admin_user:$SENHA_DB@postgres:5432/admin_db
DEBUG=0
SCRIPT_NAME=/admin
IDENTIDADE_API_URL=http://identidade:8000/interno
IDENTIDADE_API_TOKEN=$TOKEN_ADMIN
ADMIN_EMAILS=$STAFF
TOKENS_ACEITOS_PAGES=$T_PAGES
ENV

# DONO E MODO copiados de um env que JÁ FUNCIONA, em vez de escolhidos por mim:
# `umask 077` cria o arquivo do dono que rodou o script — e se isso for `root`,
# o usuário `deploy` (que o pipeline usa) NÃO consegue ler, e o `deploy-infra`
# reprova com "permission denied" (`armadilhas/091`).
chown --reference=env/identidade.env env/admin.env 2>/dev/null || parar "não consegui ajustar o dono de env/admin.env — rode como root ou como o dono dos outros env."
chmod --reference=env/identidade.env env/admin.env 2>/dev/null || parar "não consegui ajustar as permissões de env/admin.env."

# --- o outro lado do par -----------------------------------------------------
# ATUALIZA se existe, ACRESCENTA se não — nunca duplica (ver o cabeçalho).
por_linha() {  # arquivo, chave, valor
  if grep -q "^$2=" "$1"; then
    sed -i "s|^$2=.*|$2=$3|" "$1"
  else
    printf '%s=%s\n' "$2" "$3" >> "$1"
  fi
}

grep -q "^# admin" env/identidade.env || printf '\n# admin — a área administrativa (H21)\n' >> env/identidade.env
por_linha env/identidade.env TOKENS_ACEITOS_ADMIN   "$TOKEN_ADMIN"
por_linha env/identidade.env TOKENS_COMPLETOS_ADMIN "$TOKEN_ADMIN"

echo "== estado DEPOIS =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='admin_db'" 2>/dev/null | grep -q 1
then echo "  banco admin_db ............... OK"; else echo "  banco admin_db ............... FALTANDO"; fi
echo "  linhas em admin.env .......... $(wc -l < env/admin.env)  (esperado 8)"
echo "  dono/modo do env ............. $(stat -c '%U:%G %a' env/admin.env) (igual ao identidade.env: $(stat -c '%U:%G %a' env/identidade.env))"

faltou=0

# A CONFERÊNCIA QUE IMPORTA nº 1: a área admin precisa das três linhas que a
# porta usa. Faltar qualquer uma fecha a área inteira — e fecha em SILÊNCIO,
# porque a porta é fail-closed por desenho (DECISAO-celula-admin §2).
for chave in IDENTIDADE_API_URL IDENTIDADE_API_TOKEN ADMIN_EMAILS; do
  if grep -q "^$chave=..*" env/admin.env
  then echo "  admin.env / $chave ... OK"
  else echo "  admin.env / $chave ... FALTANDO"; faltou=1; fi
done

# A CONFERÊNCIA nº 1b: o par em que esta célula é PROVEDORA sobreviveu à
# reescrita, com o MESMO valor que estava no arquivo. Se ele sumir ou mudar, a
# fila da conferência do portfólio passa a responder 401 para todo mundo, e o
# sintoma é indistinguível de "ninguém tem permissão" (`armadilhas/111`).
if [ -n "$T_PAGES" ] && [ "$(ler_de env/admin.env TOKENS_ACEITOS_PAGES)" = "$T_PAGES" ]
then echo "  admin.env / TOKENS_ACEITOS_PAGES ... OK"
else echo "  admin.env / TOKENS_ACEITOS_PAGES ... FALTANDO"; faltou=1; fi

# nº 2: os dois degraus do par, do lado da identidade.
for chave in TOKENS_ACEITOS_ADMIN TOKENS_COMPLETOS_ADMIN; do
  if grep -q "^$chave=..*" env/identidade.env
  then echo "  identidade.env / $chave ... OK"
  else echo "  identidade.env / $chave ... FALTANDO"; faltou=1; fi
done

# nº 3: os DOIS degraus do MESMO par têm de ter o MESMO valor (ver o cabeçalho).
if [ "$(ler_de env/identidade.env TOKENS_ACEITOS_ADMIN)" = "$(ler_de env/identidade.env TOKENS_COMPLETOS_ADMIN)" ]
then echo "  os dois degraus do par ....... mesmo valor, como deve ser"
else echo "  os dois degraus do par ....... DIFERENTES (ERRADO — a área admin nunca abriria)"; faltou=1; fi

# nº 4: e o token DESTE par tem de ser diferente do dos OUTROS pares — token
# repetido entre pares apaga a fronteira que os degraus existem para criar.
for outro in FUNIL SUGESTOES; do
  valor_outro="$(ler_de env/identidade.env "TOKENS_ACEITOS_$outro")"
  if [ -n "$valor_outro" ] && [ "$valor_outro" = "$TOKEN_ADMIN" ]
  then echo "  token admin vs $outro ......... IGUAL (ERRADO)"; faltou=1
  else echo "  token admin vs $outro ......... diferente, como deve ser"; fi
done

# nº 5: o token não pode ter vazado para o env da célula errada.
if grep -rq "$TOKEN_ADMIN" env/ --exclude=admin.env --exclude=identidade.env 2>/dev/null
then echo "  token só nos dois envs certos  NÃO (apareceu em outro env)"; faltou=1
else echo "  token só nos dois envs certos  OK"; fi
echo

[ "$faltou" -eq 0 ] || parar "algo acima ficou FALTANDO — me mande esta tela inteira e não mergeie nada ainda."

echo "PRONTO: admin provisionada."
echo
echo "Nenhum segredo apareceu na tela, e você não precisou digitar nada — a"
echo "lista de quem entra veio do env da identidade, que já a tinha."
echo "Nenhum container foi reiniciado: quem faz isso é o deploy do próximo merge."
echo
echo "AGORA: volte ao chat e diga 'colei'. O agente mergeia o PR de infra e confere."
