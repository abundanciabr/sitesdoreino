#!/usr/bin/env bash
# =============================================================================
# LIGAR A APPMAX NA PLATAFORMA. O passo do mantenedor.
# Guarda no env da célula pagamentos QUEM é o nosso aplicativo na Appmax e o
# par de credenciais dele, recarrega a célula, e mostra na tela a porta de
# instalação deixando de recusar.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/ligar-a-appmax.sh -o /tmp/appmax.sh && bash /tmp/appmax.sh
#
# ELE PERGUNTA AS CREDENCIAIS, com digitação invisível, e essa é a decisão que
# dá nome ao arquivo. Elas NUNCA vêm como argumento: argumento de linha de
# comando aparece na tela, fica no `~/.bash_history`, é lido por qualquer
# processo pelo `ps aux`, e vai junto no print que o mantenedor manda ao agente
# para provar que funcionou. Foi assim que o segredo do OAuth do Google vazou em
# 24/08/2026 (`armadilhas/090`). Pelo mesmo motivo, aqui o valor também não
# viaja por variável de ambiente de processo filho nem por arquivo temporário:
# ele nasce no `read`, mora numa variável deste shell, e morre com ele.
#
# O QUE ELE ESCREVE em `env/pagamentos.env`, e só isto:
#   APPMAX_INSTALACOES        quem é o nosso aplicativo (montado aqui)
#   APPMAX_AUTH_URL           endereço de autenticação da API
#   APPMAX_API_URL            endereço base da API
#   APPMAX_APP_CLIENT_ID      o par OAuth do aplicativo
#   APPMAX_APP_CLIENT_SECRET
#
# `APPMAX_INSTALACOES` é a variável que `services/pagamentos/config/settings.py`
# lê de verdade, no formato `{"<app_id>":{"alias":"Loja","sites":["<site_id>"]}}`.
# Sem ela, NENHUM app_id é autorizado e a rota de instalação recusa tudo, que é
# o comportamento certo de uma porta de dinheiro sem configuração. O `site_id`
# de dentro dela é o número INTERNO do site no catálogo, não o endereço do site:
# ninguém tem como saber esse número de cabeça, e por isso este arquivo PERGUNTA
# ao catálogo em vez de perguntar a você.
#
# ELE NÃO LIGA COBRANÇA NENHUMA. `APPMAX_CARD_ENABLED_SITES` continua exatamente
# como está, e enquanto ela estiver vazia nenhuma cobrança nova no cartão sai,
# em site nenhum. Ligar um site ali é outra decisão, sua, em outro dia.
#
# IDEMPOTENTE: rodar de novo é seguro e serve para TROCAR a credencial. O env
# antigo vira `.bak-<epoch>` antes de qualquer edição, e só estas cinco linhas
# mudam. Nas perguntas de endereço, Enter mantém o que já está gravado, para que
# trocar só o segredo não obrigue a redigitar o que já estava certo.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/appmax.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/appmax.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Nada escrito na linha, nunca. Não é preciosismo de formato: é a única maneira
# de garantir que a credencial não passou por aqui (`armadilhas/090`).
if [ "$#" -gt 0 ]; then
  parar "este comando não recebe nada escrito na linha, e você escreveu algo. Se era a credencial, NÃO cole aqui: ela apareceria na tela, ficaria no histórico do terminal e qualquer processo da máquina conseguiria lê-la. Rode 'bash /tmp/appmax.sh' sem mais nada, que eu pergunto uma a uma, com a digitação invisível. Nada foi alterado."
fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_PAGAMENTOS="env/pagamentos.env"

