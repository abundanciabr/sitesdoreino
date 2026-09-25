#!/usr/bin/env bash
# =============================================================================
# LIGAR A APPMAX NA PLATAFORMA. O passo do mantenedor.
# Guarda no env da célula pagamentos QUEM é o nosso aplicativo na Appmax e o
# par de credenciais dele e prepara o cadastro sandbox para a rota de instalação.
#
# COMO O MANTENEDOR RODA (na VPS, depois da integração deste roteiro):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/ligar-a-appmax.sh -o /tmp/appmax.sh && bash /tmp/appmax.sh
#   bash /tmp/appmax.sh --oauth-merchant valida e grava o par MERCHANT sandbox
#   bash /tmp/appmax.sh --preparar-reinstalacao prepara um novo external_id privado
#
# ELE PERGUNTA AS CREDENCIAIS, com digitação invisível, e essa é a decisão que
# dá nome ao arquivo. Elas NUNCA vêm como argumento: argumento de linha de
# comando aparece na tela, fica no `~/.bash_history`, é lido por qualquer
# processo pelo `ps aux`, e vai junto no print que o mantenedor manda ao agente
# para provar que funcionou. Foi assim que o segredo do OAuth do Google vazou em
# 24/08/2026 (`armadilhas/090`). Pelo mesmo motivo, aqui o valor também não
# viaja por variável de ambiente de processo filho nem por arquivo temporário:
# ele nasce no `read` e mora numa variável deste shell. Na validação MERCHANT,
# o par segue pela entrada padrão do Python, nunca por argumento ou ambiente.
#
# NO MODO DE INSTALAÇÃO, escreve em `env/pagamentos.env`:
#   APPMAX_INSTALACOES        quem é o nosso aplicativo (montado aqui)
#   APPMAX_AUTH_URL           endereço de autenticação sandbox, fixo
#   APPMAX_API_URL            endereço base sandbox, fixo
#   APPMAX_APP_CLIENT_ID      o par OAuth do aplicativo
#   APPMAX_APP_CLIENT_SECRET
# No modo `--oauth-merchant`, escreve somente as duas chaves MERCHANT após
# provar acesso OAuth e leitura de produtos no sandbox.
# `--preparar-reinstalacao` não grava env nem chama a Appmax: sob transação e
# bloqueio da linha existente, troca somente `external_id` para a futura
# instalação consentida. Se a confirmação da operação for ambígua, não rode de
# novo até conferir o estado; cartão e endpoints devem continuar em sandbox.
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
# antigo vira `.bak-<epoch>` antes de qualquer edição. Endereços preexistentes
# fora do sandbox fazem o roteiro parar sem sobrescrever configuração alguma.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/appmax.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/appmax.sh"
  return 1 2>/dev/null || exit 1
fi

set -u
set +a
unset CLIENT_ID SEGREDO OAUTH VALOR TEMP LINHA linha saida valor ALUNOS_API_TOKEN TOKEN_CATALOGO VALOR_GATEWAY

AUTH_SANDBOX="https://auth.sandboxappmax.com.br"
API_SANDBOX="https://api.sandboxappmax.com.br"
MODO="instalacao"
if [ "$#" -eq 1 ]; then
  case "$1" in
    --oauth-merchant) MODO="oauth-merchant" ;;
    --preparar-reinstalacao) MODO="preparar-reinstalacao" ;;
    *) MODO="invalido" ;;
  esac
elif [ "$#" -gt 1 ]; then
  MODO="invalido"
fi

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

# Nada escrito na linha, nunca. Não é preciosismo de formato: é a única maneira
# de garantir que a credencial não passou por aqui (`armadilhas/090`).
if [ "$MODO" = "invalido" ]; then
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

# Compose interpola o arquivo inteiro antes de executar qualquer subcomando.
# Só estes tokens do gateway são necessários para consultar a plataforma; não
# carregue o admin.env inteiro, que também contém segredos não relacionados.
ENV_ADMIN="env/admin.env"
[ -f "$ENV_ADMIN" ] || parar "não achei $RAIZ/$ENV_ADMIN, necessário para o Compose consultar os serviços. Confira a presença de ALUNOS_API_TOKEN e TOKEN_CATALOGO sem compartilhar os valores. Nada foi alterado."
for CHAVE_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_GATEWAY="$(grep -m1 "^$CHAVE_GATEWAY=" "$ENV_ADMIN" | cut -d= -f2-)"
  [ -n "$VALOR_GATEWAY" ] || parar "$CHAVE_GATEWAY está ausente ou vazia em $RAIZ/$ENV_ADMIN, e o Compose precisa dela antes de consultar os serviços. Confira a chave sem compartilhar o valor. Nada foi alterado."
  if [ "$CHAVE_GATEWAY" = ALUNOS_API_TOKEN ]; then ALUNOS_API_TOKEN="$VALOR_GATEWAY"; else TOKEN_CATALOGO="$VALOR_GATEWAY"; fi
