#!/usr/bin/env bash
# =============================================================================
# PROVISIONAR A CÉLULA `cursos` NA VPS, o passo do mantenedor.
# Cria o par banco+role isolado, descobre o site no catálogo, escreve o env real
# da célula e abre os DOIS pares de conversa que ela precisa (identidade, alunos).
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-cursos.sh -o /tmp/c.sh && bash /tmp/c.sh meshcraft.top
#
# POR QUE ESTE ARQUIVO EXISTE, e não um bloco colado no terminal: em 24/08/2026
# o console da VPS embaralhou DUAS colagens seguidas de um bloco multi-linha
# (os pedaços se sobrepuseram, o script rodou pela metade e um deles derrubou a
# sessão do mantenedor). Script versionado + uma linha curta de invocação
# elimina os dois modos de falha (H18/H19/H20).
#
# QUANDO ELE RODA, e a ordem não é preferência: ESTE PR vem antes do degrau 1.7
# (compose + Traefik). Sem o banco, o container da célula entra em crashloop
# assim que o compose a conhecer. É a lição H18, e é por isso que o roteiro do
# mantenedor vem primeiro.
#
# SEGREDOS: a senha do banco, a chave do Django e os tokens dos pares são
# gerados AQUI, dentro da VPS, e gravados direto nos arquivos. Nenhum aparece na
# tela, nenhum passa por agente, nenhum entra no Git (INV-P8, Lei 5).
#
# O CAMPO QUE ESTE SCRIPT SE RECUSA A DEIXAR VAZIO: `SITE_ID`
# -----------------------------------------------------------
# A plataforma é multissítio (Lei 9 / [INV-P11]) e toda entidade desta célula
# nasce amarrada a um site: um curso por site no lançamento (lei §4). Esta
# célula não tem middleware para resolver o site pelo Host, e o único lugar
# onde a resposta existe é o env.
#
# Ausente, o mapa das portas de uma escola inteira responderia vazio, ou pior,
# misturado com o de outro site, e nenhuma tela quebraria para avisar. Por isso
# o número é PERGUNTADO ao catálogo (nunca chutado, nunca digitado pelo
# mantenedor), e zero sites ativos ou site ambíguo PARAM antes de qualquer
# criação.
#
# ELE RECARREGA DUAS CÉLULAS no fim (`identidade` e `alunos`), e precisa: as
# chaves novas são escritas nos ARQUIVOS de env, e um container só relê o env
# dele quando renasce. Sem essas recargas a célula sobe e leva 401 ao perguntar
# quem é a pessoa, com o deploy verde. São segundos, e ninguém é deslogado (a
# sessão vive no banco, não na memória do processo).
#
# IDEMPOTENTE: rodar de novo é seguro. O role ganha senha nova, o banco só nasce
# se faltar, os tokens dos pares são REAPROVEITADOS se já existirem, e o env
# antigo vira `.bak-<epoch>` antes de ser reescrito. ATENÇÃO: re-rodar ROTACIONA
# a chave do Django e a senha do banco desta célula. As aulas, os envios e os
# laudos continuam intactos (estão no banco, não na chave), mas a célula
# reinicia.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/c.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/c.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_CURSOS="env/cursos.env"
ENV_IDENTIDADE="env/identidade.env"
ENV_ALUNOS="env/alunos.env"
# De onde sai a lista de quem entra no /admin/. Este script NÃO a gera: copia.
ENV_ADMIN="env/admin.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_IDENTIDADE"

# Os endereços internos saem do `servers:` dos contratos congelados, e não são
# escolha deste script.
IDENTIDADE_URL="http://identidade:8000/interno"
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE, tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
for arquivo in "$ENV_IDENTIDADE" "$ENV_ALUNOS"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo. A sala de aula precisa conversar com essa célula, e ela não está provisionada aqui. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo. Rode como root ou como o dono dos env. Nada foi alterado."
done

