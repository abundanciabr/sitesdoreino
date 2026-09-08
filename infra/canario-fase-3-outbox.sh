#!/usr/bin/env bash
set -u

parar() {
  echo
  echo "PAROU POR SEGURANCA: $1"
  echo "NADA foi removido."
  exit 1
}

[ "${CONFIRMAR:-nao}" = "sim" ] || parar "este canario cria marcas identificadas em producao; rode com confirmar=sim."

cd /opt/plataforma || parar "nao encontrei /opt/plataforma na VPS."
docker compose version >/dev/null 2>&1 || parar "docker compose nao respondeu na VPS."

RUN_ID="${CANARIO_F3_RUN_ID:-manual}"
RUN_ATTEMPT="${CANARIO_F3_RUN_ATTEMPT:-1}"
SHA="${CANARIO_F3_SHA:-sem-sha}"
SHA_CURTO="$(printf '%s' "$SHA" | cut -c1-12)"
MARCA="${RUN_ID}-${RUN_ATTEMPT}"
SITE_ID="canario-fase-3"
EMAIL_IDENTIDADE="canario-fase-3-identidade-${MARCA}@meshcraft.top"
EMAIL_ALUNOS="canario-fase-3-alunos-${MARCA}@meshcraft.top"
ORDER_ID="canario-fase-3:${MARCA}:${SHA_CURTO}"
PRODUCT_ID="canario-fase-3"

echo "== alvo =="
echo "run_id=$RUN_ID"
echo "run_attempt=$RUN_ATTEMPT"
echo "sha=$SHA_CURTO"
echo "site_id=$SITE_ID"
echo

for servico in redis identidade identidade-relay alunos alunos-relay alunos-consumer; do
  docker compose config --services 2>/dev/null | grep -qx "$servico" || parar "servico $servico nao existe no compose implantado."
  docker compose ps --status running --services 2>/dev/null | grep -qx "$servico" || parar "servico $servico nao esta running na VPS."
done

echo "== pacote outbox-relay nos processos executores =="
for servico in identidade identidade-relay alunos alunos-relay alunos-consumer; do
  saida="$(docker compose exec -T "$servico" python - <<'PY'
from importlib.metadata import version
import outbox_relay

print(f"{version('outbox-relay')} {outbox_relay.__file__}")
PY
)" || parar "nao consegui importar outbox-relay em $servico."
  printf '%s %s\n' "$servico" "$saida"
  printf '%s' "$saida" | grep -q '^0\.3\.1 ' || parar "$servico nao esta usando outbox-relay 0.3.1."
done
echo

echo "== canario identidade =="
IDENTIDADE_SAIDA="$(docker compose exec -T \
  -e CANARIO_EMAIL="$EMAIL_IDENTIDADE" \
  -e CANARIO_SITE_ID="$SITE_ID" \
  identidade python manage.py shell <<'PY'
import os

from apps.core import sessao
from apps.identidade.models import OutboxEvent

email = os.environ["CANARIO_EMAIL"].strip().lower()
site_id = os.environ["CANARIO_SITE_ID"]
identidade = sessao.cunhar_ou_recuperar(
    email=email,
    nome="Canario Fase 3",
    site_id=site_id,
)
evento = (
    OutboxEvent.objects.filter(
        event="identidade.pessoa-cadastrada",
        payload__pessoa_id=str(identidade.id),
        payload__site_id=site_id,
    )
    .order_by("-id")
    .first()
)
if evento is None:
    raise SystemExit("evento_identidade=ausente")
print(f"identidade_id={identidade.id}")
print(f"event_id={evento.event_id}")
print(f"event_version={evento.version}")
print(f"published_at={evento.published_at.isoformat() if evento.published_at else ''}")
PY
)" || parar "a jornada de identidade nao criou a outbox."
printf '%s\n' "$IDENTIDADE_SAIDA"
IDENTIDADE_EVENT_ID="$(printf '%s\n' "$IDENTIDADE_SAIDA" | awk -F= '$1=="event_id"{print $2; exit}')"
[ -n "$IDENTIDADE_EVENT_ID" ] || parar "nao consegui ler o event_id da identidade."
echo

