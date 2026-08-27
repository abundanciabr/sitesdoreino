#!/usr/bin/env bash
# =============================================================================
# INAUGURAR A CAIXA DE SUGESTÕES — cria o quadro de ideias no banco dela.
#
# POR QUE ESTE SCRIPT EXISTE
# --------------------------
# Toda tela interna da Caixa (o quadro, os avisos, a moderação) começa por
# `quadro_atual()` em `services/sugestoes/apps/core/participacao.py`, que é
# FAIL-CLOSED de propósito: com zero quadros no banco ela levanta `Http404` em
# vez de inventar um. Em produção, o resultado é a página "Not Found" — sem
# nenhuma pista de que o que falta é o seed.
#
# Foi exatamente o que aconteceu em 27/08/2026: o mantenedor entrou na Caixa
# com o Google, viu "Você está dentro como … EQUIPE", clicou em "Ver o quadro
# de sugestões" e recebeu Not Found. A célula nasceu em lotes (Lotes 6 e 7 da
# Caixa) e este passo ficou no vão entre eles — nenhum despacho era dono dele.
#
# POR QUE UM SCRIPT NA VPS, E NÃO UMA MIGRATION AUTOMÁTICA
# --------------------------------------------------------
# O quadro é amarrado ao `site_id` — o UUID que a célula `catalogo` cunha para
# cada host (Lei 9). Esse número só existe no banco da produção: não está em
# `infra/sites.json` (que é declarativo, por host), e a `sugestoes` ainda não
# resolve Host→Site sozinha (CONV-SITE é despacho próprio; ver a docstring de
# `quadro_atual`). Uma migration que chutasse o valor amarraria toda a Caixa ao
# site errado em silêncio — o erro exato que o fail-closed existe para impedir.
#
# COMO O MANTENEDOR RODA (DENTRO da VPS, uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-caixa.sh -o /tmp/s.sh && bash /tmp/s.sh meshcraft.top
#
# O HOST É ARGUMENTO porque a plataforma é multissítio (Lei 9): em 27/08/2026 a
# produção já servia meshcraft.top E basileiatoutheou.org. Sem o argumento, o
# script só segue se houver exatamente UM site ativo; com dois ou mais ele lista
# e PARA, em vez de amarrar a Caixa ao site errado em silêncio.
#
# A linha começa com `curl`, e o prompt tem de estar como `deploy@srv…` ou
# `root@srv…` — se o seu prompt começa com `PS C:\>`, você está no PC e este
# script não é para lá.
#
# SEGURO DE RODAR DUAS VEZES: o `seed_sugestoes` é idempotente por construção
# (`get_or_create` no quadro e em cada categoria). Rodar de novo não duplica
# nada e não apaga ideia nenhuma — ele só completa o que faltar.
#
# NÃO ESCREVE SEGREDO NENHUM, não toca env, não reinicia serviço. As únicas
# escritas são as linhas do quadro e das categorias no banco da própria Caixa.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se as duas peças estão de pé =="
for SERVICO in catalogo sugestoes; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo."
  echo "  $SERVICO ...... de pé"
done

echo
echo "== 2/4 — descobrindo o site no catálogo =="
# A regra é a MESMA do `quadro_atual()` da célula, de propósito: um site ativo
# serve; zero ou vários PARAM. Escolher "o primeiro" aqui seria este script
# inventando um site padrão — a decisão que a própria Caixa se recusa a tomar.
SITES=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s') \
  || parar "não consegui perguntar ao catálogo quais sites existem."

QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. Sem site não há a quem amarrar o quadro."

listar_sites() {
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST; do
    echo "     - $HOST  ($ID)"
  done
}

# HOST COMO ARGUMENTO — a plataforma é multissítio (Lei 9) e em 27/08/2026 a
# produção já tinha DOIS sites ativos: meshcraft.top e basileiatoutheou.org. A
# primeira versão deste script parou aqui, corretamente, em vez de escolher.
#
# Com argumento: usa o que foi pedido, e PARA se ele não existir (nunca cai no
# "primeiro da lista" como consolo — seria o chute que o fail-closed evita).
# Sem argumento: só segue se houver exatamente UM site ativo, que é a mesma
# regra do `quadro_atual()` da célula.
HOST_PEDIDO="${1:-}"

if [ -n "$HOST_PEDIDO" ]; then
  LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
  if [ -z "$LINHA" ]; then
    echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
    listar_sites
    parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim)."
  fi
  SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
  SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
elif [ "$QUANTOS" -gt 1 ]; then
  echo "  Achei mais de um site ativo:"
  listar_sites
  echo
  echo "  Rode de novo dizendo QUAL, por exemplo:"
  echo "     bash /tmp/s.sh meshcraft.top"
  parar "há $QUANTOS sites ativos e eu não escolho por você."
else
  SITE_ID=$(printf '%s\n' "$SITES" | head -n1 | cut -f1)
  SITE_HOST=$(printf '%s\n' "$SITES" | head -n1 | cut -f2)
fi

[ -n "$SITE_ID" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site."
echo "  site ...... $SITE_HOST"
echo "  número .... $SITE_ID"

echo
echo "== 3/4 — estado ANTES =="
ANTES=$(docker compose exec -T sugestoes python manage.py shell -c \
  "from apps.sugestoes.models import Quadro, Categoria
print(f'{Quadro.objects.count()}\t{Categoria.objects.count()}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9]+\s+[0-9]+$' | head -n1) \
  || parar "não consegui perguntar à Caixa quantos quadros ela tem."
echo "  quadros ....... $(printf '%s' "$ANTES" | cut -f1)"
echo "  categorias .... $(printf '%s' "$ANTES" | cut -f2)"

echo
echo "== 4/4 — inaugurando (idempotente: rodar de novo não duplica) =="
docker compose exec -T sugestoes python manage.py seed_sugestoes --site-id "$SITE_ID" \
  || parar "o comando de seed falhou. A tela acima diz por quê — mande-a ao agente."

DEPOIS=$(docker compose exec -T sugestoes python manage.py shell -c \
  "from apps.sugestoes.models import Quadro, Categoria
print(f'{Quadro.objects.count()}\t{Categoria.objects.count()}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9]+\s+[0-9]+$' | head -n1)

echo
echo "== estado DEPOIS =="
echo "  quadros ....... $(printf '%s' "$DEPOIS" | cut -f1)"
echo "  categorias .... $(printf '%s' "$DEPOIS" | cut -f2)"
echo
if [ "$(printf '%s' "$DEPOIS" | cut -f1)" = "1" ]; then
  echo "PRONTO. Abra https://$SITE_HOST/forms/sugestoes/ e o quadro deve aparecer."
else
  echo "ATENÇÃO: esperava terminar com 1 quadro e terminei com $(printf '%s' "$DEPOIS" | cut -f1)."
  echo "Mande esta tela ao agente antes de usar a Caixa."
  exit 1
fi
