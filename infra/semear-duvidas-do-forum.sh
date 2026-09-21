#!/usr/bin/env bash
# =============================================================================
# SEMEAR AS DÚVIDAS DA ESCOLA NO FÓRUM — para ele não abrir deserto.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-duvidas-do-forum.yml`, disparado à
#   mão DEPOIS de o mantenedor aprovar o conteúdo. Nenhum terminal envolvido.
#
# E SE PRECISAR RODAR À MÃO, dentro da VPS (uma linha só, sem argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-duvidas-do-forum.sh -o /tmp/d.sh && bash /tmp/d.sh
#
#   O prompt tem de estar como `deploy@srv…` ou `root@srv…`. Se começar com
#   `PS C:\>`, você está no PC e este script não é para lá.
#
# A ORDEM IMPORTA: as ÁREAS primeiro (`semear-areas-do-forum.sh`), as dúvidas
# depois. O comando de conteúdo não cria área nenhuma, e para por segurança se
# faltar alguma.
#
# SEGURO DE RODAR DUAS VEZES: `semear_duvidas` é idempotente pela dupla
# (área, título) e NÃO atualiza o que já existe. Se o mantenedor reescrever uma
# resposta com as palavras dele, rodar de novo não desfaz.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita são os tópicos e as mensagens da escola no banco do fórum.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."

# =============================================================================
# AS CHAVES DO GATEWAY, ANTES DO PRIMEIRO `docker compose`
#
# Este bloco é CÓPIA do contrato que `infra/deploy-celula-na-vps.sh`,
# `infra/reverter-celula-na-vps.sh` e `infra/semear-quiz.sh` já cumprem, e a
# cópia é obrigatória, não preguiça: a `appleboy/ssh-action` envia o CONTEÚDO de
# UM arquivo, e /opt/plataforma não tem o repositório. Um trecho compartilhado
# por `source` não existiria na VPS.
#
# POR QUE ELE FALTAVA AQUI, medido em 20/09/2026: `infra/docker-compose.yml`
# exige `ALUNOS_API_TOKEN` e `TOKEN_CATALOGO` na forma `${VAR:?mensagem}` desde
# 15/09 (`67ccf0ed`). A interpolação do Compose roda antes de qualquer subcomando
# e sobre o arquivo inteiro, então sem as duas no ambiente TODO `docker compose`
# nesta pasta reprova, mesmo com a plataforma inteira no ar. Os dois disparos do
# `semear-quiz` (runs 35479761568 e 35479784690) morreram em três segundos na
# linha logo abaixo deste bloco, enquanto `meshcraft.top` respondia 200.
#
# NENHUM VALOR APARECE NA TELA: o log do run é lido por gente, e segredo nele é
# incidente. Este é o único ponto do script que abre um `env/`.
#
# Quem impede as cópias de divergirem, e quem obriga um semeador NOVO a nascer
# com este bloco: ci/tests/test_paridade_das_chaves_do_gateway.py
# =============================================================================
ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. NADA foi alterado: nenhum"
    echo "tópico e nenhuma mensagem foram criados, e o fórum continua como estava."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e dispare este semeador de novo. O valor não se descobre daqui,"
    echo "e este script nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se o fórum está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "forum" || true)
[ -n "$ESTADO" ] || parar "o serviço 'forum' não está rodando. Sem ele não há banco a semear."
echo "  forum ...... de pé"

echo
echo "== 2/4 — conferindo se a imagem já sabe publicar em nome da escola =="
# Fail-closed contra a ordem errada: se o deploy que traz a migração ainda não
# passou, a coluna não existe e o comando morreria com erro de SQL cru. Aqui a
# recusa diz o que fazer, em português.
SABE=$(docker compose exec -T forum python manage.py shell -c \
  "from apps.forum.models import Topico; print(Topico.objects.filter(publicado_pela_escola=True).count())" 2>&1)
case "$SABE" in
  ''|*[!0-9]*) echo "$SABE"; parar "esta imagem do fórum ainda não tem a autoria da escola. Espere o deploy da célula 'forum' ficar verde e rode de novo." ;;
esac
echo "  autoria da escola ...... disponível (tópicos da escola hoje: $SABE)"

echo
echo "== 3/4 — publicando as dúvidas =="
# `-T` porque não há terminal do outro lado (o pipeline não aloca TTY).
SAIDA=$(docker compose exec -T forum python manage.py semear_duvidas 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_duvidas falhou. A saída acima diz por quê."; }
echo "$SAIDA"

# A PROVA, e não o eco. `armadilhas/114`: o log da ssh-action ecoa o script
# inteiro, então a frase que comprova execução não pode ser uma que também
# apareça aqui no corpo. Esta vem do PYTHON, do fim do caminho feliz dele.
printf '%s' "$SAIDA" | grep -q 'SEMEADURA DAS DUVIDAS OK' \
  || parar "o comando rodou mas não imprimiu a linha de conclusão — não posso afirmar que publicou."

echo
echo "== 4/4 — conferindo do lado de fora do comando =="
# Conta de novo, por outro caminho, em vez de confiar no que o próprio comando
# disse ter feito. E confere a REGRA DURA junto: nenhuma mensagem semeada pode
# ter autor de pessoa. Contagem zero na primeira, ou qualquer número na segunda,
# é motivo de parada.
QUANTOS=$(docker compose exec -T forum python manage.py shell -c \
  "from apps.forum.models import Topico; print(Topico.objects.filter(publicado_pela_escola=True).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$QUANTOS" in
  ''|*[!0-9]*) parar "não consegui contar os tópicos da escola depois de publicar." ;;
esac
[ "$QUANTOS" -ge 8 ] || parar "esperava ao menos 8 tópicos da escola e contei $QUANTOS."
echo "  tópicos da escola no banco ...... $QUANTOS"

FINGINDO=$(docker compose exec -T forum python manage.py shell -c \
  "from apps.forum.models import Mensagem; print(Mensagem.objects.filter(publicado_pela_escola=True, autor__isnull=False).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$FINGINDO" in
  ''|*[!0-9]*) parar "não consegui conferir se alguma mensagem da escola tem autor de pessoa." ;;
esac
[ "$FINGINDO" = "0" ] && echo "  mensagens da escola com autor de pessoa ...... 0 (como tem de ser)" \
  || parar "achei $FINGINDO mensagem(ns) da escola com autor de pessoa. Isso contraria o mandato de 30/08/2026 e precisa ser investigado."

echo
echo "PRONTO: as dúvidas da escola estão publicadas no fórum."
echo "Todas assinadas por Meshcraft Academy. Nenhuma finge ser de aluno."
echo "O visitante lê as de Avisos em https://meshcraft.top/forum/ ; as demais"
echo "aparecem para quem entra com matrícula."