# -----------------------------------------------------------------------------
# 1. ONDE. Tudo conferido ANTES de perguntar qualquer coisa.
#    Perguntar primeiro e descobrir depois que falta uma peça faria o mantenedor
#    colar uma credencial à toa, e credencial colada à toa é como uma credencial
#    acaba num lugar errado.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…) Nada foi alterado."
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ. Nada foi alterado."
[ -f "$ENV_PAGAMENTOS" ] || parar "não achei $RAIZ/$ENV_PAGAMENTOS. A célula de pagamentos ainda não foi provisionada nesta máquina: rode antes o infra/provisionamento-vps.sh. Nada foi alterado."
[ -w "$ENV_PAGAMENTOS" ] || parar "não consigo escrever em $RAIZ/$ENV_PAGAMENTOS. Rode como root ou como o dono dos env. Nada foi alterado."
command -v docker >/dev/null 2>&1 || parar "não achei o docker nesta máquina, e é por ele que eu falo com o catálogo e recarrego a célula. Você está na VPS certa? Nada foi alterado."

RODANDO="$(docker compose ps --status running --services 2>/dev/null || true)"
printf '%s\n' "$RODANDO" | grep -qx catalogo \
  || parar "o serviço 'catalogo' não está rodando, e é ele quem sabe o número interno do site. Suba a plataforma (cd $RAIZ && docker compose up -d) e cole a minha linha de novo. Nada foi alterado."
printf '%s\n' "$RODANDO" | grep -qx pagamentos \
  || parar "o serviço 'pagamentos' não está rodando, e é ele quem atende a Appmax. Suba a plataforma (cd $RAIZ && docker compose up -d) e cole a minha linha de novo. Nada foi alterado."

# -----------------------------------------------------------------------------
# 2. QUAL SITE. Perguntado ao CATÁLOGO, que é onde dado de site mora.
#
#    A resposta CRUA primeiro e o filtro depois, em dois passos de propósito:
#    num pipe único, "o catálogo não respondeu" e "o catálogo respondeu que não
#    há site ativo" chegariam aqui como o MESMO erro, e o mantenedor leria "não
#    consegui perguntar" quando o problema é outro (`armadilhas/240`).
# -----------------------------------------------------------------------------
echo "== 1/4: descobrindo o site no catálogo =="
BRUTO="$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}\t{s.name}')" 2>/dev/null)" \
  || parar "não consegui perguntar ao catálogo quais sites existem. O serviço está de pé mas não respondeu: veja 'docker compose logs --tail 50 catalogo'. Nada foi alterado."

SITES="$(printf '%s\n' "$BRUTO" | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}[[:space:]]' || true)"
QUANTOS="$(printf '%s\n' "$SITES" | grep -c . || true)"
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo, e sem site não há a que escola amarrar a instalação da Appmax. Cadastre o site (infra/sites.json, que o deploy converge) e cole a minha linha de novo. Nada foi alterado."

if [ "$QUANTOS" -gt 1 ]; then
  echo "  Achei mais de um site ativo, e eu não escolho por você:"
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r COLUNA_ID COLUNA_HOST COLUNA_NOME; do
    echo "     - $COLUNA_HOST  ($COLUNA_NOME)"
  done
  echo
  printf 'Digite o endereço do site que vende pela Appmax e aperte Enter: '
  read -r ESCOLHIDO
  echo
  ESCOLHIDO="$(printf '%s' "$ESCOLHIDO" | tr -d '[:space:]')"
  LINHA="$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$ESCOLHIDO" '$2==h {print; exit}')"
  [ -n "$LINHA" ] || parar "o endereço '$ESCOLHIDO' não está entre os sites ativos do catálogo. Confira a grafia (sem https:// e sem barra no fim) e cole a minha linha de novo. Nada foi alterado."
else
  LINHA="$(printf '%s\n' "$SITES" | head -1)"
fi

SITE_ID="$(printf '%s' "$LINHA" | cut -f1)"
SITE_HOST="$(printf '%s' "$LINHA" | cut -f2)"
SITE_NOME="$(printf '%s' "$LINHA" | cut -f3)"
[ -n "$SITE_ID" ] && [ -n "$SITE_HOST" ] || parar "o catálogo respondeu num formato que eu não reconheço. Mande esta tela ao agente. Nada foi alterado."