done
unset VALOR_GATEWAY CHAVE_GATEWAY

# As atribuições exportam os tokens apenas para o processo Compose, sem deixá-
# los no ambiente herdado pelo Python e pelo curl usados mais adiante.
docker_compose() {
  ALUNOS_API_TOKEN="$ALUNOS_API_TOKEN" TOKEN_CATALOGO="$TOKEN_CATALOGO" docker compose "$@"
}

consultar_servicos_rodando() {
  if ! RODANDO="$(docker_compose ps --services --status running 2>/dev/null)"; then
    parar "não consegui consultar os serviços pelo Compose; isso não prova que estejam parados. Não rode diagnóstico no terminal: o agente deve usar operacoes-vps.yml, primeiro versao-compose e depois estado-servico para o serviço necessário. Não envie env nem valores de tokens. Nada foi alterado."
  fi
}

ler_de() {  # chave. Devolve o valor limpo, sem comentário nem espaços em volta.
  grep "^$1=" "$ENV_PAGAMENTOS" 2>/dev/null | head -1 | cut -d= -f2- \
    | tr -d '\r' | sed 's/[[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//'
}

if awk '
  {
    linha = $0
    sub(/^[[:space:]]*/, "", linha)
    if (linha !~ /^APPMAX_CARD_ENABLED_SITES([[:space:]]*([=:])|[[:space:]]*(#.*)?$)/) next
    quantidade++
    if (linha !~ /[=:]/) { ativo = 1; next }
    sub(/^[^=:]*[=:]/, "", linha)
    sub(/[[:space:]]*#.*/, "", linha)
    gsub(/[[:space:]]/, "", linha)
    if (linha != "") ativo = 1
  }
  END { exit !(ativo || quantidade > 1) }
' "$ENV_PAGAMENTOS"; then
  parar "há sites com cobrança Appmax habilitada. Este roteiro só prepara sandbox e não pode rodar nesse estado. Desative a lista APPMAX_CARD_ENABLED_SITES por um procedimento autorizado antes de continuar. Nada foi alterado."
fi

if [ "$MODO" = "oauth-merchant" ]; then
  [ "$(ler_de APPMAX_AUTH_URL)" = "$AUTH_SANDBOX/oauth2/token" ] \
    || parar "a autenticação não está fixada no sandbox. Rode primeiro 'bash /tmp/appmax.sh' para preparar o aplicativo. Nada foi alterado."
  [ "$(ler_de APPMAX_API_URL)" = "$API_SANDBOX" ] \
    || parar "a API não está fixada no sandbox. Rode primeiro 'bash /tmp/appmax.sh' para preparar o aplicativo. Nada foi alterado."
  command -v python3 >/dev/null 2>&1 || parar "não achei python3 para validar OAuth sem pôr o segredo na linha de comando. Instale python3 e rode de novo. Nada foi alterado."
  consultar_servicos_rodando
  printf '%s\n' "$RODANDO" | grep -qx pagamentos || parar "o serviço pagamentos não aparece na lista de serviços em execução. Nada foi alterado. Não rode diagnóstico no terminal: o agente deve usar estado-servico para pagamentos em operacoes-vps.yml."
  printf 'Cole o client_id do MERCHANT sandbox e aperte Enter: '
  read -r -s CLIENT_ID
  echo
  printf 'Cole o client_secret do MERCHANT sandbox e aperte Enter: '
  read -r -s SEGREDO
  echo
  [ -n "$CLIENT_ID" ] && [ -n "$SEGREDO" ] || parar "faltou uma das credenciais MERCHANT. Conclua a instalação no painel Appmax sandbox e copie o par retornado. Nada foi alterado."
  case "$CLIENT_ID$SEGREDO" in *[![:print:]]*) parar "as credenciais têm caracteres inválidos. Copie novamente o par do painel Appmax sandbox. Nada foi alterado." ;; esac
  command -v curl >/dev/null 2>&1 || parar "não achei curl para falar com OAuth sandbox sem expor as credenciais. Instale curl e rode de novo. Nada foi alterado."
  OAUTH="$(printf '%s\n%s' "$CLIENT_ID" "$SEGREDO" | python3 -c '
import json
import subprocess
import sys
import urllib.parse

client_id, client_secret = sys.stdin.read().splitlines()
body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}).encode()
try:
    result = subprocess.run(["curl", "-sS", "--max-time", "20", "-H", "Content-Type: application/x-www-form-urlencoded", "--data-binary", "@-", "-w", "\n%{http_code}", "https://auth.sandboxappmax.com.br/oauth2/token"], input=body, capture_output=True, timeout=25, check=False)
except Exception:
    print("FALHA_DE_REDE")
    raise SystemExit(0)
if result.returncode != 0:
    print("FALHA_DE_REDE")
    raise SystemExit(0)
try:
    response_body, status = result.stdout.rsplit(b"\n", 1)
    status = status.decode("ascii")
except Exception:
    print("RESPOSTA_INVALIDA")
    raise SystemExit(0)
if status != "200":
    print("HTTP_" + status if status.isdigit() else "RESPOSTA_INVALIDA")
    raise SystemExit(0)
try:
    payload = json.loads(response_body)
except Exception:
    print("RESPOSTA_INVALIDA")
    raise SystemExit(0)
try:
    token = payload["access_token"]
    tipo = payload["token_type"]
except (KeyError, TypeError):
    print("RESPOSTA_INVALIDA")
    raise SystemExit(0)
if not isinstance(token, str) or not token or tipo != "Bearer":
    print("RESPOSTA_INVALIDA")
    raise SystemExit(0)
config = "silent\nshow-error\nmax-time = 20\nurl = \"https://api.sandboxappmax.com.br/v1/products\"\nheader = " + json.dumps("Authorization: Bearer " + token) + "\nwrite-out = \"\\n%{http_code}\"\n"
try:
    result = subprocess.run(["curl", "--config", "-"], input=config.encode(), capture_output=True, timeout=25, check=False)
except Exception:
    print("API_FALHA_DE_REDE")
    raise SystemExit(0)
if result.returncode != 0:
    print("API_FALHA_DE_REDE")
    raise SystemExit(0)
try:
    response_body, status = result.stdout.rsplit(b"\n", 1)
    status = status.decode("ascii")
except Exception:
    print("API_RESPOSTA_INVALIDA")
    raise SystemExit(0)
if status != "200":
    print("API_HTTP_" + status if status.isdigit() else "API_RESPOSTA_INVALIDA")
    raise SystemExit(0)
try:
    products = json.loads(response_body).get("data", {}).get("products")
except Exception:
    products = None
print("OK" if isinstance(products, list) else "API_RESPOSTA_INVALIDA")
')" || parar "não consegui executar a validação OAuth sandbox. Nada foi alterado."
  case "$OAUTH" in
    OK) ;;
    HTTP_401) parar "a Appmax sandbox recusou as credenciais MERCHANT. Confira se copiou o par retornado ao concluir a instalação sandbox. Nada foi alterado." ;;
    HTTP_*) parar "a Appmax sandbox respondeu com erro HTTP ${OAUTH#HTTP_}. Confira o ambiente e tente novamente. Nada foi alterado." ;;
    FALHA_DE_REDE) parar "não consegui alcançar OAuth sandbox. Confira a conexão e tente novamente. Nada foi alterado." ;;
    API_HTTP_401|API_HTTP_404) parar "OAuth respondeu, mas a API sandbox não confirmou acesso aos produtos do merchant. Conclua a instalação Appmax sandbox e use o par MERCHANT retornado. Nenhuma credencial foi gravada." ;;
    API_HTTP_*) parar "o teste de leitura MERCHANT respondeu com erro HTTP ${OAUTH#API_HTTP_}. Confira a instalação sandbox e tente novamente. Nenhuma credencial foi gravada." ;;
    API_FALHA_DE_REDE) parar "OAuth respondeu, mas não consegui alcançar a API sandbox de produtos. Confira a conexão e tente novamente. Nenhuma credencial foi gravada." ;;
    API_RESPOSTA_INVALIDA) parar "OAuth respondeu, mas a API sandbox não retornou a lista esperada de produtos. Confira a instalação sandbox. Nenhuma credencial foi gravada." ;;
    *) parar "OAuth sandbox respondeu sem um token válido. Confira a instalação sandbox antes de tentar de novo. Nada foi alterado." ;;
  esac
  MARCA="$(date +%s)"
  REPETICAO=1
  while [ -e "$ENV_PAGAMENTOS.bak-$MARCA" ]; do REPETICAO=$((REPETICAO + 1)); MARCA="$(date +%s)-$REPETICAO"; done
  cp -a "$ENV_PAGAMENTOS" "$ENV_PAGAMENTOS.bak-$MARCA" || parar "não consegui guardar a cópia do env antes da edição. Nada foi alterado."
  for CHAVE in APPMAX_MERCHANT_CLIENT_ID APPMAX_MERCHANT_CLIENT_SECRET; do
    VALOR="$CLIENT_ID"
    [ "$CHAVE" = APPMAX_MERCHANT_CLIENT_SECRET ] && VALOR="$SEGREDO"
    TEMP=""
    ENCONTRADA=0
    while IFS= read -r LINHA || [ -n "$LINHA" ]; do
      case "$LINHA" in
        "$CHAVE="*) if [ "$ENCONTRADA" -eq 0 ]; then TEMP="$TEMP$CHAVE=$VALOR"$'\n'; ENCONTRADA=1; fi ;;
        *) TEMP="$TEMP$LINHA"$'\n' ;;
      esac
    done < "$ENV_PAGAMENTOS"
    [ "$ENCONTRADA" -eq 1 ] || TEMP="$TEMP$CHAVE=$VALOR"$'\n'
    printf '%s' "$TEMP" > "$ENV_PAGAMENTOS" || parar "não consegui gravar o par MERCHANT. A cópia anterior está em $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA."
  done
  SAIDA_UP="$(docker_compose up -d --force-recreate --wait --wait-timeout 180 pagamentos 2>&1)"
  CODIGO_UP=$?
  if [ "$CODIGO_UP" -ne 0 ]; then
    echo "$SAIDA_UP"
    parar "OAuth sandbox foi validado e as credenciais MERCHANT já estão gravadas. A célula não recarregou; não rode diagnóstico no terminal. O agente deve usar estado-servico para pagamentos em operacoes-vps.yml. A cópia anterior está em $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA."
  fi
  echo "OAuth sandbox e leitura de produtos MERCHANT validados; credenciais gravadas fora do repositório e célula pagamentos recarregada. O token não foi exibido nem armazenado."
  exit 0
