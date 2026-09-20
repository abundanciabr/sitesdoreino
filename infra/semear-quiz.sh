#!/usr/bin/env bash
# =============================================================================
# SEMEAR O CRIVO — publica na produção o quiz de um site: as perguntas, as
# opções, a pontuação e as faixas de resultado.
#
# POR QUE ELE EXISTE
# ------------------
# A célula `quiz` está de pé em produção desde a Fase D (`infra/docker-compose.yml`
# tem o serviço `quiz` e o worker `quiz-relay`), e nunca houve um único quiz
# publicado: `/quiz/healthz` responde 200 e o endereço do Crivo responde 404.
# Medido em 02/09/2026 e escrito como dívida em `ci/pecas-comuns-em-falta.txt`
# e em `armadilhas/286`. Subir o código de uma célula e POVOAR essa célula são
# dois passos, e o segundo não acontece sozinho: comando de gerência não roda
# no deploy. Toda célula que precisa de conteúdo em produção já tinha o seu
# semeador (caixa, áreas e dúvidas do fórum, economia, boas-vindas); o quiz era
# a única sem, e o `seed_quiz` existia sem nunca ter sido invocado por ninguém.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-quiz.yml`, disparado à mão, com o
#   host do site escolhido na hora. Nenhum terminal envolvido.
#
# Dentro da VPS, se um dia for preciso à mão (o prompt precisa ser `deploy@srv…`
# ou `root@srv…`, nunca `PS C:\>`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-quiz.sh -o /tmp/s.sh && bash /tmp/s.sh meshcraft.top
#
# O HOST É ARGUMENTO PORQUE A PLATAFORMA É MULTISSÍTIO (Lei 9). A produção
# serve meshcraft.top E basileiatoutheou.org, e outros virão. Rodar para um site
# não toca no outro: tudo que este script lê e escreve é filtrado pelo site
# pedido. Sem host não há palpite: o script lista os ativos e PARA.
#
# O NÚMERO DO SITE É O CORAÇÃO DISTO, E POR ISSO ELE É CONFERIDO NOS DOIS SENTIDOS
# ---------------------------------------------------------------------------------
# O quiz tem cadastro LOCAL de Site (`services/quiz/apps/quiz/models.py`) e
# resolve Host→Site sem chamar o catálogo — desvio deliberado, registrado em
# `services/quiz/LICOES.md`. A costura que isso exige é esta: o `id` do Site
# local precisa ser o MESMO uuid que o catálogo usa para aquele host, senão
# `quiz.completado.v1` não correlaciona com leads nem com checkout, e ninguém
# fica sabendo de um lead que existe. Tudo responde 200 e nada avisa.
#
# O `seed_quiz` faz `get_or_create(id=site_id, ...)` e `host` é `unique=True`.
# Duas consequências que este script trata ANTES de semear, em vez de descobrir
# depois:
#   - número certo com host já cadastrado em outro número: o banco levanta
#     IntegrityError e o erro aparece;
#   - host novo com número errado: o banco ACEITA, em silêncio, e cria um Site
#     que nada correlaciona. É esta a falha cara, e é a que o passo 3 impede.
#
# SEGURO DE RODAR DUAS VEZES: o `seed_quiz` é idempotente por construção
# (`get_or_create` no site, no quiz, em cada pergunta, em cada opção e em cada
# faixa). Rodar de novo não duplica nada e não apaga resposta nenhuma.
#
# O BOTÃO DA TELA DE RESULTADO VEM DO CATÁLOGO, NÃO DE UM CAMPO A PREENCHER.
# O PR #1768 dá ao `seed_quiz` um `--destino-do-botao` obrigatório: para onde vai
# quem termina o quiz. Esse destino é a oferta DAQUELE site, e o catálogo já a
# guarda (`Site.default_offer_slug`); o checkout a publica em
# `/checkout/<oferta>/`. Então o passo 2 traz a oferta na mesma consulta que traz
# o número, e o passo 4 monta o destino. Pedir isso de novo a quem dispara seria
# uma segunda verdade, livre para divergir da primeira. Site sem oferta padrão
# não ganha botão chutado: o script para e diz onde cadastrar.
#
# O ENDEREÇO DO QUIZ É MEDIDO, NÃO ESCRITO AQUI. A célula sobe atrás do Traefik
# com `SCRIPT_NAME=/quiz` e o gateway NÃO remove o prefixo (`armadilhas/197`),
# então o endereço público depende do urlconf da célula, que é dela e pode
# mudar sem avisar este script. O passo 6 pergunta ao próprio Django qual é o
# endereço, em vez de repetir de cor um caminho que envelhece.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. As
# únicas escritas são as linhas do quiz no banco da própria célula.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/6 — conferindo se as duas peças estão de pé =="
for SERVICO in catalogo quiz; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo. NADA foi alterado."
  echo "  $SERVICO ...... de pé"
