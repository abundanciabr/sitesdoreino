#!/usr/bin/env bash
# =============================================================================
# SEMEAR AS PRIMEIRAS ÁREAS DO FÓRUM — para ele deixar de nascer vazio.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-areas-do-forum.yml`, disparado à
#   mão pelo agente ou pelo mantenedor. Nenhum terminal envolvido.
#
# E SE PRECISAR RODAR À MÃO, dentro da VPS (uma linha só, sem argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-areas-do-forum.sh -o /tmp/s.sh && bash /tmp/s.sh
#
#   O prompt tem de estar como `deploy@srv…` ou `root@srv…`. Se começar com
#   `PS C:\>`, você está no PC e este script não é para lá.
#
# SEGURO DE RODAR DUAS VEZES: o `semear_areas` é idempotente por construção
# (`get_or_create` pelo slug, e SEM atualizar o que já existe). Rodar de novo
# não duplica área nenhuma e não desfaz edição do mantenedor — se ele renomear
# "Dúvidas gerais", o nome dele fica.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita são as linhas de área no banco do próprio fórum.
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
    echo "'docker compose' desta plataforma roda. NADA foi alterado: nenhuma"
    echo "área foi criada e o fórum continua como estava."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e dispare este semeador de novo. O valor não se descobre daqui,"
    echo "e este script nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/3 — conferindo se o fórum está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "forum" || true)
[ -n "$ESTADO" ] || parar "o serviço 'forum' não está rodando. Sem ele não há banco a semear."
echo "  forum ...... de pé"

echo
echo "== 2/3 — semeando =="
# `-T` porque não há terminal do outro lado (o pipeline não aloca TTY).
SAIDA=$(docker compose exec -T forum python manage.py semear_areas 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_areas falhou. A saída acima diz por quê."; }
echo "$SAIDA"

# A PROVA, e não o eco. `armadilhas/114`: o log da ssh-action ecoa o script
# inteiro, então a frase que comprova execução não pode ser uma que também
# apareça aqui no corpo. Esta vem do PYTHON, do fim do caminho feliz dele.
printf '%s' "$SAIDA" | grep -q 'SEMEADURA DO FORUM OK' \
  || parar "o comando rodou mas não imprimiu a linha de conclusão — não posso afirmar que semeou."

echo
echo "== 3/3 — conferindo do lado de fora do comando =="
# Conta de novo, por outro caminho, em vez de confiar no que o próprio comando
# disse ter feito. Contagem zero aqui seria falso-verde.
QUANTAS=$(docker compose exec -T forum python manage.py shell -c \
  "from apps.forum.models import Area; print(Area.objects.filter(ativa=True).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$QUANTAS" in
  ''|*[!0-9]*) parar "não consegui contar as áreas depois de semear." ;;
esac
[ "$QUANTAS" -ge 4 ] || parar "esperava ao menos 4 áreas ativas e contei $QUANTAS."
echo "  áreas ativas no banco ...... $QUANTAS"

echo
echo "PRONTO: as primeiras áreas do fórum existem."
echo "O visitante vê as públicas em https://meshcraft.top/forum/ ; a sala dos"
echo "alunos só aparece para quem tem matrícula."
