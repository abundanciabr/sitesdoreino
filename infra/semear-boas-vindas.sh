#!/usr/bin/env bash
# =============================================================================
# SEMEAR A SEQUÊNCIA DE BOAS-VINDAS — as linhas da jornada na produção.
#
# POR QUE ELE EXISTE
# ------------------
# Subir o código de uma célula e POVOAR essa célula são dois passos, e o segundo
# não acontece sozinho: comando de gerência não roda no deploy. Já custou duas
# vezes em dois dias (o fórum em 30/08 e a economia em 31/08, cada um com o seu
# script irmão aqui do lado). Semear é CONTEÚDO, não esquema — por isso NÃO vira
# migração de dados: lá aquilo quebrou 20 testes, porque migração de dados entra
# no banco de todo teste.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-boas-vindas.yml`, disparado à mão.
#   Nenhum terminal envolvido.
#
# O SITE PRECISA SER O MESMO QUE O CADASTRO CARIMBA, E ISSO É MEDIDO
# -------------------------------------------------------------------
# A jornada é achada por `site_id`, e o `site_id` de um cadastro vem do `funil`,
# que o resolve pelo catálogo. Semear com o site errado criaria uma jornada que
# existe no banco e que nenhum cadastro jamais encontra — tudo responde 200, o
# painel mostra a linha, e ninguém nunca recebe nada. É a pior das falhas.
#
# Então o script faz DUAS coisas em vez de supor uma:
#   1. lê `SITE_ID` do contêiner da `gamificacao` (a única célula que o declara,
#      e ele é, por definição do env, "o uuid do site no catálogo");
#   2. se a `identidade` já publicou algum cadastro, COMPARA com o site que
#      aquele evento carimbou de verdade. Divergiu, para.
#
# LIGAR É DECISÃO DO MANTENEDOR. Sem `LIGAR=1` a jornada nasce e fica DESLIGADA:
# ela não inscreve ninguém, e nada é enviado. Semear que ligasse sozinho seria
# começar a escrever para todo mundo que se cadastrar, sem ninguém ter decidido.
#
# SEGURO DE RODAR DUAS VEZES: `semear_boas_vindas` é idempotente
# (`get_or_create` pelo par site+slug) e NÃO reescreve a versão publicada — o
# banco recusaria, porque versão publicada é pedra.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

LIGAR="${LIGAR:-0}"

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/5 — conferindo se a mensageria está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "mensageria" || true)
[ -n "$ESTADO" ] || parar "o serviço 'mensageria' não está rodando. Sem ele não há banco a semear."
echo "  mensageria ....... de pé"

echo
echo "== 2/5 — descobrindo de qual escola é a sequência =="
SITE=$(docker compose exec -T gamificacao printenv SITE_ID 2>/dev/null | tr -d '\r[:space:]')
[ -n "$SITE" ] || parar "não consegui ler SITE_ID do contêiner da gamificação. Sem ele eu criaria uma jornada que nenhum cadastro acha — e isso não dá erro em lugar nenhum."
echo "  site lido do contêiner ...... ${SITE}"

echo
echo "== 3/5 — conferindo contra o site que um cadastro REAL carimba =="
# Mede em vez de supor. Se a identidade nunca publicou nada, não há o que
# comparar, e o script diz isso em voz alta em vez de fingir que conferiu.
SITE_REAL=$(docker compose exec -T identidade python manage.py shell -c \
  "from apps.identidade.models import OutboxEvent as O; e=O.objects.filter(event='identidade.pessoa-cadastrada').order_by('-id').first(); print(e.payload.get('site_id','') if e else '')" 2>/dev/null | tr -d '\r[:space:]')
if [ -z "$SITE_REAL" ]; then
  echo "  a identidade ainda não publicou nenhum cadastro: nada a comparar."
  echo "  (isto NÃO é um erro; é o estado esperado antes do primeiro cadastro)"
else
  echo "  site do último cadastro real ... ${SITE_REAL}"
  [ "$SITE" = "$SITE_REAL" ] || parar "o site da gamificação ($SITE) é DIFERENTE do que o cadastro carimba ($SITE_REAL). Semear com o primeiro criaria uma jornada que nenhum cadastro encontra."
  echo "  os dois batem ...... ok"
fi

echo
echo "== 4/5 — semeando =="
if [ "$LIGAR" = "1" ]; then
  echo "  modo: SEMEAR E LIGAR (novos cadastros passam a entrar na sequência)"
  SAIDA=$(docker compose exec -T mensageria python manage.py semear_boas_vindas --site-id "$SITE" --ligar 2>&1) \
    || { echo "$SAIDA"; parar "o comando semear_boas_vindas falhou. A saída acima diz por quê."; }
else
  echo "  modo: SÓ SEMEAR (a sequência nasce DESLIGADA e não escreve para ninguém)"
  SAIDA=$(docker compose exec -T mensageria python manage.py semear_boas_vindas --site-id "$SITE" 2>&1) \
    || { echo "$SAIDA"; parar "o comando semear_boas_vindas falhou. A saída acima diz por quê."; }
fi
echo "$SAIDA"

echo
echo "== 5/5 — conferindo do lado de fora do comando =="
# Conta por outro caminho, em vez de acreditar no que o próprio comando disse
# ter feito. E conta PELO SITE, que é como o motor pergunta.
QUANTOS=$(docker compose exec -T mensageria python manage.py shell -c \
  "from apps.jornadas.models import Passo; print(Passo.objects.filter(jornada_versao__jornada__site_id='$SITE', jornada_versao__jornada__slug='boas-vindas').count())" 2>/dev/null | tr -d '\r[:space:]')
case "$QUANTOS" in
  ''|*[!0-9]*) parar "não consegui contar os passos depois de semear." ;;
esac
[ "$QUANTOS" -eq 3 ] || parar "esperava 3 passos na sequência de boas-vindas e contei $QUANTOS."
echo "  passos da sequência ...... $QUANTOS"

TEXTOS=$(docker compose exec -T mensageria python manage.py shell -c \
  "from apps.jornadas.models import TextoDoPasso as T; print(T.objects.filter(passo__jornada_versao__jornada__site_id='$SITE').count())" 2>/dev/null | tr -d '\r[:space:]')
case "$TEXTOS" in
  ''|*[!0-9]*) parar "não consegui contar os textos depois de semear." ;;
esac
[ "$TEXTOS" -eq 9 ] || parar "esperava 9 textos (3 passos x 3 idiomas) e contei $TEXTOS."
echo "  textos nos três idiomas .. $TEXTOS"

ATIVA=$(docker compose exec -T mensageria python manage.py shell -c \
  "from apps.jornadas.models import Jornada; j=Jornada.objects.get(site_id='$SITE', slug='boas-vindas'); print('1' if j.ativa else '0')" 2>/dev/null | tr -d '\r[:space:]')
echo "  a sequência está ligada? . $([ "$ATIVA" = "1" ] && echo SIM || echo NAO)"

echo
echo "PRONTO: a sequencia de boas-vindas existe neste site."
if [ "$ATIVA" = "1" ]; then
  echo "Ela esta LIGADA: quem se cadastrar daqui em diante entra nela."
  echo "Ninguem que ja estava cadastrado recebe nada (sem preenchimento retroativo)."
else
  echo "Ela esta DESLIGADA, que e como nasce. Ligar e uma decisao sua: rode este"
  echo "mesmo fluxo marcando a opcao de ligar."
fi