done

echo
echo "== 2/6 — descobrindo o site no catálogo =="
# O catálogo é a fonte do número. Perguntar a ele é o único jeito de o Site
# local do quiz nascer com o mesmo uuid que leads e checkout enxergam.
SITES=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}\t{s.name}\t{s.default_offer_slug}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s') \
  || parar "não consegui perguntar ao catálogo quais sites existem. NADA foi alterado."

QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. Sem site não há a quem amarrar o quiz."

listar_sites() {
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST RESTO; do
    echo "     - $HOST  ($ID)"
  done
}

# Duas portas para o mesmo argumento, e NENHUMA delas costura texto de fora
# dentro do script: o `$1` da linha de colar, e a `HOST_QUIZ` que o pipeline
# entrega pelo `envs:` da ssh-action. `${{ inputs.* }}` dentro de `script:` é
# injeção de comando na VPS (`armadilhas/047`).
HOST_PEDIDO="${1:-${HOST_QUIZ:-}}"

if [ -z "$HOST_PEDIDO" ]; then
  echo "  Os sites ativos no catálogo são:"
  listar_sites
  echo
  echo "  Rode de novo dizendo QUAL, por exemplo:"
  echo "     bash /tmp/s.sh meshcraft.top"
  parar "sem host eu não escolho o site por você: a plataforma é multissítio e o quiz de um site não é o do outro."
fi

LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
if [ -z "$LINHA" ]; then
  echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
  listar_sites
  parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim). NADA foi alterado."
fi

SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
SITE_NOME=$(printf '%s' "$LINHA" | cut -f3)
OFERTA=$(printf '%s' "$LINHA" | cut -f4)
[ -n "$SITE_ID" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site."
[ -n "$SITE_NOME" ] || SITE_NOME="$SITE_HOST"

# Para onde o botão da tela de resultado leva. Não se pergunta a ninguém: a
# oferta é dado DO SITE e mora no catálogo (`Site.default_offer_slug`), na mesma
# consulta que já trouxe o número. O checkout publica a oferta em
# `/checkout/<oferta>/`. Site sem oferta padrão não ganha botão chutado: o passo
# 4 para e diz onde cadastrar.
DESTINO=""
if [ -n "$OFERTA" ]; then
  case "$OFERTA" in
    *[!a-z0-9-]*) parar "a oferta padrão de $SITE_HOST no catálogo ('$OFERTA') tem caractere que um endereço não tem. Corrija o cadastro do site antes. NADA foi alterado." ;;
  esac
  DESTINO="/checkout/$OFERTA/"
fi
# O host volta do catálogo, não do argumento, e ainda assim é conferido antes
# de virar dado de consulta: número e host entram nos comandos por `-e`, nunca
# emendados no corpo de um shell ou de um python.
case "$SITE_HOST" in
  *[!a-z0-9.-]*) parar "o host '$SITE_HOST' tem caractere que um host não tem. Confira o cadastro no catálogo." ;;
