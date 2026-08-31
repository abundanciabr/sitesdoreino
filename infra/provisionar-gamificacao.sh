#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `gamificacao` NA VPS — o passo do mantenedor.
# Cria o par banco+role isolado, descobre o site no catálogo, escreve o env real
# da célula e abre o par de conversa que ela precisa (identidade).
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-gamificacao.sh -o /tmp/g.sh && bash /tmp/g.sh meshcraft.top
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha —
# os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor. Script versionado + uma linha curta de invocação elimina
# os dois modos de falha (H18/H19/H20).
#
# SEGREDOS: a senha do banco, a chave do Django e o token do par são gerados
# AQUI, dentro da VPS, e gravados direto nos arquivos. Nenhum aparece na tela,
# nenhum passa por agente, nenhum entra no Git (INV-P8, Lei 5).
#
# O CAMPO QUE ESTE SCRIPT SE RECUSA A DEIXAR VAZIO: `SITE_ID`
# -----------------------------------------------------------
# O contrato congelado (`contracts/gamificacao.openapi.yaml`) não tem `site_id`
# em nenhuma das duas operações, e a célula ainda não tem middleware para
# resolver o site pelo Host — quem responde "de que site é este perfil?" é o env,
# lido no ponto de uso por `apps/core/sessao.py::site_atual()`.
#
# Ausente, a porta responde SEM etiqueta e grita no log: é a falha ABERTA que o
# contrato manda ("página sem selo, nunca página quebrada"). E é justamente por
# ser aberta que ela se esconde bem — sem `SITE_ID` a etiqueta de TODOS os alunos
# da escola some de uma vez e NENHUMA tela quebra para avisar.
#
# Por isso este script não aceita terminar sem ele: o número é PERGUNTADO ao
# catálogo (nunca chutado, nunca digitado pelo mantenedor), e zero sites ativos
# ou site ambíguo PARAM antes de qualquer criação. Guarda:
# `ci/tests/test_provisionar_gamificacao.py`.
#
# ELE RECARREGA UMA CÉLULA no fim (`identidade`), e precisa: a chave nova é
# escrita no ARQUIVO de env, e um container só relê o env dele quando renasce.
# Sem essa recarga a gamificação sobe e leva 401 ao perguntar quem é a pessoa,
# com o deploy verde. São segundos, e ninguém é deslogado (a sessão vive no
# banco, não na memória do processo).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só nasce
# se faltar, o token do par é REAPROVEITADO se já existir, e o env antigo vira
# `.bak-<epoch>` antes de ser reescrito. ATENÇÃO: re-rodar ROTACIONA a chave do
# Django e a senha do banco desta célula — o XP e as medalhas continuam intactos
# (estão no banco, não na chave), mas a célula reinicia.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/g.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/g.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_GAMIFICACAO="env/gamificacao.env"
ENV_IDENTIDADE="env/identidade.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_IDENTIDADE"

# O endereço interno sai do `servers:` do contrato congelado da identidade, e
# não é escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"

# -----------------------------------------------------------------------------
# 1. ONDE — tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
[ -f "$ENV_IDENTIDADE" ] || parar "não achei $RAIZ/$ENV_IDENTIDADE — a gamificação precisa perguntar quem é a pessoa, e essa célula não está provisionada aqui. Nada foi criado, nada foi alterado."
[ -w "$ENV_IDENTIDADE" ] || parar "não consigo escrever em $RAIZ/$ENV_IDENTIDADE — rode como root ou como o dono dos env. Nada foi alterado."

# -----------------------------------------------------------------------------
# 2. TRAVA DE DERIVA — este script REESCREVE `env/gamificacao.env` inteiro.
#    Só pode rodar enquanto souber gerar TODAS as chaves que o arquivo vivo tem.
#    Sem isto, o dia em que alguém acrescentar uma variável aqui (e a escada da
#    gamificação tem doze degraus pela frente, cada um uma chance), re-rodar o
#    script a apagaria em silêncio, com o deploy verde (`armadilhas/111`).
#    Guarda: `ci/tests/test_provisionamento_nao_perde_variavel.py`.
# -----------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="DATABASE_URL DEBUG DJANGO_SECRET_KEY IDENTIDADE_API_TOKEN IDENTIDADE_API_URL SCRIPT_NAME SITE_ID"

