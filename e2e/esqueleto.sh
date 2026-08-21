#!/usr/bin/env bash
# e2e/esqueleto.sh — O ESQUELETO QUE ANDA (ver ESQUELETO-QUE-ANDA.md na raiz).
#
# Sobe o compose de dev do caminho (e2e/docker-compose.e2e.yml: catalogo,
# checkout, pagamentos, alunos + postgres + redis compartilhados), seeda e
# percorre via curl a transação inteira:
#
#   seed -> sessão -> pedido -> cobrança(intent real na MP sandbox) ->
#   webhook (DEBUG simulate-webhook assinado) -> outbox -> relay -> matrícula
#
# Cada elo imprime ✅ ou ❌. Qualquer ❌ falha o script (exit != 0) — inclusive
# quando o motivo é uma célula ainda não implementada (ver o aviso "ELOS
# CONHECIDOS EM ABERTO" no fim deste arquivo e ARMADILHAS.md §9): honestidade
# sobre o estado real do caminho é o objetivo, não um "verde" fabricado.
#
# Uso:
#   cp e2e/.env.e2e.exemplo e2e/.env.e2e   # uma vez, preenchendo MP_ACCESS_TOKEN
#   make esqueleto                          # ou: bash e2e/esqueleto.sh
#
# KEEP_UP=1 bash e2e/esqueleto.sh   # não derruba o compose no final (debug)
set -uo pipefail
export PYTHONUTF8=1  # [ARMADILHAS §3.3] acento/emoji não quebram a saída

cd "$(dirname "${BASH_SOURCE[0]}")"

ENV_FILE=".env.e2e"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ ERROR: e2e/$ENV_FILE não existe."
  echo "   Copie e2e/.env.e2e.exemplo para e2e/$ENV_FILE e preencha MP_ACCESS_TOKEN"
  echo "   (credencial sandbox TEST- real da MP — ver o comentário no exemplo)."
  exit 2
fi

# Lê DOMINIO_OPERACOES do .env.e2e para usar no Host: dos curls a seguir
# (mesmo valor que o compose passa ao seed do catalogo)
DOMINIO_OPERACOES="$(grep -E '^DOMINIO_OPERACOES=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
DOMINIO_OPERACOES="${DOMINIO_OPERACOES:-esqueleto.e2e.local}"

DC() { docker compose -f docker-compose.e2e.yml --env-file "$ENV_FILE" "$@"; }

EMAIL="aluno.esqueleto+$(date +%s)@exemplo.com.br"
TOKEN_CHECKOUT="e2e-token-e2e-para-checkout"
TOKEN_PAGAMENTOS="e2e-token-checkout-para-pagamentos"
TOKEN_ALUNOS="e2e-token-e2e-para-alunos"

ELO=0
FALHOU=0

elo() {
  ELO=$((ELO + 1))
  echo ""
  echo "── elo $ELO: $1 ──"
}

ok() { echo "✅ $1"; }

falhar() {
  echo "❌ $1"
  FALHOU=1
}

parar() {
  echo ""
  echo "❌ ESQUELETO FALHOU no elo $ELO ($1)."
  if [[ "${CLEANUP_ON_FAIL:-0}" == "1" ]]; then
    fechar
  else
    echo "── compose mantido de pé para inspeção (CLEANUP_ON_FAIL=1 para derrubar automaticamente) ──"
    echo "   logs:      docker compose -f e2e/docker-compose.e2e.yml logs <servico>"
    echo "   derrubar:  docker compose -f e2e/docker-compose.e2e.yml down -v"
  fi
  exit 1
}

jget() {
  # echo "$JSON" | jget <campo.aninhado>   — sem jq (nem sempre disponível; usa python, que é garantido)
  python -c "
import json, sys
d = json.load(sys.stdin)
for chave in sys.argv[1].split('.'):
    d = d[chave] if not chave.isdigit() else d[int(chave)]
print(d)
" "$1"
}

fechar() {
  if [[ "${KEEP_UP:-0}" != "1" ]]; then
    echo ""
    echo "── encerrando compose (KEEP_UP=1 para manter de pé em caso de debug) ──"
    DC down -v
  else
    echo ""
    echo "── KEEP_UP=1: compose mantido de pé. 'docker compose -f e2e/docker-compose.e2e.yml down -v' quando terminar. ──"
  fi
}