esac
echo "  site ...... $SITE_HOST"
echo "  nome ...... $SITE_NOME"
echo "  número .... $SITE_ID"
echo "  oferta .... ${OFERTA:-nenhuma cadastrada}"

echo
echo "== 3/6 — conferindo o cadastro local do quiz contra o catálogo =="
# Os dois sentidos da mesma pergunta. O primeiro pega o quiz que já conhece o
# host por outro número; o segundo pega o número já usado para outro host.
LOCAL=$(docker compose exec -T -e ALVO_ID="$SITE_ID" -e ALVO_HOST="$SITE_HOST" quiz python manage.py shell -c \
  "import os
from apps.quiz.models import Site
por_host = Site.objects.filter(host=os.environ['ALVO_HOST'].lower()).first()
por_id = Site.objects.filter(id=os.environ['ALVO_ID']).first()
print('LOCAL\t' + (por_host.id if por_host else '') + '\t' + (por_id.host if por_id else ''))" 2>&1 | tr -d '\r')
LINHA_LOCAL=$(printf '%s\n' "$LOCAL" | grep -E '^LOCAL' | head -n1 || true)
if [ -z "$LINHA_LOCAL" ]; then
  echo "$LOCAL"
  parar "não consegui ler o cadastro de sites do quiz. A saída acima diz por quê. NADA foi alterado."
fi
LOCAL="$LINHA_LOCAL"

ID_POR_HOST=$(printf '%s' "$LOCAL" | cut -f2)
HOST_POR_ID=$(printf '%s' "$LOCAL" | cut -f3)

if [ -n "$ID_POR_HOST" ] && [ "$ID_POR_HOST" != "$SITE_ID" ]; then
  echo "  o quiz conhece $SITE_HOST pelo número .... $ID_POR_HOST"
  echo "  o catálogo diz que o número é ........... $SITE_ID"
  parar "o quiz já tem um site com este host e com número DIFERENTE do catálogo. Semear assim publicaria um quiz cujos eventos nenhum lead e nenhum checkout correlacionam. Isto é decisão do mantenedor: ou o cadastro local do quiz é corrigido para o número do catálogo, ou o catálogo mudou o número do site e alguém precisa dizer qual dos dois vale. NADA foi alterado."
fi

if [ -n "$HOST_POR_ID" ] && [ "$HOST_POR_ID" != "$SITE_HOST" ]; then
  echo "  o número $SITE_ID já está no quiz apontando para .... $HOST_POR_ID"
  parar "o número que o catálogo dá para $SITE_HOST já está cadastrado no quiz para OUTRO host. Um dos dois cadastros está errado, e escolher qual é decisão do mantenedor. NADA foi alterado."
fi

if [ -n "$ID_POR_HOST" ]; then
  echo "  o quiz já conhece este site, e pelo mesmo número ...... ok"
else
  echo "  o quiz ainda não conhece este site: ele nasce agora, com o número do catálogo"
fi

echo
echo "== 4/6 — conferindo a assinatura do comando seed_quiz =="
# A célula `quiz` é de outro dono e o comando pode ganhar parâmetro sem que
# ninguém avise este script. Então a assinatura é DESCOBERTA aqui, em vez de
# cravada. Um argumento obrigatório que este script não sabe preencher para
# tudo ANTES de o banco receber a primeira linha; um argumento novo que seja
# apenas opcional é dito em voz alta no log, porque ninguém mais vai dizer.
AJUDA=$(docker compose exec -T quiz python manage.py seed_quiz --help 2>&1 | tr -d '\r') \
  || { echo "$AJUDA"; parar "não consegui pedir a ajuda do comando seed_quiz. A saída acima diz por quê. NADA foi alterado."; }

USO=$(printf '%s\n' "$AJUDA" | awk '/^usage:/{lendo=1} lendo && NF==0 {exit} lendo {print}')
[ -n "$USO" ] || { echo "$AJUDA"; parar "a ajuda do seed_quiz não trouxe a linha de uso, e sem ela eu não sei o que o comando exige. NADA foi alterado."; }

# O botão do resultado está sendo criado por outro despacho, em outro PR, e lá
# o `--destino-do-botao` nasce OBRIGATÓRIO. Ele não é detalhe técnico: é para
# onde vai quem termina o quiz, ou seja, a oferta daquele site. Este script não
# escolhe isso — ele recebe, e cobra quando o comando passar a pedir.
ACEITA_DESTINO=0
printf '%s' "$AJUDA" | grep -q -e '--destino-do-botao' && ACEITA_DESTINO=1

CONHECIDOS=" --host --site-id --site-name "
[ "$ACEITA_DESTINO" = "1" ] && CONHECIDOS=" --host --site-id --site-name --destino-do-botao "

# Fora dos colchetes fica o que argparse considera obrigatório.
OBRIGATORIOS=$(printf '%s' "$USO" | tr '\n' ' ' | sed 's/\[[^][]*\]//g' | grep -oE -e '--[a-z0-9-]+' | sort -u)
for FLAG in $OBRIGATORIOS; do
  case "$CONHECIDOS" in
    *" $FLAG "*) ;;
    *) parar "o comando seed_quiz passou a exigir '$FLAG', e este script não sabe o que pôr nele. Quem mudou o comando precisa ensinar o valor a infra/semear-quiz.sh no mesmo PR. NADA foi alterado." ;;
  esac