# LITERAL, e não `$ENV_GAMIFICACAO`, de propósito: quem confere esta trava é
# `ci/tests/test_provisionamento_nao_perde_variavel.py`, e ele lê o script como
# TEXTO — na VPS não há Python nem este repositório para interpretar variável.
# A forma literal é o que torna o guarda possível.
if [ -f env/gamificacao.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_GAMIFICACAO" | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o $ENV_GAMIFICACAO desta máquina tem variável que eu"
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

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

echo "== 1/5 — estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='gamificacao_db'" 2>/dev/null | grep -q 1
then echo "  banco gamificacao_db ... já existe"; else echo "  banco gamificacao_db ... não existe"; fi
if [ -f "$ENV_GAMIFICACAO" ]
then echo "  env/gamificacao.env .... já existe (guardo cópia antes de reescrever)"
else echo "  env/gamificacao.env .... não existe"; fi
echo

# -----------------------------------------------------------------------------
# 3. O SITE — perguntado ao catálogo, e este script NÃO TERMINA sem ele.
#    Vem ANTES de criar banco ou escrever arquivo, de propósito: recusar aqui
#    significa que nada foi criado e não há meia-instalação para desfazer.
#
#    A regra do host é a MESMA de `semear-caixa.sh`, e ela existe porque a
#    plataforma é multissítio (Lei 9): em 27/08/2026 a produção já servia DOIS
#    hosts. Com argumento, usa o pedido e PARA se ele não existir; sem
#    argumento, só segue se houver exatamente UM site ativo. "O primeiro da
#    lista" seria o chute que amarra o XP de todo mundo ao site errado.
# -----------------------------------------------------------------------------
echo "== 2/5 — descobrindo o site no catálogo =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "catalogo" || true)
[ -n "$ESTADO" ] || parar "o serviço 'catalogo' não está rodando, e é ele quem sabe o número do site. Suba a plataforma (docker compose up -d) e rode de novo. Nada foi criado."

# A resposta CRUA primeiro, e o filtro depois, em dois passos de propósito:
# num pipe único, "o catálogo não respondeu" e "o catálogo respondeu que não há
# site ativo" chegam aqui como o MESMO exit 1 (quem falha é o `grep`), e o
# mantenedor leria "não consegui perguntar" quando o problema é outro. Duas
# causas diferentes precisam de duas telas diferentes: uma manda olhar o
# serviço, a outra manda cadastrar o site.
BRUTO=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null) \
  || parar "não consegui perguntar ao catálogo quais sites existem. Nada foi criado."

SITES=$(printf '%s\n' "$BRUTO" | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s' || true)
QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. Sem site não há a quem amarrar o XP dos alunos, e a gamificação subiria sem etiqueta nenhuma. Nada foi criado."

listar_sites() {
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST; do
    echo "     - $HOST  ($ID)"
  done
}

HOST_PEDIDO="${1:-}"
if [ -n "$HOST_PEDIDO" ]; then
  LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
  if [ -z "$LINHA" ]; then
    echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
    listar_sites
    parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim). Nada foi criado."
  fi
  SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
  SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
elif [ "$QUANTOS" -gt 1 ]; then
  echo "  Achei mais de um site ativo:"
  listar_sites
  echo
  echo "  Rode de novo dizendo QUAL, por exemplo:"
  echo "     bash /tmp/g.sh meshcraft.top"
  parar "há $QUANTOS sites ativos e eu não escolho por você. Nada foi criado."
else
  SITE_ID=$(printf '%s\n' "$SITES" | head -n1 | cut -f1)
  SITE_HOST=$(printf '%s\n' "$SITES" | head -n1 | cut -f2)
fi

# A recusa final, e ela é a razão de ser deste bloco: env sem SITE_ID apaga a
# etiqueta de todo aluno sem quebrar tela nenhuma. Se chegamos aqui com o campo
# vazio, alguma leitura acima falhou de um jeito que eu não previ — e escrever o
# arquivo assim seria pior do que não escrever.
[ -n "${SITE_ID:-}" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site. Sem SITE_ID a etiqueta de TODOS os alunos some e nenhuma tela quebra para avisar, então eu não escrevo o env. Nada foi criado."
echo "  site ...... ${SITE_HOST:-?}"
echo "  número .... $SITE_ID"
echo

# -----------------------------------------------------------------------------
# 4. OS SEGREDOS E O BANCO — par isolado, como manda a Lei 2.
# -----------------------------------------------------------------------------
echo "== 3/5 — banco e senha próprios da célula =="
# O token do par é REAPROVEITADO se já existir: gerar um novo quando há um em uso
# derrubaria a conversa que funciona.
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_GAMIFICACAO)"
[ -n "$T_IDENTIDADE" ] || T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par gamificacao->identidade ficou curto demais. Nada foi alterado."

SENHA_DB="$(gerar_segredo)" || parar "não consegui gerar a senha do banco. Nada foi alterado."
CHAVE_DJANGO="$(gerar_segredo)" || parar "não consegui gerar a chave do Django. Nada foi alterado."

psql_super -c "ALTER ROLE gamificacao_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE gamificacao_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário gamificacao_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='gamificacao_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE gamificacao_db OWNER gamificacao_user" >/dev/null \
  || parar "não consegui criar o banco gamificacao_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE gamificacao_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."
echo "  banco e usuário ........ prontos, fechados ao público"
echo