echo "  site .............. $SITE_HOST"
echo "  número interno .... $SITE_ID"
echo

ler_de() {  # chave. Devolve o valor limpo, sem comentário nem espaços em volta.
  grep "^$1=" "$ENV_PAGAMENTOS" 2>/dev/null | head -1 | cut -d= -f2- \
    | tr -d '\r' | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

echo "== estado ANTES =="
if [ -n "$(ler_de APPMAX_INSTALACOES)" ]; then
  echo "  a Appmax .......... JÁ está configurada (vou TROCAR pelo que você digitar)"
else
  echo "  a Appmax .......... não configurada (a porta de instalação recusa tudo)"
fi
echo

# -----------------------------------------------------------------------------
# 3. AS PERGUNTAS. Primeiro o que não é segredo e por isso aparece enquanto se
#    digita (ver o que colou evita a colagem pela metade que ninguém percebe);
#    depois o par de credenciais, invisível.
# -----------------------------------------------------------------------------
echo "== 2/4: as perguntas =="
echo "São seis perguntas: o número do nosso aplicativo, o nome com que a loja"
echo "se apresenta, os dois endereços da API da Appmax, e o par de credenciais."
echo "As quatro primeiras aparecem enquanto você digita, porque não são segredo."
echo "As duas últimas não aparecem."
echo

printf 'Qual o app_id do nosso aplicativo? (só números; Enter usa 1888, o da Meshcraft) '
read -r APP_ID
APP_ID="$(printf '%s' "$APP_ID" | tr -d '[:space:]')"
[ -n "$APP_ID" ] || APP_ID="1888"
case "$APP_ID" in
  *[!0-9]*) parar "o app_id da Appmax é só números, e '$APP_ID' tem outra coisa. Ele é o número da conta, não o código comprido com letras. Nada foi alterado." ;;
esac

printf 'Com que nome a loja deve se apresentar? (Enter usa %s) ' "$SITE_NOME"
read -r ALIAS
ALIAS="$(printf '%s' "$ALIAS" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
[ -n "$ALIAS" ] || ALIAS="$SITE_NOME"
# Nome vazio não é detalhe de apresentação: uma entrada sem alias é DESCARTADA
# por settings.APPMAX_INSTALACOES, e a porta continuaria recusando sem que nada
# na tela explicasse por quê.
[ -n "$ALIAS" ] || parar "o nome da loja ficou vazio, e sem nome a configuração inteira é ignorada e a porta continua recusando tudo. Rode esta linha de novo e escreva o nome da loja. Nada foi alterado."
case "$ALIAS" in
  *[\"\\]*) parar "o nome da loja não pode ter aspas nem barra invertida: esses dois caracteres quebrariam a configuração por dentro e a porta voltaria a recusar tudo. Escreva o nome sem eles. Nada foi alterado." ;;
esac

perguntar_endereco() {  # rótulo, chave no env. Ecoa o valor atual e aceita Enter.
  local atual
  atual="$(ler_de "$2")"
  if [ -n "$atual" ]; then
    printf '%s (Enter mantém %s) ' "$1" "$atual"
  else
    printf '%s ' "$1"
  fi
  read -r RESPOSTA
  RESPOSTA="$(printf '%s' "$RESPOSTA" | tr -d '[:space:]')"
  [ -n "$RESPOSTA" ] || RESPOSTA="$atual"
  case "$RESPOSTA" in
    https://?*) : ;;
    "") parar "você não respondeu, e não há nada gravado para eu manter. Copie o endereço da documentação da Appmax (docs.appmax.com.br, na parte de autenticação) e cole aqui. Nada foi alterado." ;;
    *) parar "'$RESPOSTA' não parece um endereço: ele começa com https:// e vem inteiro, sem barra no fim. Nada foi alterado." ;;
  esac
}

perguntar_endereco 'Endereço de autenticação da API:' APPMAX_AUTH_URL
AUTH_URL="$RESPOSTA"
perguntar_endereco 'Endereço base da API:' APPMAX_API_URL
API_URL="$RESPOSTA"
echo

