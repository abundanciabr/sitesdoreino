#!/usr/bin/env bash
FONTE_OPERACAO="${PLATAFORMA_DIR:-/opt/plataforma}/codigo/ferramentas/atual/infra/operacao-aplicacao.sh"
[ -f "$FONTE_OPERACAO" ] || FONTE_OPERACAO="$(dirname "${BASH_SOURCE[0]}")/operacao-aplicacao.sh"
. "$FONTE_OPERACAO"
# =============================================================================
# SEMEAR O CONVITE PARA A COMUNIDADE, DESLIGADO, na produção.
#
# POR QUE ELE EXISTE
# ------------------
# O comando `semear_convite_para_a_comunidade` da mensageria já existe, mas
# comando de gerência não roda no deploy: sem este roteiro, o convite fica no
# código e nunca chega ao banco da produção. Molde: `infra/semear-boas-vindas.sh`.
#
# COMO RODA (não é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-convite-para-a-comunidade.yml`,
#   disparado à mão. Nenhum terminal envolvido.
#
# ESTE ROTEIRO NUNCA LIGA O CONVITE, E NUNCA O DESLIGA
# ----------------------------------------------------
# Decisão do mantenedor em 27/09/2026: "Eu preparo, você liga". O robô põe a
# jornada no banco com `ativa = false`; ligar é gesto dele, na tela
# `/admin/escola/jornadas/`. Por isso aqui não existe `--ligar`, nem variável
# que o acenda. E se ele já tiver ligado, rodar de novo não apaga a escolha dele:
# o comando só cria o que falta.
#
# O SITE PRECISA SER O MESMO QUE A ESCOLA CARIMBA, E ISSO É MEDIDO
# ----------------------------------------------------------------
# A jornada é achada por `site_id`. Semear com o site errado criaria um convite
# que existe no banco e que nenhum aluno jamais recebe, sem erro em lugar nenhum.
# Então o roteiro lê `SITE_ID` do contêiner da `gamificacao` e, se a
# `identidade` já publicou algum cadastro, compara com o site que aquele evento
# carimbou de verdade. Divergiu, para.
#
# SEGURO DE RODAR DUAS VEZES: o comando é idempotente (`get_or_create` pelo par
# site+slug) e não reescreve a versão publicada. O passo 5 prova isso por fora
# do comando: uma jornada, versão 1 com 2 passos e 6 textos, sempre.
#
# SEMPRE SAI COM ZERO (`armadilhas/549`): a `appleboy/ssh-action` com
# `capture_stdout` descarta a saída inteira quando o roteiro remoto falha. O
# veredito mora no texto ("PRONTO:" ou "PAROU POR SEGURANÇA"), e quem o julga é
# o passo de prova do workflow. A única exceção é o bloco das chaves do gateway,
# cópia obrigatória que o guarda de paridade exige com `exit 1`.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy.
# =============================================================================
set -u

SLUG="convite-para-a-comunidade"
PASSOS_ESPERADOS=2
TEXTOS_ESPERADOS=6

NOTA_DO_BANCO="NADA foi alterado."
parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "$NOTA_DO_BANCO"; exit 0; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa?"


[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."

# =============================================================================
# AS CHAVES DO GATEWAY, ANTES DO PRIMEIRO `docker compose`
#
# CÓPIA do contrato que `infra/semear-boas-vindas.sh` e os demais semeadores
# cumprem: a `appleboy/ssh-action` envia o CONTEÚDO de UM arquivo, e
# /opt/plataforma não tem o repositório, então não há `source` possível.
# `infra/docker-compose.yml` exige `ALUNOS_API_TOKEN` e `TOKEN_CATALOGO` na forma
# `${VAR:?mensagem}`, e sem as duas no ambiente TODO `docker compose` reprova.
#
# NENHUM VALOR APARECE NA TELA: o log do run é lido por gente.
#
# Quem impede as cópias de divergirem: ci/tests/test_paridade_das_chaves_do_gateway.py
# =============================================================================
ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. NADA foi alterado: o convite para"
    echo "a Comunidade não foi criado e a mensageria continua como estava."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e dispare este semeador de novo. O valor não se descobre daqui,"
    echo "e este script nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/5: conferindo se a mensageria está de pé =="
ESTADO=$(servicos_rodando 2>/dev/null | grep -Fx "mensageria") || ESTADO=""
[ -n "$ESTADO" ] || parar "o serviço 'mensageria' não está rodando. Sem ele não há banco a semear."
echo "  mensageria ....... de pé"

echo
echo "== 2/5: descobrindo de qual escola é o convite =="
SITE=$(env_servico gamificacao SITE_ID 2>/dev/null | tr -d '\r[:space:]') || SITE=""
[ -n "$SITE" ] || parar "não consegui ler SITE_ID do contêiner da gamificação. Sem ele eu criaria um convite que nenhum aluno recebe, e isso não dá erro em lugar nenhum."
echo "  site lido do contêiner ...... ${SITE}"

echo
echo "== 3/5: conferindo contra o site que um cadastro REAL carimba =="
SITE_REAL=$(comando_servico identidade shell -c \
  "from apps.identidade.models import OutboxEvent as O; e=O.objects.filter(event='identidade.pessoa-cadastrada').order_by('-id').first(); print(e.payload.get('site_id','') if e else '')" 2>/dev/null | tr -d '\r[:space:]') || SITE_REAL=""
if [ -z "$SITE_REAL" ]; then
  echo "  a identidade ainda não publicou nenhum cadastro: nada a comparar."
  echo "  (isto NÃO é um erro; é o estado esperado antes do primeiro cadastro)"
else
  echo "  site do último cadastro real ... ${SITE_REAL}"
  [ "$SITE" = "$SITE_REAL" ] || parar "o site da gamificação ($SITE) é DIFERENTE do que o cadastro carimba ($SITE_REAL). Semear com o primeiro criaria um convite que nenhum aluno recebe."
  echo "  os dois batem ...... ok"
fi

echo
echo "== 4/5: semeando (sem ligar: o convite nasce DESLIGADO) =="
NOTA_DO_BANCO="O comando de semear já rodou. Dispare de novo depois de corrigir: ele não duplica."
if SAIDA=$(comando_servico mensageria semear_convite_para_a_comunidade --site-id "$SITE" 2>&1); then
  echo "$SAIDA"
else
  echo "$SAIDA"
  parar "o comando semear_convite_para_a_comunidade falhou. A saída acima diz por quê."
fi
# O comando diz se CRIOU a jornada agora ou se ela já existia. Só a criada neste
# run tem a obrigação de ter nascido desligada; a que já existia pode ter sido
# ligada na tela, e este fluxo nunca desliga.
case "$SAIDA" in
  *"@$SITE: criada"*) ORIGEM="criada neste run" ;;
  *"@$SITE: ja existia"*) ORIGEM="ja existia" ;;
  *) parar "a saída do comando não diz se a jornada foi criada agora ou se já existia." ;;