esperar_healthz() {
  local nome="$1" porta="$2"
  for _ in $(seq 1 60); do
    if curl -sS -o /dev/null -w '' "http://localhost:${porta}/healthz" 2>/dev/null; then
      ok "$nome respondeu /healthz"
      return 0
    fi
    sleep 2
  done
  return 1
}

echo "═══════════════════════════════════════════════════════════════"
echo " O ESQUELETO QUE ANDA — e2e local (webhook simulado, sandbox MP real)"
echo "═══════════════════════════════════════════════════════════════"

echo ""
echo "── subindo e2e/docker-compose.e2e.yml (build local, pode levar alguns minutos) ──"
if ! DC up -d --build; then
  echo "❌ ERROR: 'docker compose up' falhou — ver saída acima."
  echo "── compose mantido de pé para inspeção (CLEANUP_ON_FAIL=1 para derrubar automaticamente) ──"
  [[ "${CLEANUP_ON_FAIL:-0}" == "1" ]] && fechar
  exit 2
fi

echo ""
echo "── esperando /healthz das 4 células ──"
for par in "catalogo:8001" "pagamentos:8003" "checkout:8002" "alunos:8004"; do
  nome="${par%%:*}"
  porta="${par##*:}"
  if ! esperar_healthz "$nome" "$porta"; then
    echo "❌ ERROR: $nome não respondeu /healthz a tempo."
    DC logs "$nome" | tail -80
    echo "── compose mantido de pé para inspeção (CLEANUP_ON_FAIL=1 para derrubar automaticamente) ──"
    [[ "${CLEANUP_ON_FAIL:-0}" == "1" ]] && fechar
    exit 2
  fi
done

# ── elo 1: seed ──────────────────────────────────────────────────────────
elo "seed (catalogo: site + produto + oferta curso-esqueleto)"
SEED_OUT="$(DC exec -T catalogo python manage.py seed_esqueleto 2>&1)"
SEED_EXIT=$?
echo "$SEED_OUT"
if [[ $SEED_EXIT -ne 0 ]] || ! echo "$SEED_OUT" | grep -q "curso-esqueleto"; then
  falhar "seed_esqueleto não confirmou a oferta curso-esqueleto"
  parar "seed"
fi
ok "seed rodou (idempotente) — site host=$DOMINIO_OPERACOES"

# ── elo 2: sessão ────────────────────────────────────────────────────────
elo "sessão (POST /api/checkout/sessoes)"
RESP="$(curl -sS -w '\n%{http_code}' -X POST "http://localhost:8002/api/checkout/sessoes" \
  -H "Host: ${DOMINIO_OPERACOES}" \
  -H "Authorization: Bearer ${TOKEN_CHECKOUT}" \
  -H "Content-Type: application/json" \
  -d '{"offer_slug":"curso-esqueleto"}')"
HTTP_STATUS="$(echo "$RESP" | tail -n1)"
BODY="$(echo "$RESP" | sed '$d')"
if [[ "$HTTP_STATUS" != "201" ]]; then
  echo "$BODY"
  falhar "esperava 201, recebi $HTTP_STATUS"
  parar "sessão"
fi
SESSION_ID="$(echo "$BODY" | jget id)"
ok "sessão criada: $SESSION_ID"

# ── elo 3: pedido ────────────────────────────────────────────────────────
elo "pedido (POST /api/checkout/sessoes/{id}/pedido)"
RESP="$(curl -sS -w '\n%{http_code}' -X POST "http://localhost:8002/api/checkout/sessoes/${SESSION_ID}/pedido" \
  -H "Host: ${DOMINIO_OPERACOES}" \
  -H "Authorization: Bearer ${TOKEN_CHECKOUT}" \
  -H "Content-Type: application/json" \
  -d "{\"customer\":{\"email\":\"${EMAIL}\",\"name\":\"Aluno Esqueleto\"},\"method\":\"pix\"}")"
HTTP_STATUS="$(echo "$RESP" | tail -n1)"
BODY="$(echo "$RESP" | sed '$d')"
if [[ "$HTTP_STATUS" != "201" ]]; then
  echo "$BODY"
  falhar "esperava 201, recebi $HTTP_STATUS (elo 'cobrança' embutido aqui — confira MP_ACCESS_TOKEN em e2e/.env.e2e se for erro de autenticação da MP)"
  parar "pedido/cobrança"
fi
ORDER_ID="$(echo "$BODY" | jget order_id)"
INTENT_ID="$(echo "$BODY" | jget payment.intent_id)"
ok "pedido criado: order_id=$ORDER_ID intent_id=$INTENT_ID"

