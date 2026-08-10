# CAMINHO DOURADO — As Receitas Canônicas da Plataforma

> A Constituição diz "não". Este documento diz "sim, exatamente assim".
> Velocidade assertiva = zero decisões no caminho feliz: o agente decide apenas
> o que é único da tarefa dele; todo o resto já está decidido aqui.

## §0 — Como usar (dieta por citação)

**Este documento NÃO é lido inteiro.** O despacho cita receitas por número
(`RECEITAS: R3, R5`); o agente carrega no contexto: este §0 + a tabela de decisão
(§1) + SOMENTE as receitas citadas. As receitas assumem a árvore do
`celula-template/` (projeto `config/`, apps em `apps/`).

**Três leis das receitas:**
1. Todo trecho colado leva o marcador da origem na primeira linha:
   `# [RECEITA:R3 v1]`. É assim que detectamos drift depois.
2. Desviar de uma receita não é improviso local — é issue `arquitetura:` ANTES.
3. Receita que precisar mudar duas vezes (chegar a v3) é candidata a virar pacote
   versionado (`plataforma-<nome>`) — a "casa única" definitiva da Lei 3. Mudança
   neste arquivo passa por CODEOWNERS, como toda lei.

## §1 — Tabela de decisão

| Preciso de... | Receita | Nunca faça |
|---|---|---|
| Expor um endpoint novo na minha API | **R1** | Mudar `contracts/` junto (rito §3 do RITOS.md) |
| Chamar a API de outra célula | **R2** | Importar código dela ou ler o banco dela |
| Avisar a plataforma que algo aconteceu | **R3** | Publicar direto no Redis sem outbox |
| Reagir a algo que aconteceu fora da célula | **R4** | Consultar o banco de quem emitiu |
| Proteger uma regra que não pode quebrar | **R5** | Guarda sem evidência vermelho→verde |
| Criar uma tela/página nova | **R6** | Estado compartilhado entre páginas; status decidido no cliente |
| Mudar o schema do banco | **R7** | Remover/renomear coluna na mesma release que parou de usá-la |
| Trabalho assíncrono interno da célula | **R8** | Task não-idempotente |
| Dado inicial, demo ou fixture de ambiente | **R9** | INSERT manual no banco |
| Marcar testes de caminho feliz por método | **R10** | Smoke sem marker registrado |
| Colocar um site/domínio novo no ar | **R11** | Editar o Traefik ou criar stack nova |

## §2 — O Despacho (template de brief — copie e preencha)

```markdown
# DESPACHO — <celula>: <tarefa em ≤5 palavras>
CÉLULA: <celula> · WORKTREE: wt-<celula>-<tarefa> · RECEITAS: R_, R_
CONTEXTO (≤5 linhas): ...
MISSÃO (1 frase): ...
ALVOS (PERMITIDO ESCREVER): services/<celula>/apps/<x>/..., services/<celula>/tests/...
SOMENTE-LEITURA: contracts/<...>.openapi.yaml, contracts/eventos/<...>.v1.json
FORA DE ESCOPO: <o que NÃO tocar, mesmo que pareça relacionado>
INVARIANTES TOCADOS: INV-P_ (evidência vermelho→verde obrigatória no PR)
DoD: make ci verde + <critérios específicos da tarefa>
ORÇAMENTO: ≤ N arquivos (fix: 1–5 · feature: 5–15)
```

## §3 — Convenções transversais (valem em toda receita)

```python
# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from django.core.exceptions import ImproperlyConfigured

def env(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = os.environ.get("SCRIPT_NAME") or None  # célula dona do próprio prefixo

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v}
```