fi

if [ "$MODO" = "preparar-reinstalacao" ]; then
  [ "$(ler_de APPMAX_AUTH_URL)" = "$AUTH_SANDBOX/oauth2/token" ] \
    || parar "a autenticação não está fixada no sandbox. Nada foi alterado."
  [ "$(ler_de APPMAX_API_URL)" = "$API_SANDBOX" ] \
    || parar "a API não está fixada no sandbox. Nada foi alterado."
  consultar_servicos_rodando
  printf '%s\n' "$RODANDO" | grep -qx catalogo \
    || parar "o catálogo não está em execução. Nada foi alterado. O agente deve usar estado-servico para catalogo em operacoes-vps.yml."
  printf '%s\n' "$RODANDO" | grep -qx pagamentos \
    || parar "pagamentos não está em execução. Nada foi alterado. O agente deve usar estado-servico para pagamentos em operacoes-vps.yml."

  SITES_ATIVOS="$(docker_compose exec -T catalogo python manage.py shell -c \
    "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(s.id)" 2>/dev/null)" \
    || parar "não consegui confirmar os sites ativos no catálogo; nenhuma rotação foi solicitada. O agente deve medir catalogo com estado-servico em operacoes-vps.yml e corrigir por PR."
  SITES_ATIVOS="$(printf '%s\n' "$SITES_ATIVOS" | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}$' || true)"
  [ -n "$SITES_ATIVOS" ] \
    || parar "o catálogo não confirmou site ativo algum. Nada foi alterado."

  CODIGO_ROTACAO="$(cat <<'PYTHON'
