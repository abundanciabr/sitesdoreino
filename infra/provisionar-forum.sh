#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `forum` NA VPS — o passo do mantenedor.
# Cria o par banco+role isolado, escreve o env real da célula, e abre os dois
# pares de conversa que o fórum precisa (identidade e alunos).
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-forum.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha —
# os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor. Script versionado + uma linha curta de invocação elimina
# os dois modos de falha (H18/H19/H20).
#
# SEGREDOS: as senhas e os tokens são gerados AQUI, dentro da VPS, e gravados
# direto nos arquivos. Nenhum aparece na tela, nenhum passa por agente, nenhum
# entra no Git (INV-P8, Lei 5).
#
# ELE RECARREGA DUAS CÉLULAS no fim (`identidade` e `alunos`), e precisa: as
# chaves novas são escritas no ARQUIVO de env, e um container só relê o env dele
# quando renasce. Sem essa recarga o fórum sobe e leva 401 em toda página, com o
# deploy verde. São segundos de indisponibilidade nessas duas, e ninguém é
# deslogado (a sessão vive no banco, não na memória do processo).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só nasce
# se faltar, os tokens de par são REAPROVEITADOS se já existirem, e o env antigo
# vira `.bak-<epoch>` antes de ser reescrito. ATENÇÃO: re-rodar ROTACIONA a
# chave do Django e a senha do banco desta célula — as conversas continuam
# intactas (estão no banco, não na chave), mas a célula reinicia.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_FORUM="env/forum.env"
ENV_IDENTIDADE="env/identidade.env"
ENV_ALUNOS="env/alunos.env"
ENV_ADMIN="env/admin.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ALUNOS"

# Os endereços internos saem do `servers:` dos contratos congelados, e não são
# escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE — tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
for arquivo in "$ENV_IDENTIDADE" "$ENV_ALUNOS"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo — o fórum precisa conversar com essa célula, e ela não está provisionada aqui. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo — rode como root ou como o dono dos env. Nada foi alterado."
done

# -----------------------------------------------------------------------------
# 2. TRAVA DE DERIVA — este script REESCREVE `env/forum.env` inteiro.
#    Só pode rodar enquanto souber gerar TODAS as chaves que o arquivo vivo tem.
#    Sem isto, o dia em que alguém acrescentar uma variável aqui, re-rodar o
#    script a apagaria em silêncio, com o deploy verde (`armadilhas/111`).
#    Guarda: `ci/tests/test_provisionamento_nao_perde_variavel.py`.
# -----------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="ADMIN_EMAILS ALUNOS_API_TOKEN ALUNOS_API_URL DATABASE_URL DEBUG DJANGO_SECRET_KEY FORUM_PROFESSORES IDENTIDADE_API_TOKEN IDENTIDADE_API_URL SCRIPT_NAME"