# ── elo 4: cobrança (intent real na MP sandbox) ─────────────────────────
elo "cobrança (intent em pagamentos, criada na MP sandbox de verdade)"
RESP="$(curl -sS -w '\n%{http_code}' "http://localhost:8003/api/pagamentos/intents/${INTENT_ID}" \
  -H "Authorization: Bearer ${TOKEN_PAGAMENTOS}")"
HTTP_STATUS="$(echo "$RESP" | tail -n1)"
BODY="$(echo "$RESP" | sed '$d')"
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "$BODY"
  falhar "GET /intents/${INTENT_ID} esperava 200, recebi $HTTP_STATUS"
  parar "cobrança"
fi
INTENT_STATUS="$(echo "$BODY" | jget status)"
MP_PAYMENT_ID="$(DC exec -T pagamentos python manage.py shell -c "
from pagamentos.core.models import Intent
print(Intent.objects.get(id='${INTENT_ID}').provider_payment_id)
" 2>/dev/null | tr -d '\r' | tail -n1)"
if [[ -z "$MP_PAYMENT_ID" ]]; then
  falhar "provider_payment_id vazio — a MP sandbox não devolveu um id de pagamento (confira MP_ACCESS_TOKEN)"
  parar "cobrança"
fi
ok "intent status=$INTENT_STATUS, mp_payment_id=$MP_PAYMENT_ID (MP sandbox respondeu de verdade)"

# ── elo 5: webhook (DEBUG simulate-webhook assinado) ────────────────────
elo "webhook (POST /debug/simulate-webhook, assinado, DEBUG=1)"
RESP="$(curl -sS -w '\n%{http_code}' -X POST "http://localhost:8003/debug/simulate-webhook" \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"pix\",\"mp_payment_id\":\"${MP_PAYMENT_ID}\",\"status\":\"approved\"}")"
HTTP_STATUS="$(echo "$RESP" | tail -n1)"
BODY="$(echo "$RESP" | sed '$d')"
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "$BODY"
  falhar "esperava 200, recebi $HTTP_STATUS"
  parar "webhook"
fi
WEBHOOK_INTERNO_STATUS="$(echo "$BODY" | jget webhook_status_code)"
if [[ "$WEBHOOK_INTERNO_STATUS" != "200" ]]; then
  echo "$BODY"
  falhar "o webhook assinado que o /debug entregou a si mesma voltou $WEBHOOK_INTERNO_STATUS (esperava 200 — assinatura/idempotência)"
  parar "webhook"
fi
RESP2="$(curl -sS "http://localhost:8003/api/pagamentos/intents/${INTENT_ID}" -H "Authorization: Bearer ${TOKEN_PAGAMENTOS}")"
INTENT_STATUS2="$(echo "$RESP2" | jget status)"
if [[ "$INTENT_STATUS2" != "approved" ]]; then
  falhar "intent deveria estar 'approved' após o webhook, está '$INTENT_STATUS2'"
  parar "webhook"
fi
ok "webhook assinado aceito; intent transicionou para approved"

# ── elo 6: outbox ────────────────────────────────────────────────────────
elo "outbox (pagamento.aprovado gravado e publicado na mesma transação — INV-P6)"
OUTBOX_OK="$(DC exec -T pagamentos python manage.py shell -c "
from pagamentos.core.models import OutboxEvent
qs = OutboxEvent.objects.filter(event='pagamento.aprovado', payload__order_id='${ORDER_ID}')
print('SIM' if qs.filter(published_at__isnull=False).exists() else 'NAO')
" 2>/dev/null | tr -d '\r' | tail -n1)"
if [[ "$OUTBOX_OK" != "SIM" ]]; then
  falhar "nenhum OutboxEvent pagamento.aprovado publicado para order_id=$ORDER_ID"
  parar "outbox"
fi
ok "OutboxEvent pagamento.aprovado publicado (published_at preenchido)"

# ── elo 7: relay (Redis Streams) ────────────────────────────────────────
elo "relay (eventos.pagamento.aprovado no Redis Streams)"
STREAM_OUT="$(DC exec -T redis redis-cli XRANGE eventos.pagamento.aprovado - + 2>/dev/null)"
if ! echo "$STREAM_OUT" | grep -q "$ORDER_ID"; then
  falhar "order_id=$ORDER_ID não apareceu em eventos.pagamento.aprovado (redis-cli XRANGE)"
  parar "relay"