echo "== canario alunos =="
ALUNOS_SAIDA="$(docker compose exec -T \
  -e CANARIO_EMAIL="$EMAIL_ALUNOS" \
  -e CANARIO_SITE_ID="$SITE_ID" \
  -e CANARIO_ORDER_ID="$ORDER_ID" \
  -e CANARIO_PRODUCT_ID="$PRODUCT_ID" \
  alunos python manage.py shell <<'PY'
import os

from apps.matriculas.models import OutboxEvent
from apps.matriculas.services import matricular

matricula, criada = matricular(
    site_id=os.environ["CANARIO_SITE_ID"],
    order_id=os.environ["CANARIO_ORDER_ID"],
    product_id=os.environ["CANARIO_PRODUCT_ID"],
    email=os.environ["CANARIO_EMAIL"].strip().lower(),
    name="Canario Fase 3",
)
evento = (
    OutboxEvent.objects.filter(
        event="matricula.situacao-alterada",
        payload__matricula_id=str(matricula.id),
        payload__site_id=os.environ["CANARIO_SITE_ID"],
    )
    .order_by("-id")
    .first()
)
if evento is None:
    raise SystemExit("evento_alunos=ausente")
if not criada:
    raise SystemExit("matricula_canario_ja_existia")
print(f"matricula_id={matricula.id}")
print(f"matricula_criada={criada}")
print(f"event_id={evento.event_id}")
print(f"event_version={evento.version}")
print(f"published_at={evento.published_at.isoformat() if evento.published_at else ''}")
PY
)" || parar "a jornada de alunos nao criou a outbox."
printf '%s\n' "$ALUNOS_SAIDA"
ALUNOS_EVENT_ID="$(printf '%s\n' "$ALUNOS_SAIDA" | awk -F= '$1=="event_id"{print $2; exit}')"
[ -n "$ALUNOS_EVENT_ID" ] || parar "nao consegui ler o event_id de alunos."
echo

echo "== pendencia controlada identidade-relay =="
IDENTIDADE_RELAY_SAIDA="$(docker compose exec -T \
  -e CANARIO_IDENTIDADE_EVENT_ID="$IDENTIDADE_EVENT_ID" \
  -e CANARIO_SITE_ID="$SITE_ID" \
  identidade python manage.py shell <<'PY'
import os

from django.db import transaction

from apps.identidade import eventos
from apps.identidade.models import OutboxEvent

origem = OutboxEvent.objects.get(event_id=os.environ["CANARIO_IDENTIDADE_EVENT_ID"])
with transaction.atomic():
    pendente = eventos.pessoa_cadastrada(
        site_id=os.environ["CANARIO_SITE_ID"],
        pessoa_id=origem.payload["pessoa_id"],
    )
if pendente.published_at is not None:
    raise SystemExit("pendencia_identidade_ja_publicada")
print(f"event_id={pendente.event_id}")
print(f"event_version={pendente.version}")
PY
)" || parar "nao consegui criar pendencia controlada para identidade-relay."
printf '%s\n' "$IDENTIDADE_RELAY_SAIDA"
IDENTIDADE_RELAY_EVENT_ID="$(printf '%s\n' "$IDENTIDADE_RELAY_SAIDA" | awk -F= '$1=="event_id"{print $2; exit}')"
[ -n "$IDENTIDADE_RELAY_EVENT_ID" ] || parar "nao consegui ler o event_id pendente da identidade."
echo

echo "== pendencia controlada alunos-relay =="
ALUNOS_RELAY_SAIDA="$(docker compose exec -T \
  -e CANARIO_ALUNOS_EVENT_ID="$ALUNOS_EVENT_ID" \
  alunos python manage.py shell <<'PY'