esac

echo
echo "== 5/5: conferindo do lado de fora do comando =="
# Conta por outro caminho, pelo site e pelo slug, em vez de acreditar no que o
# comando disse. Mede a versão 1, que é publicada e imutável: se o mantenedor
# publicar uma versão nova na tela, esta contagem continua valendo.
MEDIDA=$(comando_servico mensageria shell -c \
  "from apps.jornadas.models import Jornada, JornadaVersao, Passo, TextoDoPasso as T; q=dict(jornada_versao__jornada__site_id='$SITE', jornada_versao__jornada__slug='$SLUG', jornada_versao__numero=1); j=Jornada.objects.filter(site_id='$SITE', slug='$SLUG'); print(j.count(), JornadaVersao.objects.filter(jornada__in=j).count(), Passo.objects.filter(**q).count(), T.objects.filter(**{'passo__'+k: v for k, v in q.items()}).count(), int(j.filter(ativa=True).exists()))" 2>/dev/null | tr -d '\r') || MEDIDA=""
set -- $MEDIDA
JORNADAS="${1:-}" VERSOES="${2:-}" PASSOS="${3:-}" TEXTOS="${4:-}" ATIVA="${5:-}"
for NUMERO in "$JORNADAS" "$VERSOES" "$PASSOS" "$TEXTOS" "$ATIVA"; do
  case "$NUMERO" in
    ''|*[!0-9]*) parar "não consegui medir o convite no banco depois de semear (resposta: '$MEDIDA')." ;;
  esac
done
[ "$JORNADAS" -eq 1 ] || parar "esperava 1 jornada $SLUG neste site e contei $JORNADAS."
[ "$VERSOES" -ge 1 ] || parar "a jornada $SLUG existe, mas não tem nenhuma versão."
[ "$PASSOS" -eq "$PASSOS_ESPERADOS" ] || parar "esperava $PASSOS_ESPERADOS passos na versão 1 e contei $PASSOS."
[ "$TEXTOS" -eq "$TEXTOS_ESPERADOS" ] || parar "esperava $TEXTOS_ESPERADOS textos ($PASSOS_ESPERADOS passos x 3 idiomas) e contei $TEXTOS."
echo "  jornadas $SLUG .... $JORNADAS"
echo "  versões ........................... $VERSOES"
echo "  passos da versão 1 ................ $PASSOS"
echo "  textos nos três idiomas ........... $TEXTOS"

echo
if [ "$ORIGEM" = "criada neste run" ] && [ "$ATIVA" = "1" ]; then
  parar "a jornada $SLUG foi criada agora e nasceu LIGADA; ela deveria nascer desligada. Desligue em /admin/escola/jornadas/ e confira o comando semear_convite_para_a_comunidade."
fi
echo "PRONTO: o convite para a Comunidade existe neste site."
echo "ORIGEM: $ORIGEM"
if [ "$ATIVA" = "1" ]; then
  echo "ESTADO: LIGADO (na tela /admin/escola/jornadas/)"
else
  echo "ESTADO: DESLIGADO, que é como nasce. Ninguém recebe nada até o mantenedor"
  echo "ligar em /admin/escola/jornadas/."
fi