done
for FLAG in --host --site-id --site-name; do
  printf '%s' "$AJUDA" | grep -q -e "$FLAG" \
    || parar "o comando seed_quiz não aceita mais '$FLAG', e é por ele que o site certo chega ao quiz. Atualize infra/semear-quiz.sh junto com a célula. NADA foi alterado."
done
echo "  o comando aceita --host, --site-id e --site-name ...... ok"
echo "  e não exige nenhum outro argumento ................... ok"

if [ "$ACEITA_DESTINO" = "1" ]; then
  [ -n "$DESTINO" ] || parar "o comando seed_quiz agora planta o botão da tela de resultado, e $SITE_HOST não tem oferta padrão no catálogo. Botão sem destino levaria para lugar nenhum, e adivinhar a oferta de um site não é meu. O QUE FAZER: cadastre a oferta padrão desse site no catálogo (o campo que guarda o slug da oferta) e dispare de novo. NADA foi alterado."
  echo "  o botão de cada faixa vai levar para ...... $DESTINO"
elif [ -n "$DESTINO" ]; then
  echo "  este seed_quiz ainda não planta botão: a oferta $OFERTA fica para a próxima"
fi

# O que o comando aceita e este script deixa no padrão. Hoje é só o `--slug`.
# Argumento novo que seja apenas opcional não para nada, e o silêncio sobre ele
# seria a pior resposta: quem o criou precisa ver que ninguém o preenche.
SOBRANDO=""
for FLAG in $(printf '%s' "$AJUDA" | grep -oE -e '--[a-z0-9-]+' | sort -u); do
  case "$CONHECIDOS --help " in
    *" $FLAG "*) ;;
    *) SOBRANDO="$SOBRANDO $FLAG" ;;
  esac
done
if [ -n "$SOBRANDO" ]; then
  echo "  o comando também aceita, e este script deixa no padrão:$SOBRANDO"
  echo "  (se algum deles for necessário, quem o criou precisa ensinar o valor a infra/semear-quiz.sh)"
fi

echo
echo "== 5/6 — semeando (idempotente: rodar de novo não duplica) =="
# Duas chamadas em vez de montar a linha de comando numa variável: variável
# solta dentro de um comando se parte em espaços, e o destino do botão é texto
# que vem de fora.
if [ "$ACEITA_DESTINO" = "1" ]; then
  SAIDA=$(docker compose exec -T quiz python manage.py seed_quiz \
    --host "$SITE_HOST" --site-id "$SITE_ID" --site-name "$SITE_NOME" \
    --destino-do-botao "$DESTINO" 2>&1) \
    || { echo "$SAIDA"; parar "o comando seed_quiz falhou. A saída acima diz por quê."; }