# -----------------------------------------------------------------------------
# 2. TRAVA DE DERIVA: este script REESCREVE `env/cursos.env` inteiro.
#    Só pode rodar enquanto souber gerar TODAS as chaves que o arquivo vivo tem.
#    Sem isto, o dia em que alguém acrescentar uma variável aqui, re-rodar o
#    script a apagaria em silêncio, com o deploy verde (`armadilhas/111`).
#    Guarda: `ci/tests/test_provisionamento_nao_perde_variavel.py`.
#
#    A data era previsível e chegou em 05/09/2026, com o
#    `infra/abrir-a-sala-de-aula.sh`: `ADMIN_EMAILS` (quem entra no /admin/ e,
#    por isso, no plantão), `ANTHROPIC_API_KEY` e `ANTHROPIC_WORKSPACE_ID` (o
#    Assistente de laudo) passaram a existir no env vivo, escritas por AQUELE
#    roteiro. Elas entraram nesta lista no MESMO PR, e o bloco de leitura da
#    seção 4 as PRESERVA relendo do arquivo vivo, porque reescrever o env sem
#    saber delas as apagaria em silêncio, com o deploy verde. `CURSOS_PROFESSORES`
#    entra junto pelo mesmo motivo: ela é lista escrita à mão pelo mantenedor,
#    e ninguém aqui sabe inventá-la.
#
#    O QUE AINDA NÃO ESTÁ NESTA LISTA, e é dito na cara para ninguém descobrir
#    pela recusa: `TOKENS_ACEITOS_ADMIN`, `CATALOGO_API_URL` e `TOKEN_CATALOGO`.
#    Quem as escreve é `infra/provisionar-pares-da-sala-de-aula.sh`, e depois de
#    ELE rodar esta trava passa a recusar toda nova execução deste script. A
#    recusa é fail-closed e barulhenta (não apaga nada, e manda avisar o
#    agente), mas ela torna falsa a promessa de idempotência do cabeçalho. Fazer
#    este roteiro herdar as três é mudar de dono uma variável entre dois
#    roteiros, e essa decisão pede tarefa própria, não um parágrafo aqui.
# -----------------------------------------------------------------------------
CHAVES_QUE_EU_GERO="ADMIN_EMAILS ALUNOS_API_TOKEN ALUNOS_API_URL ANTHROPIC_API_KEY ANTHROPIC_WORKSPACE_ID CURSOS_PROFESSORES DATABASE_URL DEBUG DJANGO_SECRET_KEY IDENTIDADE_API_TOKEN IDENTIDADE_API_URL SCRIPT_NAME SITE_ID"

# LITERAL, e não `$ENV_CURSOS`, de propósito: quem confere esta trava é
# `ci/tests/test_provisionamento_nao_perde_variavel.py`, e ele lê o script como
# TEXTO. Na VPS não há Python nem este repositório para interpretar variável.
# A forma literal é o que torna o guarda possível.
if [ -f env/cursos.env ]; then
  SOBRANDO=""
  for CHAVE in $(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_CURSOS" | tr -d '=' | sort -u); do
    case " $CHAVES_QUE_EU_GERO " in
      *" $CHAVE "*) : ;;
      *) SOBRANDO="$SOBRANDO $CHAVE" ;;
    esac
  done
  if [ -n "$SOBRANDO" ]; then
    echo "PAROU POR SEGURANÇA: o $ENV_CURSOS desta máquina tem variável que eu"
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

echo "== 1/5: estado ANTES =="
if psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='cursos_db'" 2>/dev/null | grep -q 1
then echo "  banco cursos_db ... já existe"; else echo "  banco cursos_db ... não existe"; fi
if [ -f "$ENV_CURSOS" ]
then echo "  env/cursos.env .... já existe (guardo cópia antes de reescrever)"
else echo "  env/cursos.env .... não existe"; fi
echo

# -----------------------------------------------------------------------------
# 3. O SITE, perguntado ao catálogo, e este script NÃO TERMINA sem ele.
#    Vem ANTES de criar banco ou escrever arquivo, de propósito: recusar aqui
#    significa que nada foi criado e não há meia-instalação para desfazer.
#
#    A regra do host é a MESMA de `provisionar-gamificacao.sh`, e ela existe
#    porque a plataforma é multissítio (Lei 9): em 27/08/2026 a produção já
#    servia DOIS hosts. Com argumento, usa o pedido e PARA se ele não existir;
#    sem argumento, só segue se houver exatamente UM site ativo. "O primeiro da
#    lista" seria o chute que amarra a sala de aula de todo mundo ao site errado.
# -----------------------------------------------------------------------------
echo "== 2/5: descobrindo o site no catálogo =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "catalogo" || true)
[ -n "$ESTADO" ] || parar "o serviço 'catalogo' não está rodando, e é ele quem sabe o número do site. Suba a plataforma (docker compose up -d) e rode de novo. Nada foi criado."