# -----------------------------------------------------------------------------
# 5. O ENV DA CÉLULA — reescrito inteiro, com cópia do anterior.
# -----------------------------------------------------------------------------
echo "== 4/5 — escrevendo o env da célula =="
umask 077
[ -f "$ENV_GAMIFICACAO" ] && cp -a "$ENV_GAMIFICACAO" "$ENV_GAMIFICACAO.bak-$(date +%s)"

# O molde é infra/env/gamificacao.env.exemplo — se aquele arquivo ganhar variável
# nova, este bloco e a lista CHAVES_QUE_EU_GERO precisam ganhar junto.
# LITERAL pelo mesmo motivo da trava acima: o guarda procura este heredoc por
# texto para comparar as chaves com a lista `CHAVES_QUE_EU_GERO`.
cat > env/gamificacao.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://gamificacao_user:$SENHA_DB@postgres:5432/gamificacao_db
DEBUG=0
SCRIPT_NAME=/conquistas
SITE_ID=$SITE_ID
IDENTIDADE_API_URL=$IDENTIDADE_URL
IDENTIDADE_API_TOKEN=$T_IDENTIDADE
ENV

chown --reference="$ENV_REF" "$ENV_GAMIFICACAO" 2>/dev/null \
  || parar "não consegui ajustar o dono de $ENV_GAMIFICACAO — rode como root."
chmod --reference="$ENV_REF" "$ENV_GAMIFICACAO" 2>/dev/null \
  || parar "não consegui ajustar as permissões de $ENV_GAMIFICACAO — rode como root."
echo "  $ENV_GAMIFICACAO ... escrito ($(grep -c '=' "$ENV_GAMIFICACAO") variáveis)"
echo

# -----------------------------------------------------------------------------
# 6. O OUTRO LADO DO PAR — acrescentado, nunca reescrito.
#    PROVEDOR ANTES DE CONSUMIDOR já aconteceu: o env da gamificação acima já
#    tem o token, mas a célula ainda não está no compose. Quando estiver, os
#    dois lados já se conhecem.
#
#    Não há `TOKENS_COMPLETOS_GAMIFICACAO`, e a ausência é a decisão: aquele
#    degrau libera E-MAIL, e esta célula pede só o id opaco (`getSession`).
#    Conceder o que não se usa é superfície de graça.
# -----------------------------------------------------------------------------
echo "== 5/5 — abrindo a conversa com a identidade =="
MEXIDOS=""
garantir() {  # arquivo, chave, valor, cabeçalho
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  [ -f "$arq.bak-provisionar-gamificacao" ] || cp -a "$arq" "$arq.bak-provisionar-gamificacao"

  if grep -q "^$chave=" "$arq"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arq" \
      || parar "a edição de $arq falhou. Há cópia intacta em $arq.bak-provisionar-gamificacao."
  else
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # chave nova no fim da última linha — e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-gamificacao.sh (DECISAO-gamificacao).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" || parar "não consegui escrever em $arq."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null || parar "não consegui ajustar o dono de $arq — rode como root."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null || parar "não consegui ajustar as permissões de $arq — rode como root."
  fi
  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

garantir "$ENV_IDENTIDADE" TOKENS_ACEITOS_GAMIFICACAO "$T_IDENTIDADE" "par gamificacao->identidade: a gamificacao pergunta quem e a pessoa"

# -----------------------------------------------------------------------------
# 7. RECARREGAR O PAR — sem isto, a gamificação sobe e leva 401 ao perguntar
#    quem é a pessoa. A chave acima foi escrita no ARQUIVO, e um container só lê
#    o env dele quando (re)nasce.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só este serviço, pelo nome. A
#    `gamificacao` NÃO entra aqui de propósito — ela ainda não existe neste
#    compose; quem a põe lá é a entrega de `infra/`, depois desta tela.
# -----------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1 && docker compose config --services 2>/dev/null | grep -qx "identidade"; then
  if docker compose up -d identidade >/dev/null 2>&1; then
    echo "  recarreguei: identidade"
  else
    echo "  (aviso: não consegui recarregar a identidade. O arquivo JÁ está certo; o próximo deploy dela relê o env. Avise o agente.)"
  fi
else
  echo "  (aviso: não achei o serviço identidade no compose desta máquina. O arquivo JÁ está certo; o próximo deploy relê o env.)"
fi
echo

# -----------------------------------------------------------------------------
# 8. O QUE FICOU
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
echo "  banco gamificacao_db ... pronto, fechado ao público"
echo "  $ENV_GAMIFICACAO ... escrito, com SITE_ID preenchido"
echo "  par aberto ............. gamificacao->identidade"
for arq in $MEXIDOS; do echo "  tocado ................. $arq (cópia em $arq.bak-provisionar-gamificacao)"; done
echo
echo "== PRONTO. Copie esta tela inteira e mande para o robô. =="
echo "A gamificação ainda NÃO está no ar: falta a entrega que a põe no"
echo "docker-compose e no roteador, em /conquistas. O robô faz essa parte"
echo "sozinho, depois desta tela."