echo "Agora o par de credenciais do aplicativo. Os dois são segredo, então NADA"
echo "vai aparecer na tela enquanto você cola. Isso é normal."
echo
printf 'Cole o client_id e aperte Enter: '
read -r -s CLIENT_ID
echo   # a quebra de linha que o -s engoliu
printf 'Cole o client_secret e aperte Enter: '
read -r -s SEGREDO
echo
echo

conferir_credencial() {  # valor, nome na tela
  [ -n "$1" ] || parar "você não colou o $2. Nada foi alterado."
  case "$1" in
    *[![:print:]]*) parar "o $2 tem um caractere que não dá para digitar, sinal de que veio junto com formatação de algum editor. Copie de novo, direto do painel da Appmax. Nada foi alterado." ;;
  esac
}

CLIENT_ID="$(printf '%s' "$CLIENT_ID" | tr -d '[:space:]')"
SEGREDO="$(printf '%s' "$SEGREDO" | tr -d '[:space:]')"
conferir_credencial "$CLIENT_ID" "client_id"
conferir_credencial "$SEGREDO" "client_secret"

# -----------------------------------------------------------------------------
# 4. GRAVAR, com cópia do arquivo antes e só as cinco linhas mudando.
#
#    A escrita é feita AQUI DENTRO, sem `sed`, sem `awk` e sem arquivo
#    temporário: o valor nunca vira argumento de outro programa (que o `ps` de
#    qualquer processo leria) nem sobra em disco se este comando morrer no meio.
#    O `printf ... >` também trunca o arquivo NO LUGAR, sem recriá-lo, e por
#    isso dono e permissão continuam os mesmos mesmo rodando como root
#    (`armadilhas/091`).
# -----------------------------------------------------------------------------
echo "== 3/4: gravando e recarregando =="
MARCA="$(date +%s)"
cp -a "$ENV_PAGAMENTOS" "$ENV_PAGAMENTOS.bak-$MARCA" \
  || parar "não consegui guardar a cópia de segurança do env. Nada foi alterado."

gravar() {  # chave, valor
  local chave="$1" valor="$2" linha saida="" achou=0
  while IFS= read -r linha || [ -n "$linha" ]; do
    case "$linha" in
      "$chave="*)
        # A segunda linha da mesma chave some: duas fariam o valor depender da
        # ordem em que alguém lê o arquivo.
        if [ "$achou" -eq 0 ]; then
          saida="$saida$chave=$valor"$'\n'
          achou=1
        fi
        ;;
      *)
        saida="$saida$linha"$'\n'
        ;;
    esac
  done < "$ENV_PAGAMENTOS"
  [ "$achou" -eq 1 ] || saida="$saida$chave=$valor"$'\n'
  printf '%s' "$saida" > "$ENV_PAGAMENTOS" \
    || parar "não consegui escrever em $RAIZ/$ENV_PAGAMENTOS. Há cópia intacta em $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA."
}

gravar APPMAX_INSTALACOES "{\"$APP_ID\":{\"alias\":\"$ALIAS\",\"sites\":[\"$SITE_ID\"]}}"
gravar APPMAX_AUTH_URL "$AUTH_URL"
gravar APPMAX_API_URL "$API_URL"
gravar APPMAX_APP_CLIENT_ID "$CLIENT_ID"
gravar APPMAX_APP_CLIENT_SECRET "$SEGREDO"

echo "  aplicativo ........ $APP_ID, como $ALIAS, vendendo por $SITE_HOST"
echo "  par guardado ...... client_id com ${#CLIENT_ID} caracteres e client_secret com ${#SEGREDO} caracteres (não mostro o conteúdo, de propósito)"
echo "  cópia do env ...... $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA"