import os

from django.db import transaction

from apps.matriculas import eventos
from apps.matriculas.models import OutboxEvent

origem = OutboxEvent.objects.get(event_id=os.environ["CANARIO_ALUNOS_EVENT_ID"])
with transaction.atomic():
    pendente = eventos.emitir(
        "matricula.situacao-alterada",
        dict(origem.payload),
        envelope_extra={"ator_id": "canario-fase-3-relay"},
    )
if pendente.published_at is not None:
    raise SystemExit("pendencia_alunos_ja_publicada")
print(f"event_id={pendente.event_id}")
print(f"event_version={pendente.version}")
PY
)" || parar "nao consegui criar pendencia controlada para alunos-relay."
printf '%s\n' "$ALUNOS_RELAY_SAIDA"
ALUNOS_RELAY_EVENT_ID="$(printf '%s\n' "$ALUNOS_RELAY_SAIDA" | awk -F= '$1=="event_id"{print $2; exit}')"
[ -n "$ALUNOS_RELAY_EVENT_ID" ] || parar "nao consegui ler o event_id pendente de alunos."
echo

aguardar_evento() {
  servico="$1"
  evento="$2"
  event_id="$3"
  docker compose exec -T \
    -e CANARIO_EVENT_NAME="$evento" \
    -e CANARIO_EVENT_ID="$event_id" \
    "$servico" python manage.py shell <<'PY'
import json
import os
import time

import redis

event_name = os.environ["CANARIO_EVENT_NAME"]
event_id = os.environ["CANARIO_EVENT_ID"]
if event_name.startswith("identidade."):
    from apps.identidade.models import OutboxEvent as modelo
else:
    from apps.matriculas.models import OutboxEvent as modelo
stream = f"eventos.{event_name}"

for _ in range(90):
    evento = modelo.objects.get(event_id=event_id)
    publicado = evento.published_at is not None
    achou = False
    if publicado:
        cliente = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for _, campos in cliente.xrevrange(stream, count=500):
            bruto = campos.get(b"json") or campos.get("json")
            if not bruto:
                continue
            envelope = json.loads(bruto.decode() if isinstance(bruto, bytes) else bruto)
            if envelope.get("event_id") == event_id:
                achou = True
                break
    if publicado and achou:
        print(f"stream={stream}")
        print("published_at=true")
        print("event_id_no_stream=true")
        raise SystemExit(0)
    time.sleep(1)
raise SystemExit(f"evento {event_id} nao apareceu publicado no stream {stream}")
PY
}

echo "== publicacao identidade =="
aguardar_evento identidade "identidade.pessoa-cadastrada" "$IDENTIDADE_EVENT_ID" || parar "identidade nao publicou o canario no Redis."
echo

echo "== publicacao alunos =="
aguardar_evento alunos "matricula.situacao-alterada" "$ALUNOS_EVENT_ID" || parar "alunos nao publicou o canario no Redis."
echo

echo "== publicacao identidade-relay =="
aguardar_evento identidade "identidade.pessoa-cadastrada" "$IDENTIDADE_RELAY_EVENT_ID" || parar "identidade-relay nao publicou a pendencia controlada no Redis."
echo

echo "== publicacao alunos-relay =="
aguardar_evento alunos "matricula.situacao-alterada" "$ALUNOS_RELAY_EVENT_ID" || parar "alunos-relay nao publicou a pendencia controlada no Redis."
echo

echo "PRONTO: canario F3 outbox publicado em alunos e identidade"
echo "evidencia=run:$RUN_ID tentativa:$RUN_ATTEMPT sha:$SHA_CURTO identidade_event_id:$IDENTIDADE_EVENT_ID alunos_event_id:$ALUNOS_EVENT_ID identidade_relay_event_id:$IDENTIDADE_RELAY_EVENT_ID alunos_relay_event_id:$ALUNOS_RELAY_EVENT_ID"