import os
import sys
import uuid
from django.conf import settings
from django.db import transaction
from pagamentos.core.models import InstalacaoAppmax

sites_ativos = {linha.strip() for linha in sys.stdin if linha.strip()}
configuracoes = settings.APPMAX_INSTALACOES
if not isinstance(configuracoes, dict) or len(configuracoes) != 1: print("CONFIGURACAO_AMBIGUA"); raise SystemExit(20)
app_id, configuracao = next(iter(configuracoes.items()))
alias = configuracao.get("alias") if isinstance(configuracao, dict) else None
sites = configuracao.get("sites") if isinstance(configuracao, dict) else None
if not isinstance(alias, str) or not alias.strip() or not isinstance(sites, list) or not sites: print("SITE_NAO_AUTORIZADO"); raise SystemExit(21)
sites = [str(site) for site in sites]
if len(set(sites)) != len(sites) or not set(sites).issubset(sites_ativos): print("SITE_NAO_AUTORIZADO"); raise SystemExit(21)

with transaction.atomic():
    instalacoes = list(InstalacaoAppmax.objects.select_for_update().filter(app_id=app_id))
    if len(instalacoes) != 1: print("INSTALACAO_AUSENTE_OU_AMBIGUA"); raise SystemExit(22)
    instalacao = instalacoes[0]
    if instalacao.alias != alias or not isinstance(instalacao.platform_site_ids, list) or len(instalacao.platform_site_ids) != len(sites) or set(instalacao.platform_site_ids) != set(sites): print("SITE_NAO_AUTORIZADO"); raise SystemExit(21)
    if settings.APPMAX_AUTH_URL != "https://auth.sandboxappmax.com.br/oauth2/token": print("AUTH_FORA_SANDBOX"); raise SystemExit(23)
    if settings.APPMAX_API_URL != "https://api.sandboxappmax.com.br": print("API_FORA_SANDBOX"); raise SystemExit(24)
    if os.environ.get("APPMAX_CARD_ENABLED_SITES", "").strip() or getattr(settings, "APPMAX_CARD_ENABLED_SITES", ()): print("CARTAO_ATIVO"); raise SystemExit(25)
    instalacao.external_id = uuid.uuid4()
    instalacao.save(update_fields=["external_id"])