# Um container só relê o env dele quando renasce, e `--force-recreate` é o que
# obriga: `up -d` sozinho vê a mesma imagem e a mesma configuração de compose e
# não faz nada, porque mudança DENTRO do env_file não conta como mudança para
# ele. Sem isso as credenciais ficariam no arquivo e fora do processo.
# `--wait` faz este comando devolver a linha só depois de a célula estar
# saudável de novo, e não no instante em que ela começou a subir.
#
# A SAÍDA DE ERRO NÃO VAI PARA O LIXO (`armadilhas/377`): em 06/09/2026 um
# roteiro desta casa recarregou duas células com `>/dev/null 2>&1`, o comando
# falhou, e o texto que teria dito o porquê foi apagado. A página ficou 502 por
# minutos enquanto a tela dizia PRONTO.
#
# JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as células à
# tag :main do compose (RITOS §4). Só `pagamentos`, pelo nome.
SAIDA_UP="$(docker compose up -d --force-recreate --wait --wait-timeout 180 pagamentos 2>&1)"
CODIGO_UP=$?
if [ "$CODIGO_UP" -ne 0 ]; then
  echo "$SAIDA_UP"
  parar "não consegui recarregar a célula de pagamentos, e ela pode ter ficado fora do ar. O env JÁ está gravado e correto, e há cópia do anterior em $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA. NÃO cole as credenciais de novo: rode 'docker compose ps pagamentos' para ver como ela está, e mande esta tela ao agente."
fi
echo "  célula recarregada"
echo

# -----------------------------------------------------------------------------
# 5. A PROVA, na tela. Uma chamada de verdade à porta de instalação, com o
#    app_id que acabou de ser configurado, pelo mesmo endereço público que a
#    Appmax usa. Ela é segura de repetir: a porta devolve sempre o MESMO
#    external_id para o mesmo app_id, e é justamente isso que a Appmax exige.
#    Nada de segredo entra nesta chamada nem sai nesta tela.
# -----------------------------------------------------------------------------
echo "== 4/4: batendo na porta de instalação =="
ROTA="https://$SITE_HOST/api/pagamentos/appmax/instalacao"
echo "  $ROTA"
RESPOSTA_HTTP="$(curl -sS -m 20 -w '\n%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  --data "{\"app_id\":\"$APP_ID\"}" \
  "$ROTA" 2>&1)" \
  || parar "não consegui falar com $ROTA de dentro desta máquina. O env JÁ está gravado e correto, e NÃO é para colar as credenciais de novo. Confira se o site responde (curl -I https://$SITE_HOST) e mande esta tela ao agente."

CODIGO="$(printf '%s\n' "$RESPOSTA_HTTP" | tail -n 1 | tr -d '[:space:]')"
CORPO="$(printf '%s\n' "$RESPOSTA_HTTP" | sed '$d')"
echo "  HTTP $CODIGO"
echo "  $CORPO"
echo

case "$CODIGO" in
  200)
    echo "== PRONTO =="
    echo "A porta que recusava a Appmax passou a aceitar. O 'external_id' aí em"
    echo "cima é o nosso número desta instalação: ele nunca muda, e é o mesmo que"
    echo "a Appmax vai receber quando instalar o aplicativo de verdade."
    echo
    echo "O que fazer agora: volte ao painel da Appmax e instale o aplicativo na"
    echo "sua loja. Se ela pedir o endereço de instalação, é este mesmo:"
    echo "  $ROTA"
    echo
    echo "Lembre: nenhuma cobrança nova no cartão sai enquanto"
    echo "APPMAX_CARD_ENABLED_SITES estiver vazia, e este comando não encostou"
    echo "nela. Ligar a venda no cartão é outra decisão, sua."
    ;;
  *)
    parar "gravei tudo e recarreguei a célula, mas a porta respondeu '$CODIGO' em vez de aceitar. O env JÁ está gravado e NÃO é para colar as credenciais de novo. O caso mais comum é o app_id: confira no painel da Appmax se o número do nosso aplicativo é mesmo $APP_ID e, se não for, rode esta linha outra vez com o número certo. Se for, mande esta tela ao agente."
    ;;
esac