# LITERAL, e não `$ENV_FORUM`, de propósito: quem confere esta trava é
# `ci/tests/test_provisionamento_nao_perde_variavel.py`, e ele lê o script
# como TEXTO — na VPS não há Python nem este repositório para interpretar
# variável. A forma literal é o que torna o guarda possível.
if [ -f env/forum.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_FORUM" | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o $ENV_FORUM desta máquina tem variável que eu NÃO"
    echo "sei gerar, e eu reescrevo o arquivo inteiro. Rodar assim apagaria:"
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

echo "== estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='forum_db'" 2>/dev/null | grep -q 1
then echo "  banco forum_db ......... já existe"; else echo "  banco forum_db ......... não existe"; fi
if [ -f "$ENV_FORUM" ]
then echo "  env/forum.env .......... já existe (guardo cópia antes de reescrever)"
else echo "  env/forum.env .......... não existe"; fi
echo

# -----------------------------------------------------------------------------
# 3. OS TOKENS DOS PARES — reaproveitados se já existirem.
#    Gerar token novo quando já há um em uso derrubaria a conversa que funciona.
# -----------------------------------------------------------------------------
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_FORUM)"
T_ALUNOS="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_FORUM)"
[ -n "$T_IDENTIDADE" ] || T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ -n "$T_ALUNOS" ]     || T_ALUNOS="$(gerar_segredo)"     || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par forum→identidade ficou curto demais. Nada foi alterado."
[ ${#T_ALUNOS} -ge 32 ]     || parar "o token do par forum→alunos ficou curto demais. Nada foi alterado."

# Os administradores do fórum são os MESMOS do painel — copiados de lá numa
# FOTOGRAFIA, não numa ligação viva. Se a lista mudar no painel, rode este
# script de novo para o fórum acompanhar. Vazio ⇒ ninguém, que é fail-closed.
ADMINS="$(ler_de "$ENV_ADMIN" ADMIN_EMAILS)"

SENHA_DB="$(gerar_segredo)" || parar "não consegui gerar a senha do banco. Nada foi alterado."
CHAVE_DJANGO="$(gerar_segredo)" || parar "não consegui gerar a chave do Django. Nada foi alterado."

# -----------------------------------------------------------------------------
# 4. O BANCO — par isolado, como manda a Lei 2.
# -----------------------------------------------------------------------------
psql_super -c "ALTER ROLE forum_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE forum_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário forum_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='forum_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE forum_db OWNER forum_user" >/dev/null \
  || parar "não consegui criar o banco forum_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE forum_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."

# A extensão que prepara a cura dos dois buracos da busca em português
# (`armadilhas/154`): sem `unaccent`, quem digitar "chapeu" nunca acha
# "chapéu" — e no Brasil quase ninguém acentua ao buscar. Instalar exige
# superusuário, então é AQUI e não numa migração do Django, que roda com o
# papel restrito da célula. Só instala; quem passa a usá-la é o código, depois.
psql_super -d forum_db -c "CREATE EXTENSION IF NOT EXISTS unaccent" >/dev/null 2>&1 \
  && echo "  extensão unaccent ...... pronta (a busca sem acento pode ser ligada)" \
  || echo "  AVISO: não consegui instalar a extensão unaccent. O fórum funciona; a busca sem acento fica para depois."

# -----------------------------------------------------------------------------
# 5. O ENV DA CÉLULA — reescrito inteiro, com cópia do anterior.
# -----------------------------------------------------------------------------
umask 077
[ -f "$ENV_FORUM" ] && cp -a "$ENV_FORUM" "$ENV_FORUM.bak-$(date +%s)"

# O molde é infra/env/forum.env.exemplo — se aquele arquivo ganhar variável
# nova, este bloco e a lista CHAVES_QUE_EU_GERO precisam ganhar junto.
# LITERAL pelo mesmo motivo da trava acima: o guarda procura este heredoc
# por texto para comparar as chaves com a lista `CHAVES_QUE_EU_GERO`.
cat > env/forum.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://forum_user:$SENHA_DB@postgres:5432/forum_db
DEBUG=0
SCRIPT_NAME=/forum
IDENTIDADE_API_URL=$IDENTIDADE_URL
IDENTIDADE_API_TOKEN=$T_IDENTIDADE
ALUNOS_API_URL=$ALUNOS_URL
ALUNOS_API_TOKEN=$T_ALUNOS
FORUM_PROFESSORES=
ADMIN_EMAILS=$ADMINS
ENV

chown --reference="$ENV_REF" "$ENV_FORUM" 2>/dev/null \
  || parar "não consegui ajustar o dono de $ENV_FORUM — rode como root."
chmod --reference="$ENV_REF" "$ENV_FORUM" 2>/dev/null \
  || parar "não consegui ajustar as permissões de $ENV_FORUM — rode como root."

# -----------------------------------------------------------------------------
# 6. O OUTRO LADO DOS PARES — acrescentado, nunca reescrito.
#    PROVEDOR ANTES DE CONSUMIDOR já aconteceu: o env do fórum acima já tem os
#    tokens, mas a célula ainda não está no compose. Quando estiver, os dois
#    lados já se conhecem.
# -----------------------------------------------------------------------------
MEXIDOS=""
garantir() {  # arquivo, chave, valor, cabeçalho
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  [ -f "$arq.bak-provisionar-forum" ] || cp -a "$arq" "$arq.bak-provisionar-forum"

  if grep -q "^$chave=" "$arq"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arq" \
      || parar "a edição de $arq falhou. Há cópia intacta em $arq.bak-provisionar-forum."
  else
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # chave nova no fim da última linha — e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-forum.sh (DECISAO-forum-da-escola).\n' "$cabecalho" >> "$arq"
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

garantir "$ENV_IDENTIDADE" TOKENS_ACEITOS_FORUM "$T_IDENTIDADE" "par forum->identidade: o forum pergunta quem e a pessoa"
# O DEGRAU DO E-MAIL, e é o MESMO token — valores diferentes dariam 403
# silencioso em toda página do fórum. Registrado por escrito em
# DECISAO-celula-de-identidade.md §6.3, como aquela lei exige.
garantir "$ENV_IDENTIDADE" TOKENS_COMPLETOS_FORUM "$T_IDENTIDADE" "degrau de e-mail do forum (DECISAO-forum-da-escola §3)"
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_FORUM "$T_ALUNOS" "par forum->alunos: o forum pergunta em que categoria a pessoa esta"

# -----------------------------------------------------------------------------
# 7. RECARREGAR OS PARES — sem isto, o forum sobe e leva 401 em toda pagina.
#    As chaves acima foram escritas no ARQUIVO, e um container so le o env dele
#    quando (re)nasce. Enquanto `identidade` e `alunos` seguirem rodando com o
#    env antigo em memoria, elas nao conhecem `TOKENS_ACEITOS_FORUM` — e a
#    resposta para o forum e 401, em toda requisicao, com tudo verde no deploy.
#    E o mesmo passo que `provisionar-pares-de-categorias.sh` da, pelo mesmo
#    motivo.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    celulas a tag :main do compose (RITOS §4). So estes servicos, pelo nome.
#    O `forum` NAO entra aqui de proposito — ele ainda nao existe neste compose;
#    quem o poe la e a entrega de `infra/`, depois desta tela.
# -----------------------------------------------------------------------------
echo "== recarregando os pares para eles relerem o env =="
if command -v docker >/dev/null 2>&1; then
  ALVOS=""
  for servico in identidade alunos; do
    docker compose config --services 2>/dev/null | grep -qx "$servico" && ALVOS="$ALVOS $servico"
  done
  if [ -n "$ALVOS" ]; then
    if docker compose up -d $ALVOS >/dev/null 2>&1; then
      echo "  recarreguei:$ALVOS"
    else
      echo "  (aviso: nao consegui recarregar$ALVOS — os arquivos JA estao certos; o proximo deploy de cada celula rele o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: nao achei estes servicos no compose desta maquina — o proximo deploy rele o env.)"
  fi
else
  echo "  (aviso: nao achei o docker aqui — os arquivos JA estao certos; o proximo deploy rele o env.)"
fi
echo

# -----------------------------------------------------------------------------
# 8. O QUE FICOU
# -----------------------------------------------------------------------------
echo
echo "== estado DEPOIS =="
echo "  banco forum_db ......... pronto, fechado ao público"
echo "  $ENV_FORUM ....... escrito ($(grep -c '=' "$ENV_FORUM") variáveis)"
echo "  pares abertos .......... forum->identidade (com degrau de e-mail), forum->alunos"
for arq in $MEXIDOS; do echo "  tocado ................. $arq (cópia em $arq.bak-provisionar-forum)"; done
if [ -z "$ADMINS" ]; then
  echo
  echo "  AVISO: ADMIN_EMAILS ficou VAZIO (não achei em $ENV_ADMIN)."
  echo "  Isso é fail-closed: ninguém modera o fórum até a lista existir."
fi
echo
echo "== PRONTO. Copie esta tela inteira e mande para o robô. =="
echo "O fórum ainda NÃO está no ar: falta a entrega que o põe no docker-compose"
echo "e no roteador. O robô faz essa parte sozinho, depois desta tela."