print("ROTACAO_SANDBOX_OK")
PYTHON
  )"
  ROTACAO_SAIDA=""
  if ROTACAO_SAIDA="$(printf '%s\n' "$SITES_ATIVOS" | docker_compose exec -T pagamentos python manage.py shell -c "$CODIGO_ROTACAO" 2>/dev/null)"; then
    [ "$ROTACAO_SAIDA" = "ROTACAO_SANDBOX_OK" ] \
      || parar "a consulta privada não confirmou a rotação. Não execute novamente; mantenha o cartão desligado e peça conferência do estado antes de nova tentativa."
  else
    case "$ROTACAO_SAIDA" in
      CONFIGURACAO_AMBIGUA) parar "há mais de uma configuração Appmax e não escolhi uma loja. Nada foi alterado." ;;
      SITE_NAO_AUTORIZADO) parar "a instalação existente não corresponde a um site ativo autorizado. Nada foi alterado." ;;
      INSTALACAO_AUSENTE_OU_AMBIGUA) parar "não encontrei uma instalação existente única. Nada foi alterado." ;;
      AUTH_FORA_SANDBOX) parar "a autenticação do processo pagamentos não está fixada no sandbox. Nada foi alterado." ;;
      API_FORA_SANDBOX) parar "a API do processo pagamentos não está fixada no sandbox. Nada foi alterado." ;;
      CARTAO_ATIVO) parar "há sites com cobrança Appmax habilitada no processo pagamentos. Nada foi alterado." ;;
      *) parar "não consegui confirmar se o identificador foi trocado. Não execute novamente; mantenha o cartão desligado e peça conferência do estado antes de nova tentativa." ;;
    esac
  fi
  echo "preparação de reinstalação sandbox concluída; finalize consentimento e OAuth MERCHANT; cartão permanece desligado"
  exit 0
fi

AUTH_ATUAL="$(ler_de APPMAX_AUTH_URL)"
API_ATUAL="$(ler_de APPMAX_API_URL)"
[ -z "$AUTH_ATUAL" ] || [ "$AUTH_ATUAL" = "$AUTH_SANDBOX/oauth2/token" ] \
  || parar "o env já aponta a Appmax para outro endereço de autenticação. Este roteiro não substitui configuração existente. Nada foi alterado."
[ -z "$API_ATUAL" ] || [ "$API_ATUAL" = "$API_SANDBOX" ] \
  || parar "o env já aponta a Appmax para outra API. Este roteiro não substitui configuração existente. Nada foi alterado."

consultar_servicos_rodando
printf '%s\n' "$RODANDO" | grep -qx catalogo \
  || parar "o serviço 'catalogo' não aparece na lista de serviços em execução, e é ele quem sabe o número interno do site. Nada foi alterado. O agente deve usar estado-servico para catalogo em operacoes-vps.yml."