```python
# apps/core/middleware.py — células PÚBLICAS (funil, quiz, checkout, alunos)  # [RECEITA:CONV-SITE v1]
import os
import time

import httpx
from django.http import Http404

_CACHE: dict = {}
TTL_SEGUNDOS = 60

class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição, via catálogo (com cache).
    Host não cadastrado ⇒ 404 — nunca um site padrão."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        site = self._resolver(host)
        if site is None:
            raise Http404("site desconhecido")
        request.site = site          # todo o resto da célula lê daqui
        return self.get_response(request)

    def _resolver(self, host: str):
        hit = _CACHE.get(host)
        if hit and hit[0] > time.time():
            return hit[1]
        r = httpx.get(
            f"{os.environ['CATALOGO_API_URL']}/sites/by-host/{host}",
            headers={"Authorization": f"Bearer {os.environ['TOKEN_CATALOGO']}"},
            timeout=5.0,
        )
        site = r.json() if r.status_code == 200 else None
        _CACHE[host] = (time.time() + TTL_SEGUNDOS, site)   # cacheia inclusive o 404
        return site
```

Registre em `MIDDLEWARE` logo após os middlewares de segurança do Django. Views e
queries da célula filtram SEMPRE por `request.site["id"]`.

Dinheiro: `amount_cents`/`price_cents`/`total_cents` **inteiros**, sempre.
Identificadores em EN, comentários e prosa em PT. `Decimal` só na borda do provider.

---

## R1 — Endpoint novo (Django-Ninja) + export do schema

```python
# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI
from apps.core.auth import BearerPorPar
from apps.ofertas.api import router as ofertas_router

api = NinjaAPI(title="Catalogo API", version="1.0.0", auth=BearerPorPar())
api.add_router("/ofertas", ofertas_router)
# Webhooks públicos (só na fortaleza): api.add_router("/webhooks", webhooks_router, auth=None)
```

```python
# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer

class BearerPorPar(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor."""
    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
```

```python
# apps/ofertas/api.py  # [RECEITA:R1 v1]
from ninja import Router, Schema

router = Router()

class OfferOut(Schema):
    slug: str
    price_cents: int  # dinheiro é centavos inteiros — lei da plataforma

@router.get("/{slug}", response=OfferOut)
def get_offer(request, slug: str):
    ...
```

```python
# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
import json
from django.core.management.base import BaseCommand
from config.api import api

class Command(BaseCommand):
    help = "Imprime o schema OpenAPI vivo (o freeze de contrato compara com contracts/)"
    def handle(self, *args, **kwargs):
        self.stdout.write(json.dumps(api.get_openapi_schema(), ensure_ascii=False))
```

JSON é YAML válido — o `ci/freeze-de-contrato.sh` aceita a saída como está.
**Se o endpoint novo não está no contrato congelado: PARE.** É Rito de Contrato
(RITOS.md §3), não decisão de sessão.

## R2 — Cliente da API de outra célula

```python
# apps/core/clients/pagamentos.py  # [RECEITA:R2 v1]
import os
import httpx

class PagamentosClient:
    """Fala SÓ o que está em contracts/pagamentos.openapi.yaml.
    Em dev, aponte PAGAMENTOS_API_URL para o mock prism (make mocks, porta 4010)."""

    def __init__(self) -> None:
        self.base = os.environ["PAGAMENTOS_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_PAGAMENTOS"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def criar_intent(self, *, idempotency_key: str, payload: dict) -> dict:
        r = httpx.post(
            f"{self.base}/intents",
            json=payload,
            headers={**self._headers(), "X-Idempotency-Key": idempotency_key},  # [INV-P4]
            timeout=10.0,  # timeout SEMPRE explícito
        )
        r.raise_for_status()
        return r.json()

    def obter_intent(self, intent_id: str) -> dict:
        r = httpx.get(f"{self.base}/intents/{intent_id}", headers=self._headers(), timeout=10.0)
        r.raise_for_status()
        return r.json()
```

Retry: livre em GET; em POST **somente** repetindo a MESMA `X-Idempotency-Key`.
Em testes unitários, mocke com `respx` — nunca suba a outra célula.

## R3 — Emitir evento (outbox transacional + relay)

```python
# apps/eventos/models.py  # [RECEITA:R3 v1]
import uuid
from django.db import models

class OutboxEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)            # ex.: "pagamento.aprovado"
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()                        # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]
```