else
  SAIDA=$(docker compose exec -T quiz python manage.py seed_quiz \
    --host "$SITE_HOST" --site-id "$SITE_ID" --site-name "$SITE_NOME" 2>&1) \
    || { echo "$SAIDA"; parar "o comando seed_quiz falhou. A saída acima diz por quê."; }
fi
echo "$SAIDA"

echo
echo "== 6/6 — conferindo no banco, por fora do comando que semeou =="
# `armadilhas/114`: o log ecoa o script, e ler o eco como execução já enganou
# esta casa. Aqui a prova é contada de novo, por outro caminho, e filtrada
# PELO SITE pedido — é assim que se vê que o site vizinho não foi tocado.
RESUMO=$(docker compose exec -T -e ALVO_ID="$SITE_ID" quiz python manage.py shell -c \
  "import os
from django.urls import reverse
from apps.quiz.models import Quiz, Site
alvo = os.environ['ALVO_ID']
site = Site.objects.filter(id=alvo).first()
print('SITE\t' + (site.host if site else ''))
for q in Quiz.objects.filter(site_id=alvo).order_by('slug'):
    try:
        endereco = reverse('quiz-formulario', args=[q.slug])
    except Exception:
        endereco = ''
    print('QUIZ\t' + q.slug + '\t' + str(q.questions.count()) + '\t' + str(q.bands.count()) + '\t' + endereco)" 2>&1 | tr -d '\r')
if ! printf '%s\n' "$RESUMO" | grep -qE '^SITE'; then
  echo "$RESUMO"
  parar "semeei e não consegui conferir depois. A saída acima diz por quê. Rode de novo: o comando é idempotente e não duplica nada."
fi

HOST_DEPOIS=$(printf '%s\n' "$RESUMO" | grep -E '^SITE' | head -n1 | cut -f2)
[ "$HOST_DEPOIS" = "$SITE_HOST" ] \
  || parar "depois de semear, o site $SITE_ID no quiz aponta para '$HOST_DEPOIS' e não para '$SITE_HOST'. Não publique nada neste estado: mande esta tela ao agente."

QUIZZES=$(printf '%s\n' "$RESUMO" | grep -cE '^QUIZ' || true)
[ "${QUIZZES:-0}" -ge 1 ] \
  || parar "o comando terminou sem erro e não há NENHUM quiz para este site no banco. Ausência de erro não é sucesso."

ENDERECOS=""
while IFS="$(printf '\t')" read -r MARCA SLUG PERGUNTAS FAIXAS ENDERECO; do
  [ "$MARCA" = "QUIZ" ] || continue
  echo "  quiz '$SLUG' ...... $PERGUNTAS pergunta(s), $FAIXAS faixa(s) de resultado"
  [ "${PERGUNTAS:-0}" -ge 1 ] || parar "o quiz '$SLUG' existe e não tem pergunta nenhuma. Quem abrisse a página veria um formulário vazio."
  [ "${FAIXAS:-0}" -ge 1 ] || parar "o quiz '$SLUG' existe e não tem faixa de resultado. Quem respondesse não receberia resultado nenhum."
  [ -n "$ENDERECO" ] || parar "não consegui medir o endereço público do quiz '$SLUG' (a rota 'quiz-formulario' sumiu do urlconf da célula?). Os dados FORAM criados e rodar de novo não duplica nada, mas eu não entrego um endereço que não medi."
  ENDERECOS="$ENDERECOS
  https://$SITE_HOST$ENDERECO"
done <<FIM
$RESUMO
FIM

echo
echo "PRONTO: o Crivo existe em $SITE_HOST e abre nestes endereços:$ENDERECOS"
echo
echo "O outro site da plataforma não foi tocado: tudo que este script leu e"
echo "escreveu foi filtrado pelo número $SITE_ID."
