#!/usr/bin/env bash
# =============================================================================
# SEMEAR EXPERIMENTO: liga ou desliga, na produção, o A/A técnico da página de
# oferta de um site, pela mesma porta da tela da área administrativa.
#
# POR QUE ELE EXISTE
# ------------------
# O ensaio do sistema de experimentos precisa de um A/A ATIVO no espaço
# `cubo.headline` da página de oferta: as duas metades das visitas veem o mesmo
# título, e o que se mede é o sorteio, a exposição e a contagem. Até aqui, só a
# tela `/admin/paginas/experimentos/` criava e iniciava um experimento, e ela
# exige alguém logado. O mantenedor decidiu em 27/09/2026 que o robô liga e
# desliga esse A/A sem navegador e sem ele.
#
# O QUE ELE RODA: `manage.py semear_experimento` dentro do contêiner `admin`.
# O comando chama as mesmas funções da tela (criar em rascunho, iniciar,
# decidir com `encerrar`), com as mesmas recusas e a mesma auditoria, assinada
# pelo semeador. Ele só toca o experimento que tem a assinatura do A/A; outro
# experimento ativo na página faz o comando parar sem tocar em nada.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-experimento.yml`, disparado à mão,
#   com o host e a ação escolhidos na hora. Nenhum terminal envolvido.
#
# Dentro da VPS, se um dia for preciso à mão (o prompt precisa ser `deploy@srv…`
# ou `root@srv…`, nunca `PS C:\>`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-experimento.sh -o /tmp/s.sh && bash /tmp/s.sh meshcraft.top iniciar-aa
#
# SEGURO DE RODAR DUAS VEZES: A/A já no ar não ganha irmão, A/A em rascunho é
# iniciado em vez de nascer outro, e encerrar sem A/A no ar não muda nada.
#
# POR QUE AS PARADAS DAQUI SAEM COM 0 (`armadilhas/549`): a `appleboy/ssh-action`
# com `capture_stdout` descarta a saída inteira quando o roteiro sai diferente
# de zero, e o motivo da parada é justamente o que precisa chegar ao log. A
# parada imprime "PAROU POR SEGURANÇA" e o workflow reprova por ela. A exceção é
# o bloco das chaves do gateway, cujo `exit 1` é contrato guardado por
# `ci/tests/test_paridade_das_chaves_do_gateway.py`.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita é o experimento no catálogo, pela API, e a linha de auditoria
# no banco da admin.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 0; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."

# =============================================================================
# AS CHAVES DO GATEWAY, ANTES DO PRIMEIRO `docker compose`
#
# Este bloco é CÓPIA do contrato que `infra/deploy-celula-na-vps.sh` e os
# outros semeadores já cumprem, e a cópia é obrigatória: a
# `appleboy/ssh-action` envia o CONTEÚDO de UM arquivo, e /opt/plataforma não
# tem o repositório. Sem as duas chaves no ambiente, TODO `docker compose`
# nesta pasta reprova na interpolação, mesmo com a plataforma inteira no ar.
#
# NENHUM VALOR APARECE NA TELA: o log do run é lido por gente, e segredo nele é
# incidente. Este é o único ponto do script que abre um `env/`.
#
# Quem impede as cópias de divergirem:
# ci/tests/test_paridade_das_chaves_do_gateway.py
# =============================================================================
ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. NADA foi alterado: nenhum"
    echo "experimento foi criado, iniciado ou encerrado."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e dispare o semeador de novo. O valor não se descobre daqui, e"
    echo "este script nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

RECADO_DO_COMPOSE=$(docker compose ps 2>&1 >/dev/null) \
  || parar "não consegui falar com o Docker Compose em $RAIZ. O Docker respondeu:

$RECADO_DO_COMPOSE

O QUE FAZER: rode 'docker compose ps' nesta pasta e leia a linha acima. Se ela
falar em 'required variable ... is missing a value', falta uma chave em
$ENV_DO_ADMIN. Se falar em daemon ou socket, o Docker não está de pé. NADA foi
alterado."

echo "== 1/3: conferindo o pedido e as duas peças =="
# Duas portas para os mesmos argumentos, e NENHUMA costura texto de fora dentro
# do script: `$1` e `$2` da linha de colar, ou `HOST_EXPERIMENTO` e
# `ACAO_EXPERIMENTO`, que o pipeline entrega pelo `envs:` da ssh-action.
# `${{ inputs.* }}` dentro de `script:` é injeção de comando na VPS
# (`armadilhas/047`).
HOST_PEDIDO="${1:-${HOST_EXPERIMENTO:-}}"
ACAO_PEDIDA="${2:-${ACAO_EXPERIMENTO:-}}"

case "$ACAO_PEDIDA" in
  iniciar-aa|encerrar) ;;
  *) parar "a ação '$ACAO_PEDIDA' não existe. Use iniciar-aa (liga o A/A) ou encerrar (desliga o A/A). NADA foi alterado." ;;
esac
case "$HOST_PEDIDO" in
  *[!a-z0-9.-]*) parar "o host '$HOST_PEDIDO' tem caractere que um host não tem. Escreva só o domínio, sem https:// e sem barra, por exemplo meshcraft.top. NADA foi alterado." ;;
esac

for SERVICO in catalogo admin; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo. NADA foi alterado."
  echo "  $SERVICO ...... de pé"
done

if [ -z "$HOST_PEDIDO" ]; then
  echo "  Os sites ativos no catálogo são:"
  docker compose exec -T catalogo python manage.py shell -c \
    "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print('     - ' + s.host)" 2>&1 | tr -d '\r'
  parar "sem host eu não escolho o site por você: a plataforma é multissítio e o experimento de um site não é o do outro. Rode de novo dizendo qual, por exemplo: bash /tmp/s.sh meshcraft.top $ACAO_PEDIDA"
fi
echo "  site ...... $HOST_PEDIDO"
echo "  ação ...... $ACAO_PEDIDA"

echo
echo "== 2/3: rodando o comando da área administrativa =="
SAIDA=$(docker compose exec -T admin python manage.py semear_experimento \
  --host "$HOST_PEDIDO" --acao "$ACAO_PEDIDA" 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_experimento parou. A saída acima diz o que houve e o que fazer."; }
SAIDA=$(printf '%s\n' "$SAIDA" | tr -d '\r')
echo "$SAIDA"

echo
echo "== 3/3: conferindo a linha de conclusão =="
# A PROVA, e não o eco (`armadilhas/114`). A linha de conclusão vem do PYTHON,
# e ele só a imprime depois de reler o experimento no catálogo por uma chamada
# separada da que o mudou: estado, número de variantes e igualdade dos textos.
printf '%s\n' "$SAIDA" | grep -q '^PRONTO: ' \
  || parar "o comando terminou sem a linha de conclusão, e ausência de erro não é sucesso. Não posso afirmar que o A/A está como foi pedido."
echo "  a linha de conclusão veio do comando, depois da releitura no catálogo."