```python
# apps/eventos/emitir.py  # [RECEITA:R3 v1]
from .models import OutboxEvent

def emitir(event: str, data: dict, *, version: int = 1) -> OutboxEvent:
    """[INV-P6] Chame SEMPRE dentro da MESMA transaction.atomic() da mudança de estado."""
    return OutboxEvent.objects.create(event=event, version=version, payload=data)
```

```python
# apps/eventos/tasks.py  # [RECEITA:R3 v1]
import json
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey
from .models import OutboxEvent

_r = redis.from_url(os.environ["REDIS_STREAMS_URL"])

@huey.periodic_task(crontab(minute="*"))   # rede de segurança
def relay_outbox():
    pendentes = OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:200]
    for ev in pendentes:
        envelope = {
            "event": ev.event,
            "version": ev.version,
            "event_id": str(ev.event_id),
            "occurred_at": ev.occurred_at.isoformat(),
            "data": ev.payload,
        }
        _r.xadd(f"eventos.{ev.event}", {"json": json.dumps(envelope, ensure_ascii=False)})
        ev.published_at = timezone.now()
        ev.save(update_fields=["published_at"])
```

Uso no ponto de mudança de estado (latência sub-segundo + segurança):

```python
from django.db import transaction
from apps.eventos.emitir import emitir
from apps.eventos.tasks import relay_outbox

with transaction.atomic():
    payment.aprovar()                      # mudança de estado
    emitir("pagamento.aprovado", data)     # [INV-P6] mesma transação
    transaction.on_commit(lambda: relay_outbox())   # publica já; o periódico cobre falhas
```

## R4 — Consumir evento (consumer group + dedup)

```python
# apps/eventos/models.py (acrescentar)  # [RECEITA:R4 v1]
class EventoProcessado(models.Model):
    event_id = models.UUIDField(unique=True)   # a unicidade É o guarda de idempotência
    processed_at = models.DateTimeField(auto_now_add=True)
```

```python
# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from apps.eventos.models import EventoProcessado
from apps.matriculas.handlers import ao_pagamento_aprovado

GRUPO = "alunos"                                # nome DESTA célula
STREAMS = {"eventos.pagamento.aprovado": ao_pagamento_aprovado}

class Command(BaseCommand):
    help = "Consumer de eventos da célula (roda como processo supervisionado)"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            resp = r.xreadgroup(GRUPO, "worker-1", {s: ">" for s in STREAMS}, count=10, block=5000)
            for stream, msgs in resp or []:
                handler = STREAMS[stream.decode()]
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    try:
                        EventoProcessado.objects.create(event_id=envelope["event_id"])
                    except IntegrityError:                      # já processado — idempotência
                        r.xack(stream, GRUPO, msg_id)
                        continue
                    handler(envelope["data"])
                    r.xack(stream, GRUPO, msg_id)
```

Handler com a unicidade como guarda (exemplo INV-P5):

```python
# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
from django.db import transaction
from .models import Matricula   # order_id = models.CharField(unique=True)

def ao_pagamento_aprovado(data: dict) -> None:
    with transaction.atomic():
        Matricula.objects.get_or_create(          # [INV-P5] unique=True é o guarda real
            order_id=data["order_id"],
            defaults={"email": data["customer"]["email"]},
        )
```

## R5 — Teste-guarda de invariante

```python
# tests/test_inv_p3_webhook_idempotente.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import pytest

pytestmark = pytest.mark.django_db

def test_webhook_reentregue_gera_uma_transicao(client, webhook_pix_assinado):
    for _ in range(3):
        resp = client.post("/api/pagamentos/webhooks/mp/pix", **webhook_pix_assinado)
        assert resp.status_code == 200
    assert Payment.objects.filter(status="approved").count() == 1
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1
```

Protocolo de evidência (Lei 6): rode o guarda ANTES do fix e cole a saída vermelha
crua no PR; rode DEPOIS e cole a verde. Sem edição, sem resumo.

## R6 — Página nova (ilha Alpine, mobile-first, status do servidor)