fi
ok "evento presente no stream eventos.pagamento.aprovado"

# ── diagnóstico extra, não bloqueia (config/api.py do checkout documenta
#    este GET como consumido pela suíte E2E — fora do caminho numerado do
#    ESQUELETO-QUE-ANDA.md, por isso não falha o script; container
#    checkout-consumer é assíncrono, dá um tempo antes de checar). Roda
#    ANTES do elo 8 de propósito: elo 8 pode `parar` (exit) se alunos ainda
#    não implementou o GET, e essa informação não pode ficar presa depois. ──
STATUS_PEDIDO="?"
for _ in $(seq 1 15); do
  STATUS_PEDIDO="$(curl -sS "http://localhost:8002/api/checkout/pedidos/${ORDER_ID}" \
    -H "Host: ${DOMINIO_OPERACOES}" -H "Authorization: Bearer ${TOKEN_CHECKOUT}" | jget status 2>/dev/null || echo "?")"
  [[ "$STATUS_PEDIDO" == "pago" ]] && break
  sleep 1
done
echo ""
echo "ℹ diagnóstico (não bloqueia): GET /pedidos/${ORDER_ID}.status = ${STATUS_PEDIDO}"

# ── elo 8: matrícula (verificação final) ────────────────────────────────
elo "matrícula (GET /api/alunos/alunos/{email}/matriculas ⇒ matrícula ativa)"

# Diagnóstico: o consumer (apps/eventos/management/commands/consume_eventos.py,
# container alunos-consumer) é assíncrono — dá um tempo pra ele processar o
# evento antes de checar o banco. Não é o critério de aprovação do elo (esse é
# o GET abaixo, o que ESQUELETO-QUE-ANDA.md pede), só contexto pra mensagem de
# erro ser precisa se o GET falhar.
MATRICULA_NO_BANCO="NAO"
for _ in $(seq 1 15); do
  MATRICULA_NO_BANCO="$(DC exec -T alunos python manage.py shell -c "
from apps.matriculas.models import Matricula
m = Matricula.objects.filter(order_id='${ORDER_ID}').first()
print('SIM' if m and m.status == 'ativa' else 'NAO')
" 2>/dev/null | tr -d '\r' | tail -n1)"
  [[ "$MATRICULA_NO_BANCO" == "SIM" ]] && break
  sleep 1
done

RESP="$(curl -sS -w '\n%{http_code}' "http://localhost:8004/api/alunos/alunos/${EMAIL}/matriculas" \
  -H "Authorization: Bearer ${TOKEN_ALUNOS}")"
HTTP_STATUS="$(echo "$RESP" | tail -n1)"
BODY="$(echo "$RESP" | sed '$d')"
if [[ "$HTTP_STATUS" == "501" ]]; then
  echo "$BODY"
  if [[ "$MATRICULA_NO_BANCO" == "SIM" ]]; then
    falhar "GET /alunos/{email}/matriculas devolveu 501 (ainda não implementado — comentário em apps/core/api.py: 'listEnrollments segue fora de escopo'), MAS o consumer JÁ criou a matrícula ativa para order_id=$ORDER_ID no banco de alunos. O caminho de dados funciona ponta a ponta (evento -> consumer -> Matricula); só falta o endpoint de LEITURA."
  else
    falhar "GET /alunos/{email}/matriculas devolveu 501 e a matrícula também NÃO apareceu no banco para order_id=$ORDER_ID — o consumer não processou o evento (confira 'docker compose -f e2e/docker-compose.e2e.yml logs alunos-consumer')."
  fi
  parar "matrícula"
fi
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "$BODY"
  falhar "esperava 200, recebi $HTTP_STATUS"
  parar "matrícula"
fi
TEM_ATIVA="$(echo "$BODY" | python -c "
import json, sys
matriculas = json.load(sys.stdin)
print('SIM' if any(m.get('status') == 'ativa' for m in matriculas) else 'NAO')
")"
if [[ "$TEM_ATIVA" != "SIM" ]]; then
  echo "$BODY"
  falhar "resposta 200 mas nenhuma matrícula com status=ativa para $EMAIL"
  parar "matrícula"
fi
ok "matrícula ativa confirmada para $EMAIL"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ ESQUELETO ANDOU — todos os $ELO elos verdes."
echo "═══════════════════════════════════════════════════════════════"
fechar
exit 0