# A resposta CRUA primeiro, e o filtro depois, em dois passos de propósito:
# num pipe único, "o catálogo não respondeu" e "o catálogo respondeu que não há
# site ativo" chegam aqui como o MESMO exit 1 (quem falha é o `grep`), e o
# mantenedor leria "não consegui perguntar" quando o problema é outro
# (`armadilhas/240`). Duas causas diferentes precisam de duas telas diferentes.
BRUTO=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null) \
  || parar "não consegui perguntar ao catálogo quais sites existem. Nada foi criado."

SITES=$(printf '%s\n' "$BRUTO" | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s' || true)
QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. Sem site não há a quem amarrar as aulas e os envios, e a célula subiria sem etiqueta nenhuma. Nada foi criado."

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
  echo "     bash /tmp/c.sh meshcraft.top"
  parar "há $QUANTOS sites ativos e eu não escolho por você. Nada foi criado."
else
  SITE_ID=$(printf '%s\n' "$SITES" | head -n1 | cut -f1)
  SITE_HOST=$(printf '%s\n' "$SITES" | head -n1 | cut -f2)
fi

# A recusa final, e ela é a razão de ser deste bloco: env sem SITE_ID mistura ou
# esvazia o mapa das portas de uma escola inteira sem quebrar tela nenhuma. Se
# chegamos aqui com o campo vazio, alguma leitura acima falhou de um jeito que
# eu não previ, e escrever o arquivo assim seria pior do que não escrever.
[ -n "${SITE_ID:-}" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site. Sem SITE_ID a sala de aula responde para o site errado e nenhuma tela quebra para avisar, então eu não escrevo o env. Nada foi criado."
echo "  site ...... ${SITE_HOST:-?}"
echo "  número .... $SITE_ID"
echo

# -----------------------------------------------------------------------------
# 4. OS SEGREDOS E O BANCO: par isolado, como manda a Lei 2.
# -----------------------------------------------------------------------------
echo "== 3/5: banco e senha próprios da célula =="
# Os tokens dos pares são REAPROVEITADOS se já existirem: gerar novos quando há
# um em uso derrubaria a conversa que funciona.
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_CURSOS)"
[ -n "$T_IDENTIDADE" ] || T_IDENTIDADE="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_IDENTIDADE} -ge 32 ] || parar "o token do par cursos->identidade ficou curto demais. Nada foi alterado."

T_ALUNOS="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_CURSOS)"
[ -n "$T_ALUNOS" ] || T_ALUNOS="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
[ ${#T_ALUNOS} -ge 32 ] || parar "o token do par cursos->alunos ficou curto demais. Nada foi alterado."

# ── AS QUATRO QUE ESTE SCRIPT NÃO SABE GERAR, e por isso RELÊ ───────────────
# Reescrever o arquivo inteiro sem estas quatro linhas as apagaria em silêncio,
# com o container de pé e o deploy verde (`armadilhas/111`). O efeito seria o
# plantão fechar para o próprio dono e o botão "Rascunhar laudo" sumir da tela,
# sem erro em lugar nenhum. Fail-closed por falta de valor é indistinguível de
# fail-closed por decisão, e é isso que torna esta classe de defeito cara.

# Os administradores da sala de aula são os MESMOS do painel, copiados de lá
# numa FOTOGRAFIA, não numa ligação viva (o mesmo desenho do
# `provisionar-forum.sh`). Se a lista mudar no painel, rode este script de novo,
# ou o `infra/abrir-a-sala-de-aula.sh`, para a sala acompanhar. Vazio ⇒ ninguém,
# que é fail-closed.
ADMINS="$(ler_de "$ENV_ADMIN" ADMIN_EMAILS)"

# Quem entra no plantão além dos administradores: lista de ids de plataforma,
# escrita à mão pelo mantenedor. Ninguém aqui sabe inventá-la, então ela só
# pode ser preservada do arquivo vivo. Vazia é estado legítimo.
PROFESSORES="$(ler_de "$ENV_CURSOS" CURSOS_PROFESSORES)"

# A chave da Anthropic e o workspace dela. Nascem na conta do mantenedor, custam
# dinheiro por uso, e chegam aqui pelo `infra/abrir-a-sala-de-aula.sh`, que as
# copia do env do fórum. Vazias = o Assistente de laudo desligado, que é um
# estado honesto: a célula sobe igual e só o botão de rascunhar falha, em
# português, dizendo o que falta.
CHAVE_DA_IA="$(ler_de "$ENV_CURSOS" ANTHROPIC_API_KEY)"
WORKSPACE_DA_IA="$(ler_de "$ENV_CURSOS" ANTHROPIC_WORKSPACE_ID)"

SENHA_DB="$(gerar_segredo)" || parar "não consegui gerar a senha do banco. Nada foi alterado."
CHAVE_DJANGO="$(gerar_segredo)" || parar "não consegui gerar a chave do Django. Nada foi alterado."

psql_super -c "ALTER ROLE cursos_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null 2>&1 \
  || psql_super -c "CREATE ROLE cursos_user LOGIN PASSWORD '$SENHA_DB'" >/dev/null \
  || parar "não consegui criar/atualizar o usuário cursos_user."

psql_super -tAc "SELECT 1 FROM pg_database WHERE datname='cursos_db'" 2>/dev/null | grep -q 1 \
  || psql_super -c "CREATE DATABASE cursos_db OWNER cursos_user" >/dev/null \
  || parar "não consegui criar o banco cursos_db."

# A muralha de dados (Lei 2): nenhuma outra célula enxerga este banco.
psql_super -c "REVOKE ALL ON DATABASE cursos_db FROM PUBLIC" >/dev/null \
  || parar "não consegui fechar o banco ao público."
echo "  banco e usuário ........ prontos, fechados ao público"
echo

# -----------------------------------------------------------------------------
# 5. O ENV DA CÉLULA: reescrito inteiro, com cópia do anterior.
# -----------------------------------------------------------------------------
echo "== 4/5: escrevendo o env da célula =="
umask 077
[ -f "$ENV_CURSOS" ] && cp -a "$ENV_CURSOS" "$ENV_CURSOS.bak-$(date +%s)"

# O molde é infra/env/cursos.env.exemplo. Se aquele arquivo ganhar variável
# nova, este bloco e a lista CHAVES_QUE_EU_GERO precisam ganhar junto.
# LITERAL pelo mesmo motivo da trava acima: o guarda procura este heredoc por
# texto para comparar as chaves com a lista `CHAVES_QUE_EU_GERO`.
cat > env/cursos.env <<ENV
DJANGO_SECRET_KEY=$CHAVE_DJANGO
DATABASE_URL=postgres://cursos_user:$SENHA_DB@postgres:5432/cursos_db
DEBUG=0
SCRIPT_NAME=/cursos
SITE_ID=$SITE_ID
IDENTIDADE_API_URL=$IDENTIDADE_URL
IDENTIDADE_API_TOKEN=$T_IDENTIDADE
ALUNOS_API_URL=$ALUNOS_URL
ALUNOS_API_TOKEN=$T_ALUNOS
ADMIN_EMAILS=$ADMINS
CURSOS_PROFESSORES=$PROFESSORES
ANTHROPIC_API_KEY=$CHAVE_DA_IA
ANTHROPIC_WORKSPACE_ID=$WORKSPACE_DA_IA
ENV

chown --reference="$ENV_REF" "$ENV_CURSOS" 2>/dev/null \
  || parar "não consegui ajustar o dono de $ENV_CURSOS. Rode como root."
chmod --reference="$ENV_REF" "$ENV_CURSOS" 2>/dev/null \
  || parar "não consegui ajustar as permissões de $ENV_CURSOS. Rode como root."
echo "  $ENV_CURSOS ... escrito ($(grep -c '=' "$ENV_CURSOS") variáveis)"
echo

# -----------------------------------------------------------------------------
# 6. O OUTRO LADO DOS PARES: acrescentado, nunca reescrito.
#    PROVEDOR ANTES DE CONSUMIDOR já aconteceu: o env da sala de aula acima já
#    tem os tokens, mas a célula ainda não está no compose. Quando estiver, os
#    dois lados já se conhecem.
#
#    ESTE script não escreve `TOKENS_COMPLETOS_CURSOS` na identidade, e a
#    ausência é decisão, não esquecimento. A lei desta célula consome
#    `getSessionFull` (o e-mail é o que `getStudentStanding` pede no caminho),
#    e esse degrau libera E-MAIL: a lei da identidade (§6.3) exige registrar
#    ali, por escrito, o porquê de cada par novo, e ninguém lê esse degrau
#    antes do cliente do degrau 1.8. Ele entra junto com quem o lê
#    (`armadilhas/224`: declare o presente, nunca o roadmap), e é uma linha
#    de `garantir` idempotente, no mesmo molde do `provisionar-forum.sh`.
# -----------------------------------------------------------------------------
echo "== 5/5: abrindo as conversas com a identidade e a alunos =="
MEXIDOS=""
garantir() {  # arquivo, chave, valor, cabeçalho
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  [ -f "$arq.bak-provisionar-cursos" ] || cp -a "$arq" "$arq.bak-provisionar-cursos"

  if grep -q "^$chave=" "$arq"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arq" \
      || parar "a edição de $arq falhou. Há cópia intacta em $arq.bak-provisionar-cursos."
  else
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # chave nova no fim da última linha, e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-cursos.sh (DECISAO-celula-de-cursos).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" || parar "não consegui escrever em $arq."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root, e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null || parar "não consegui ajustar o dono de $arq. Rode como root."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null || parar "não consegui ajustar as permissões de $arq. Rode como root."
  fi
  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

garantir "$ENV_IDENTIDADE" TOKENS_ACEITOS_CURSOS "$T_IDENTIDADE" "par cursos->identidade: a sala de aula pergunta quem e a pessoa"
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_CURSOS "$T_ALUNOS" "par cursos->alunos: a sala de aula pergunta se a pessoa e aluna"

# -----------------------------------------------------------------------------
# 7. RECARREGAR OS PARES. Sem isto, a célula sobe e leva 401 nas duas
#    perguntas. As chaves acima foram escritas nos ARQUIVOS, e um container só
#    lê o env dele quando (re)nasce.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes serviços, pelo nome. A
#    `cursos` NÃO entra aqui de propósito: ela ainda não existe neste compose;
#    quem a põe lá é o degrau 1.7, depois desta tela.
# -----------------------------------------------------------------------------
for SERVICO in identidade alunos; do
  if command -v docker >/dev/null 2>&1 && docker compose config --services 2>/dev/null | grep -qx "$SERVICO"; then
    if docker compose up -d "$SERVICO" >/dev/null 2>&1; then
      echo "  recarreguei: $SERVICO"
    else
      echo "  (aviso: não consegui recarregar $SERVICO. O arquivo JÁ está certo; o próximo deploy dela relê o env. Avise o agente.)"
    fi
  else
    echo "  (aviso: não achei o serviço $SERVICO no compose desta máquina. O arquivo JÁ está certo; o próximo deploy relê o env.)"
  fi
done
echo

# -----------------------------------------------------------------------------
# 8. O QUE FICOU
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
echo "  banco cursos_db ........ pronto, fechado ao público"
echo "  $ENV_CURSOS ... escrito, com SITE_ID preenchido"
echo "  pares abertos .......... cursos->identidade, cursos->alunos"
for arq in $MEXIDOS; do echo "  tocado ................. $arq (cópia em $arq.bak-provisionar-cursos)"; done
if [ -n "$CHAVE_DA_IA" ]; then
  echo "  chave da IA ............ preservada (${#CHAVE_DA_IA} caracteres, não mostro o conteúdo)"
fi
if [ -z "$ADMINS" ]; then
  echo
  echo "  AVISO: ADMIN_EMAILS ficou VAZIO (não achei em $ENV_ADMIN)."
  echo "  Isso é fail-closed: o plantão da sala de aula fica fechado até a lista"
  echo "  existir, inclusive para você. Rode o infra/provisionar-admin.sh e depois"
  echo "  o infra/abrir-a-sala-de-aula.sh."
fi
if [ -z "$CHAVE_DA_IA" ]; then
  echo
  echo "  AVISO: ANTHROPIC_API_KEY ficou VAZIA (não havia uma em $ENV_CURSOS)."
  echo "  Isso não quebra nada: a sala de aula sobe igual e só o botão"
  echo "  'Rascunhar laudo' fica desligado. Quem a põe lá é o"
  echo "  infra/abrir-a-sala-de-aula.sh, que a copia do env do fórum."
fi
echo
echo "== PRONTO. Copie esta tela inteira e mande para o robô. =="
echo "A sala de aula ainda NÃO está no ar: falta a entrega que a põe no"
echo "docker-compose e no roteador, em /cursos. O robô faz essa parte"
echo "sozinho, depois desta tela."