printf '%s\n' "$RODANDO" | grep -qx pagamentos \
  || parar "o serviço 'pagamentos' não aparece na lista de serviços em execução, e é ele quem atende a Appmax. Nada foi alterado. O agente deve usar estado-servico para pagamentos em operacoes-vps.yml."

# -----------------------------------------------------------------------------
# 2. QUAL SITE. Perguntado ao CATÁLOGO, que é onde dado de site mora.
#
#    A resposta CRUA primeiro e o filtro depois, em dois passos de propósito:
#    num pipe único, "o catálogo não respondeu" e "o catálogo respondeu que não
#    há site ativo" chegariam aqui como o MESMO erro, e o mantenedor leria "não
#    consegui perguntar" quando o problema é outro (`armadilhas/240`).
# -----------------------------------------------------------------------------
echo "== 1/4: descobrindo o site no catálogo =="
BRUTO="$(docker_compose exec -T catalogo python manage.py shell -c \
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
echo "São quatro perguntas: o número do nosso aplicativo, o nome da loja e o par"
echo "de credenciais do APP. Os endereços ficam fixos no sandbox."
echo "As duas credenciais não aparecem enquanto você digita."
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
# 4. GRAVAR, com cópia do arquivo antes e só as chaves deste modo mudando.
#
#    A escrita é feita AQUI DENTRO, sem `sed`, sem `awk` e sem arquivo
#    temporário: o valor nunca vira argumento de outro programa (que o `ps` de
#    qualquer processo leria) nem sobra em disco se este comando morrer no meio.
#    O `printf ... >` também trunca o arquivo NO LUGAR, sem recriá-lo, e por
#    isso dono e permissão continuam os mesmos mesmo rodando como root
#    (`armadilhas/091`).
# -----------------------------------------------------------------------------
echo "== 3/4: gravando e recarregando =="
# A marca é o epoch em SEGUNDOS, e duas trocas de credencial dentro do mesmo
# segundo dariam o mesmo nome: a segunda cópia sobrescreveria a primeira e o env
# anterior sumiria justamente na hora em que ele mais importa, que é a de
# desfazer uma troca errada. O sufixo só aparece quando a colisão acontece, para
# que o caso normal continue sendo `.bak-<epoch>` puro.
MARCA="$(date +%s)"
REPETICAO=1
while [ -e "$ENV_PAGAMENTOS.bak-$MARCA" ]; do
  REPETICAO=$((REPETICAO + 1))
  MARCA="$(date +%s)-$REPETICAO"
done
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
gravar APPMAX_AUTH_URL "$AUTH_SANDBOX/oauth2/token"
gravar APPMAX_API_URL "$API_SANDBOX"
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
SAIDA_UP="$(docker_compose up -d --force-recreate --wait --wait-timeout 180 pagamentos 2>&1)"
CODIGO_UP=$?
if [ "$CODIGO_UP" -ne 0 ]; then
  echo "$SAIDA_UP"
  parar "não consegui recarregar a célula de pagamentos, e ela pode ter ficado fora do ar. O env JÁ está gravado e correto, e há cópia do anterior em $RAIZ/$ENV_PAGAMENTOS.bak-$MARCA. NÃO cole as credenciais de novo nem rode diagnóstico no terminal: o agente deve usar estado-servico para pagamentos em operacoes-vps.yml."
fi
echo "  célula recarregada"
echo

# -----------------------------------------------------------------------------
# 5. Nenhuma chamada pública é feita aqui. A Appmax envia o health check à URL
#    de instalação durante o fluxo real. Um HTTP 200 nessa etapa não valida
#    OAuth MERCHANT; essa validação é um comando separado após a instalação.
# -----------------------------------------------------------------------------
ROTA="https://$SITE_HOST/api/pagamentos/appmax/instalacao"
echo "== CONFIGURAÇÃO DE INSTALAÇÃO PREPARADA =="
echo "App $APP_ID associado a $SITE_HOST. Esta execução não chamou a rota pública."
echo "A Appmax fará o health check ao concluir a instalação sandbox: $ROTA"
echo "HTTP 200 nessa etapa não comprova OAuth MERCHANT. Depois da instalação, rode:"
echo "  bash /tmp/appmax.sh --oauth-merchant"
echo "Esse comando valida o par MERCHANT no OAuth sandbox antes de guardá-lo."
