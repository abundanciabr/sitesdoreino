#!/usr/bin/env bash
# =============================================================================
# ACERTO DE CONTAS DAS MENSAGENS DO FÓRUM — a segunda metade do backfill
# retroativo pedido pelo mantenedor em 03/09/2026 (a primeira, tópico e
# resposta aceita, é `backfill-pontos-do-forum.sh`).
#
# POR QUE ESTE É DIFERENTE DO OUTRO
# ------------------------------------
# `forum-topico-criado` e `forum-resposta-aceita` têm tabela-espelho DENTRO da
# gamificação (escrita independente da regra estar ligada), então aquele
# script só fala com UM serviço. Mensagem não tem espelho: o único lugar onde
# o fato ainda existe é o `Mensagem` do fórum, célula dona dele (Lei 3). Este
# script fala com DOIS serviços, no MESMO host, e encadeia a saída de um na
# entrada do outro — sem porta nova entre as duas células, sem par de tokens
# novo para provisionar.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/backfill-mensagens-do-forum.yml`.
#
# ENSAIO POR PADRÃO, como o irmão: só passa `--confirmo` ao comando de crédito
# quando CONFIRMAR="sim" — e ensaio nunca grava nada (roda tudo numa
# transação e desfaz no final).
#
# SEGURO DE RODAR DUAS VEZES: o comando de crédito é idempotente
# (`origem_event_id` determinístico + a trava única do ledger normal). O
# export é só leitura — rodar de novo não muda nada no fórum.
# =============================================================================
set -u
set -o pipefail

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

CONFIRMAR="${CONFIRMAR:-nao}"

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa?"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se o fórum e a gamificação estão de pé =="
for S in forum gamificacao; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$S" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$S' não está rodando."
done
echo "  forum, gamificacao ...... de pé"

echo
echo "== 2/4 — descobrindo o site e desde quando a regra vale =="
SITE=$(docker compose exec -T gamificacao printenv SITE_ID 2>/dev/null | tr -d '\r[:space:]')
[ -n "$SITE" ] || parar "o contêiner da gamificação não declara SITE_ID."
VIGENTE=$(docker compose exec -T gamificacao python manage.py shell -c \
  "from apps.gamificacao.models import RegraDePontuacao as R; r = R.objects.filter(site_id='$SITE', slug='forum-mensagem').first(); print(r.vigente_desde.isoformat() if r and r.vigente_desde else '')" \
  2>/dev/null | tr -d '\r' | tail -1)
[ -n "$VIGENTE" ] || parar "a regra 'forum-mensagem' ainda não existe ou não está ligada neste site. Ligue em https://meshcraft.top/admin/economia/ primeiro."
echo "  site ...... ${SITE}"
echo "  regra ligada desde ...... ${VIGENTE}"

echo
if [ "$CONFIRMAR" = "sim" ]; then
  echo "== 3/4 — exportando o histórico e CREDITANDO DE VERDADE (--confirmo) =="
else
  echo "== 3/4 — exportando o histórico e ENSAIANDO (nada será gravado) =="
fi
FLAG=""
[ "$CONFIRMAR" = "sim" ] && FLAG="--confirmo"
SAIDA=$( { docker compose exec -T forum python manage.py exportar_mensagens_para_backfill --antes-de "$VIGENTE" \
  | docker compose exec -T gamificacao python manage.py backfill_mensagens_do_forum --site-id "$SITE" $FLAG; } 2>&1 ) \
  || { echo "$SAIDA"; parar "o comando falhou. A saída acima diz por quê."; }
echo "$SAIDA"

printf '%s' "$SAIDA" | grep -q '^TOTAL:' \
  || parar "o comando rodou mas não imprimiu a linha TOTAL — não posso afirmar o resultado."

echo
echo "== 4/4 =="
if [ "$CONFIRMAR" = "sim" ]; then
  echo "PRONTO: o acerto de contas das mensagens foi gravado. A linha TOTAL acima diz exatamente o quê."
else
  echo "PRONTO: ensaio concluído, nada foi gravado. A linha TOTAL acima é o que SERIA pago."
  echo "Para gravar de verdade, dispare o workflow de novo marcando 'confirmar'."
fi
