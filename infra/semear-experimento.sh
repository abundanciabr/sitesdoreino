#!/usr/bin/env bash
. "$(dirname "${BASH_SOURCE[0]}")/operacao-aplicacao.sh"
# =============================================================================
# SEMEAR EXPERIMENTO: liga, desliga ou mede, na produção, o A/A técnico da
# página de oferta de meshcraft.top, pela mesma porta das telas da área
# administrativa.
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
# O comando chama as mesmas funções das telas (criar em rascunho, iniciar,
# decidir com `encerrar`, contar como a tela de resultado), com as mesmas
# recusas e a mesma auditoria, assinada pelo semeador. Ele só toca o
# experimento que tem a assinatura do A/A; outro experimento ativo na página
# faz o comando parar sem tocar em nada. `medir` só lê a contagem por braço.
#
# UM SITE SÓ: meshcraft.top. A área administrativa só tem rota nesse domínio
# (`infra/traefik/dynamic/plataforma.yml`) e basileiatoutheou.org está congelado
# (`docs/decisoes/DECISAO-foco-em-meshcraft.md`). Por isso o site não é
# argumento, e um host passado no lugar da ação é recusado dizendo por quê.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-experimento.yml`, disparado à mão,
#   com a ação escolhida na hora. Nenhum terminal envolvido.
#
# Dentro da VPS, se um dia for preciso à mão (o prompt precisa ser `deploy@srv…`
# ou `root@srv…`, nunca `PS C:\>`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-experimento.sh -o /tmp/s.sh && bash /tmp/s.sh iniciar-aa
#
# SEGURO DE RODAR DUAS VEZES: A/A já no ar não ganha irmão, A/A em rascunho é
# iniciado em vez de nascer outro, encerrar sem A/A no ar não muda nada, e
# medir nunca muda nada.
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

# O pedido é conferido antes de tocar em qualquer coisa. `$1` da linha de colar,
# ou `ACAO_EXPERIMENTO`, que o pipeline entrega pelo `envs:` da ssh-action.
# `${{ inputs.* }}` dentro de `script:` é injeção de comando na VPS
# (`armadilhas/047`), e por isso nenhum texto de fora é costurado aqui dentro.
ACAO_PEDIDA="${1:-${ACAO_EXPERIMENTO:-}}"
case "$ACAO_PEDIDA" in
  iniciar-aa|encerrar|medir) ;;
  *.*) parar "o semeador não recebe o site ('$ACAO_PEDIDA'). Ele só serve meshcraft.top, o único domínio com a área administrativa no ar, e basileiatoutheou.org está congelado. Rode só com a ação, por exemplo: bash /tmp/s.sh iniciar-aa. NADA foi alterado." ;;
  *) parar "a ação '$ACAO_PEDIDA' não existe. Use iniciar-aa (liga o A/A), encerrar (desliga o A/A) ou medir (lê a contagem do A/A). NADA foi alterado." ;;
esac

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"

# Exclusao comum no receptor; o descritor herdado precisa apontar ao mesmo inode.
TRAVA_PUBLICACAO="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux na VPS antes de publicar." >&2; exit 1; }
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: nao criei a trava comum; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: nao li a trava comum; o dono deve liberar leitura sem remover o arquivo." >&2; exit 1; }
fi
flock --exclusive 8 || { echo "ERRO: nao obtive a trava comum; confira o mutador em andamento antes de repetir." >&2; exit 1; }
unset TRAVA_PUBLICACAO

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

echo "== 1/3: conferindo as duas peças =="
for SERVICO in catalogo admin; do
  ESTADO=$(servicos_rodando 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo. NADA foi alterado."
  echo "  $SERVICO ...... de pé"
done

echo "  site ...... meshcraft.top"
echo "  ação ...... $ACAO_PEDIDA"

echo
echo "== 2/3: rodando o comando da área administrativa =="
SAIDA=$(comando_servico admin semear_experimento \
  --acao "$ACAO_PEDIDA" 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_experimento parou. A saída acima diz o que houve e o que fazer."; }
SAIDA=$(printf '%s\n' "$SAIDA" | tr -d '\r')
echo "$SAIDA"

echo
echo "== 3/3: conferindo a linha de conclusão =="
# A PROVA, e não o eco (`armadilhas/114`). A linha de conclusão vem do PYTHON.
# Ao ligar e desligar, ele só a imprime depois de reler o experimento no
# catálogo por uma chamada separada da que o mudou (estado, decisão, variantes,
# textos); ao medir, depois de a medição responder dentro do combinado.
printf '%s\n' "$SAIDA" | grep -q '^PRONTO: ' \
  || parar "o comando terminou sem a linha de conclusão, e ausência de erro não é sucesso. Não posso afirmar que o A/A está como foi pedido."
echo "  a linha de conclusão veio do comando, depois da releitura ou da medição."