```html
<!-- templates/<celula>/pix.html  # [RECEITA:R6 v1] -->
{% extends "base_mobile.html" %}
{% block conteudo %}
<div x-data="pixIsland()" x-init="init()" class="p-4 max-w-md mx-auto">
  <img :src="qrBase64" alt="QR Code Pix" class="w-full">
  <p class="text-center mt-4" x-text="statusLabel()"></p>
</div>
<script>
function pixIsland() {
  return {
    status: "aguardando_pagamento",
    qrBase64: window.PIX_QR,
    async poll() {                                   // [INV-P7] status vem do servidor
      const pedido = await api.get(`/pedidos/${window.ORDER_ID}`);
      this.status = pedido.status;
      if (this.status === "aguardando_pagamento") setTimeout(() => this.poll(), 3000);
      if (this.status === "pago") window.location = window.URL_OBRIGADO;
    },
    statusLabel() {
      return { aguardando_pagamento: "Aguardando pagamento…", pago: "Pagamento confirmado!",
               expirado: "QR Code expirado" }[this.status] ?? this.status;
    },
    init() { this.poll(); },
  };
}
</script>
{% endblock %}
```

```javascript
// static/<celula>/api.js  # [RECEITA:R6 v1] — cliente fino; NENHUMA regra de negócio
const api = {
  async get(path) {
    const r = await fetch(`${window.API_BASE}${path}`);
    if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(`${window.API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${path}: ${r.status}`);
    return r.json();
  },
};
```

Cada página é uma ilha: estado próprio, zero variáveis compartilhadas entre páginas.
Comunicação entre páginas = servidor (snapshot/status), nunca `localStorage` ou globais.

## R7 — Migration Expand-and-Contract (a dança de três releases)

| Release | O que entra | Regra |
|---|---|---|
| N (**expand**) | `AddField` nullable/nova tabela + código escreve nos DOIS lugares + `RunPython` de backfill | Nada é removido |
| N+1 (**switch**) | Código passa a LER só do novo; escrita dupla pode cair | Coluna velha ainda existe |
| N+2 (**contract**) | `RemoveField`/drop da coluna velha | Só depois do switch em produção |

```python
# migrations/000X_backfill_novo_campo.py  # [RECEITA:R7 v1]
from django.db import migrations

def backfill(apps, schema_editor):
    Order = apps.get_model("pedidos", "Order")
    for o in Order.objects.filter(novo_campo__isnull=True).iterator():
        o.novo_campo = derivar(o)
        o.save(update_fields=["novo_campo"])

class Migration(migrations.Migration):
    dependencies = [("pedidos", "000X_add_novo_campo")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
```

Nunca deletar/renomear migration aplicada. Migration reversível sempre que possível.

## R8 — Task assíncrona interna (Huey)

```python
# config/huey.py  # [RECEITA:R8 v1]
import os
from huey import RedisHuey

huey = RedisHuey(url=os.environ["HUEY_REDIS_URL"])   # db exclusivo da célula
```

```python
from config.huey import huey

@huey.task(retries=5, retry_delay=30)
def notificar_ponte(matricula_id: int) -> None:
    """Toda task é idempotente — retry é comportamento normal, não exceção."""
    ...
```

Fila intra-célula = Huey. Comunicação ENTRE células = eventos (R3/R4), nunca uma
célula enfileirando task na outra.

## R9 — Seed idempotente

```python
# apps/core/management/commands/seed_esqueleto.py  # [RECEITA:R9 v1]
from django.core.management.base import BaseCommand
from apps.produtos.models import Product, Offer

class Command(BaseCommand):
    help = "Dados do esqueleto — idempotente: rodar 2× não duplica nada"

    def handle(self, *args, **opts):
        produto, _ = Product.objects.get_or_create(
            slug="curso-esqueleto",
            defaults={"name": "Curso Esqueleto", "price_cents": 990, "active": True},
        )
        Offer.objects.get_or_create(slug="curso-esqueleto", defaults={"product": produto, "price_cents": 990})
        self.stdout.write(self.style.SUCCESS("✅ seed do esqueleto"))
```

## R10 — Markers de smoke registrados

```ini
# pytest.ini  # [RECEITA:R10 v1]
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
markers =
    smoke_pix: caminho feliz do Pix (cross-smoke roda quando cartão é tocado)
    smoke_card: caminho feliz do cartão (cross-smoke roda quando Pix é tocado)
```

```python
@pytest.mark.smoke_pix
def test_caminho_feliz_pix(...): ...
```

---

## R11 — Novo site (domínio) no ar

Um site novo é DADO, não infraestrutura. Três passos, minutos:

**1. DNS (mantenedor, fora do repo):** no Cloudflare (plano gratuito), adicionar o
domínio, registro `A` → IP da VPS (proxy laranja LIGADO), SSL mode **Full**.
Modo B (sem Cloudflare): adicionar o domínio à lista `tls.domains` do router
`funil` em `infra/traefik/dynamic/plataforma.yml` (uma linha, PR de infra).

**2. Cadastro (agente, célula catalogo):**

```python
# apps/sites/management/commands/criar_site.py  # [RECEITA:R11 v1]
from django.core.management.base import BaseCommand
from apps.sites.models import Site

class Command(BaseCommand):
    help = "Cadastra um site novo (idempotente por host)"

    def add_arguments(self, parser):
        parser.add_argument("host")
        parser.add_argument("name")

    def handle(self, host: str, name: str, **opts):
        site, criado = Site.objects.get_or_create(
            host=host.lower(), defaults={"name": name, "active": True}
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ criado' if criado else 'ℹ já existia'}: {site.host} → {site.id}"
        ))
```

Depois, as ofertas do site: criar `Offer` com o `site_id` novo (slug livre —
slugs são únicos POR site).

**3. Smoke (30 segundos):**

```bash
curl -sS https://<dominio-novo>/healthz                      # gateway ok
curl -sS https://<dominio-novo>/ | head -20                  # landing do site certo
# na VPS — host não cadastrado DEVE dar 404 (INV-P11):
curl -k -s -o /dev/null -w "%{http_code}\n" -H "Host: nao-cadastrado.teste" https://localhost/
```

## §4 — Anti-padrões com resposta pronta

| A tentação | A resposta (sem pensar duas vezes) |
|---|---|
| "Vou importar esse util da outra célula" | R2 (API) — ou issue `arquitetura:` propondo pacote versionado |
| "Leio o banco dela só pra conferir" | API dela (R2) ou evento (R4). O Postgres vai negar mesmo. |
| "O teste está errado, ajusto o assert" | PARE. RITOS.md §2.3 — teste é intocável; reporte. |
| "Crio um base.html compartilhado" | Cada célula tem o seu (Lei 7). Copie o padrão, não o arquivo. |
| "Só dessa vez o contrato muda junto" | A cerca reprova. Rito §3, com o mantenedor. |
| "Float facilita o cálculo do desconto" | `amount_cents` inteiro. Sempre. |
| "Coloco um retry nesse POST" | Só com a MESMA `X-Idempotency-Key` (R2). |
| "Resolvo a corrida com um sleep" | Poll de status do servidor (R6) ou lock/unicidade (R4). |
| "Um segundo commit gigante no fim" | Catraca verde (RITOS §2.1): verde ⇒ commit, sempre. |
| "Host desconhecido? Sirvo o site principal" | 404 (INV-P11). Site padrão silencioso contamina os testes de todos os sites. |

## §5 — Checklist pré-PR (30 segundos, mecânico)

1. `make ci` verde — saída colada no PR.
2. `git diff --name-only origin/main...HEAD` bate com os ALVOS do despacho.
3. Contagem de arquivos dentro do ORÇAMENTO do despacho.
4. `git diff origin/main...HEAD | grep -nE "TODO|print\(|console\.log"` — limpo ou justificado.
5. Invariante tocado ⇒ evidência vermelho→verde colada.
6. Handoff escrito no corpo do PR (RITOS §1).
7. Título em Conventional Commit: `feat(checkout): ...` / `fix(pix): ...`.
