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
| Criar uma página em vários idiomas | **R12** | Texto fixo no template; a tag `url` crua; página nascendo com um idioma só |
| Acrescentar um idioma a um site | **R12** | Recalcular o `_fonte` sem traduzir; idioma novo nascendo indexável |

## §2 — O Despacho (template de brief — copie e preencha)

```markdown
# DESPACHO — <celula>: <tarefa em ≤5 palavras>
CÉLULA: <celula> · WORKTREE: wt-<celula>-<tarefa> · RECEITAS: R_, R_
ANTES: ARMADILHAS.md (raiz) + services/<celula>/LICOES.md, se existir. Ao terminar,
  acrescente o que aprendeu; o que só o mantenedor resolve vai na tabela §1 do
  ARMADILHAS.md E no seu relatório final.
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

**Addendo — contrato sem `$ref` nomeado (schemas 100% inline nos paths):** alguns
contratos (ex.: `leads`, `alunos`) não declaram `components.schemas` — todo
`requestBody`/`response` é inline no próprio path. Se o handler usar um
`ninja.Schema` tipado normalmente (como `OfferOut` acima), o django-ninja extrai o
model para um `components.schemas.<Nome>` nomeado e referencia via `$ref` — o
freeze reprova, porque o congelado não tem esse `$ref`. Nesse caso, não tipe o
corpo com `Schema`: aceite `request` sem parâmetro de corpo tipado e declare o
`requestBody`/`responses` inteiros via `openapi_extra` no decorator (dict Python
literal, na mesma forma exata do YAML congelado — chaves de status como `int`,
não string). `deep_dict_update` do django-ninja faz merge recursivo: se a chave
já existir (ex.: `responses[200]["description"]`) o valor é sobrescrito; se não
existir (ex.: `requestBody`, ou um novo status `422`), é inserida inteira. Depois,
em `export_openapi.py`, remova também o que o django-ninja sempre emite mas o
contrato à mão omite quando vazio: `"parameters": []` por operação sem parâmetro
de path/query, e `components.schemas: {}` quando nenhum model nomeado foi
registrado. Exemplo completo: `services/leads/apps/core/api.py` +
`services/leads/apps/core/management/commands/export_openapi.py`.

Nota: esta técnica existe porque os contratos originais desta plataforma
misturam schemas nomeados e inline sem critério declarado. Contratos NOVOS
deveriam preferir components.schemas nomeados desde o início — evita este
workaround por completo. Use openapi_extra só quando o contrato congelado já
existir inline e mudar a estrutura não for opção (Rito de Contrato).

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

Página de site multilíngue (host no `sites_i18n.yaml`): **R12** manda — texto por
`{% t %}`, link por `{% url_i18n %}`, strings da ilha pela subárvore `js.*`.

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

---

## R12 — Página multilíngue (prefixo de idioma + catálogo key-major + `{% t %}`)

Lei: `docs/i18n/PLANO-I18N.md`, decisões D1–D9. Implementação de referência,
verificada e no ar desde 23/08/2026: `services/funil/` — **copie o padrão, não o
arquivo** (Lei 7). O portão é `apps/i18n/validador.py`, com DUAS entradas: o teste
`test_validador_da_celula_real_passa` (protege o merge) e `AppConfig.ready()`
(protege a produção — **catálogo inválido ⇒ a célula não sobe**, D4 fail-closed).
Não existe `ci/i18n_check.py` na raiz: o portão i18n roda dentro do `make ci` da
célula.

**Antes de escrever a primeira linha, escolha o fluxo (D9):**

| O que você vai fazer | Fluxo | Regra dura |
|---|---|---|
| Página NOVA em site já multilíngue | **A** | Nasce com TODOS os idiomas do site **no mesmo PR** — a paridade exata força, e o formato key-major faz custar **1 arquivo** de catálogo, tenha o site 3 ou 15 idiomas |
| Idioma NOVO em site que já tem páginas | **B** | Idioma-**base** novo toca TODO `traducoes/*.yaml` da célula de uma vez. Lote pela lane `traducoes`, ou sequência com `_fonte: pendente` + `indexavel: false` até completar |

> ✅ **Fluxo B — a lane funciona ponta a ponta desde 23/08/2026.** O portão
> (`ci/orcamento-de-mudanca.sh`) e a catraca (`ci/mergear.py`, `checar_labels()`)
> conhecem os dois a lane `traducoes` (ARMADILHAS §5.11, PR #94). Um lote com
> >15 arquivos passa **se e somente se** todo caminho casar
> `services/<celula>/traducoes/...` — e a label `traducoes` existe no GitHub.
> Divisão de trabalho entre os dois, de propósito: a catraca confere o
> **caminho**; o **modo** (executável, symlink, submódulo) fica com as muralhas,
> porque a API de PR do GitHub não devolve modo. Dois testes-guarda leem o
> próprio `.sh` e reprovam se as duas cópias da regra divergirem.

### A — Página nova (todos os idiomas de uma vez)

**1. Template** em `templates/<celula>/<pagina>.html` — `{% extends %}` na
LINHA 1, sempre (LICOES do funil: até um `{% load %}` antes derruba o parse):

```html
{% extends "base_mobile.html" %}
{% load t %}
{% load url_i18n %}
<!-- templates/<celula>/<pagina>.html  [RECEITA:R12 v1]
     Todo texto visível sai do catálogo. Em COMENTÁRIO de template, cite a tag
     url crua do Django pelo NOME — nunca escreva a sintaxe dela aqui: o lint do
     validador varre o arquivo inteiro por regex e reprova o comentário. -->
{% block titulo %}{% t "<pagina>.titulo" %}{% endblock %}
{% block head_extra %}
  <meta name="description" content="{% t "<pagina>.meta_descricao" %}">
  <meta property="og:title" content="{% t "<pagina>.titulo" %}">
  <meta property="og:description" content="{% t "<pagina>.meta_descricao" %}">
{% endblock %}
{% block conteudo %}
{{ i18n_js|json_script:"i18n-data" }}
<div class="card" x-data="ilha()" x-init="init()">
  <h1>{% t "<pagina>.titulo_pagina" %}</h1>
  <form method="post" action="{% url_i18n '<pagina>' %}">
    <button class="cta" type="submit"><span x-text="i18n.enviando">{% t "<pagina>.js.enviar" %}</span></button>
  </form>
</div>
{% endblock %}
```

Regras que o portão IMPÕE neste arquivo (não são estilo):

- **`{% t %}` com chave LITERAL entre aspas.** Chave dinâmica (`{% t variavel %}`)
  cega a análise estática e reprova.
- **`{% url_i18n %}` em TODO link/action interno.** A tag `url` crua do Django
  em template que usa `{% t %}` é **FAIL** — ela não gera o prefixo, e o link
  cairia na matriz D1 (GET vira 302 extra; POST vira 404 com o corpo
  descartado). Link para OUTRA célula continua cru e monolíngue até o D6 entrar
  no Traefik.
- **`title`, meta description e og:\* saem do catálogo** como qualquer texto —
  `lang`, `dir`, canonical, hreflang, `x-default`, `og:locale`, `robots
  noindex` e o seletor de idiomas o `base_mobile.html` já emite sozinho, do
  registro (`registro.dados_seo`). Não escreva nenhum deles à mão.
- **Ilha Alpine**: as strings que o JS troca em runtime moram na subárvore
  `<pagina>.js.*`, emitidas com `|json_script` e lidas no `init()`. **Proibido
  catálogo de tradução em JS.**

**2. Catálogo** `traducoes/<pagina>.yaml` — 1 arquivo, todos os idiomas lado a
lado. O nome do arquivo (`[a-z0-9_]+`) é o PRIMEIRO segmento de toda chave:

```yaml
# traducoes/<pagina>.yaml  # [RECEITA:R12 v1]
titulo:
  # Comentário YAML é o contexto que o tradutor-IA lê — use.
  _fonte: "9741dd"                       # sha256(valor en)[:6]
  en: "Sign up — Meshcraft"
  pt-br: "Cadastro — Meshcraft"
  es: "Registro — Meshcraft"

itens:
  _fonte: "a1b2c3"                       # plural: categorias CLDR DO IDIOMA
  en:    { one: "{quantidade} item", other: "{quantidade} items" }
  pt-br: { one: "{quantidade} item", many: "{quantidade} de itens", other: "{quantidade} itens" }

aviso.html:                              # única forma que admite markup
  _fonte: "d4e5f6"
  en: "See <strong>{nome}</strong>"

js:                                      # subárvore da ilha Alpine
  enviar:
    _fonte: "0f1e2d"
    en: "Send"
```

Formato, ponto a ponto (tudo verificado em `apps/i18n/catalogo.py`):

- **Chave semântica, imutável**: nomeia o papel (`cadastro.cta_primaria`), nunca
  o texto. Mudança de copy NÃO renomeia chave. Duplicar é melhor que acoplar.
- **Toda folha é string entre aspas** — o loader estrito recusa folha não-string
  (`12:30` viraria 750, `no` viraria `False`), chave duplicada, âncora, alias e
  tag explícita.
- **Placeholders `{nome_simples}`** em `[a-z_][a-z0-9_]*` — sem ponto, sem
  índice, sem `!r`, sem `:>10`. O conjunto de placeholders tem de ser IDÊNTICO
  em todos os idiomas da chave.
- **Meta permitida hoje: `_fonte`, `_juridico` e `_revisado_humano`** (os dois
  últimos andam juntos — D8.2, ver abaixo). Qualquer outra chave com `_`
  reprova como meta desconhecida. `_juridico` vai **entre aspas**
  (`_juridico: "true"`): toda folha do catálogo é `str`, então o booleano nu
  morre antes, na regra do loader.
- **Sufixo `.html` só na folha**, com whitelist (`a abbr b br code em i small
  span strong`); handler `on*=` e `javascript:` reprovam. Todo o resto é
  escapado por padrão.

**3. View e rota.** O urlconf da célula **não conhece prefixo de idioma** — o
resolver decapa `/en|pt-br|es` de `request.path_info` antes da resolução:

```python
# config/urls.py  # [RECEITA:R12 v1]
path("<pagina>", <pagina>, name="<pagina>"),   # sem prefixo: o resolver já decapou
```

```python
# apps/core/views.py  # [RECEITA:R12 v1]
def <pagina>(request):
    if getattr(request, "idioma", None) is None:
        raise Http404("página só existe em site registrado no i18n")   # decida EXPLICITAMENTE
    contexto = {"i18n_js": js_da_pagina("<pagina>", request.idioma)}
    return render(request, "<celula>/<pagina>.html", contexto)
```

Site fora do registro é monolíngue por construção: decida — **404** (como
`cadastro`) ou **template próprio separado** (como `landing`/`landing_i18n`).
Nunca um `if` de idioma dentro de um template só: é o que quebra o golden
byte-idêntico da landing.

**4. Sitemap**: acrescente o caminho a `PAGINAS_PUBLICAS` em `apps/core/views.py`
(hoje `("/", "/cadastro")`). Sem isso a página nasce fora do sitemap.

**5. Testes mínimos** (molde real: `tests/test_cadastro.py`) — parametrizados
pelos idiomas:

```python
@pytest.mark.parametrize("idioma", ("en", "pt-br", "es"))
def test_pagina_nos_3_idiomas(client, rede, idioma):
    resp = client.get(f"/{idioma}/<pagina>", HTTP_HOST=HOST_MESH)   # Host SEMPRE (§4.6)
    conteudo = resp.content.decode()
    assert f'<html lang="{TAGS[idioma]}" dir="ltr">' in conteudo
    assert f"<title>{escape(t('<pagina>.titulo', idioma))}</title>" in conteudo
    assert f'action="/{idioma}/<pagina>"' in conteudo

def test_pseudo_locale_sem_texto_hardcoded(catalogo_pseudo):        # D8.4
    html = get_template("<celula>/<pagina>.html").render({...}, request=_request_pseudo("/qps/<pagina>"))
    assert texto_hardcoded(html) == []
```

O teste de pseudo-locale é o **único detector mecânico de string fora do
catálogo** — página nova sem ele nasce sem rede. Valor esperado vem SEMPRE do
próprio `t()`/`gettext`, nunca de copy colado no teste (erro de formulário
localizado se afirma com `override()` + `gettext`).

### B — Idioma novo em site que já existe

**1. Registro** `services/<celula>/sites_i18n.yaml` (interim; destino final é
`infra/sites.json`, fase 4 com Rito de Contrato):

```yaml
    idiomas:
      en:    { tag: en,    dir: ltr, indexavel: true }
      fr:    { tag: fr,    dir: ltr, indexavel: false }              # idioma-BASE novo
      pt-pt: { tag: pt-PT, dir: ltr, indexavel: false, base: pt-br } # VARIANTE (overlay)
```

Campos obrigatórios e fail-closed: **código minúsculo** na URL (`[a-z]{2,3}`
com região opcional; `/pt-BR/` e `/pt_br/` são 404 por decisão), **`tag`** BCP 47
igual ao código em caixa canônica (`pt-br` ⇄ `pt-BR`), **`dir`** (`ltr`/`rtl`),
**`indexavel`** booleano explícito, **`base`** só em variante (máximo 1 nível —
base de variante não pode ter base; o `default` do site nunca é variante). Campo
desconhecido reprova. Todo host aqui tem de existir em `infra/sites.json`
(teste de coerência).

**2. Entenda o que você acabou de disparar.** Idioma **sem `base`** é
idioma-BASE: a paridade exata passa a exigi-lo em **toda chave de todo
`traducoes/*.yaml` da célula** — não só nas páginas novas. Idioma **com `base`**
é variante: overlay esparso, ausência herda (válido), presença tem de DIFERIR da
base (overlay idêntico reprova: "remova, a herança já cobre").

**3. Complete o eixo** em cada `traducoes/*.yaml`, com o `_fonte` correto por
chave. As duas saídas legítimas quando não dá para traduzir tudo no mesmo PR:

- **`_fonte: pendente` na chave** — isenta aquela chave da paridade e declara a
  degradação; em runtime cai pela cadeia (variante → base → en) com **ERROR +
  contador**. Degradação declarável, nunca inferível.
- **`indexavel: false`** — mantém o idioma fora do hreflang, do `x-default` e do
  sitemap enquanto está incompleto, e emite `robots noindex`.

**4. Nasça `indexavel: false`** (D5 — "3 idiomas bons antes do 4º"): idioma novo
em domínio novo com tradução de agente é o padrão que classificador de spam
procura. Indexar depois custa flipar um dado. Foi assim que o `es` nasceu.

**5. Lote**: label `traducoes` no PR (`gh pr edit <N> --add-label traducoes`) —
o `ci/orcamento-de-mudanca.sh` deixa passar >15 arquivos **somente se** 100% do
diff casar `services/<celula>/traducoes/...` e **todo arquivo entrar como dado**
(modo `100644` ou remoção `000000`; executável, symlink e submódulo reprovam).
Um único arquivo fora dessa árvore derruba a lane inteira de volta ao teto de 15.
**E releia o aviso da catraca lá em cima antes de montar o lote.**

### O contrato do `_fonte` (D4) — e a regra anti-burla

`_fonte` são os **6 primeiros hex do sha256 do valor `en`** no momento em que a
tradução foi feita. É o detector de obsolescência: `_fonte != hash(en)` ⇒ o
inglês mudou e as traduções daquela chave estão velhas ⇒ **FAIL**.

```bash
# hash de um valor simples (a fonte da verdade, plural incluso, é
# apps/i18n/catalogo.py::hash_da_fonte — plural entra em forma canônica)
python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:6])" "Sign up — Meshcraft"
```

**Regra anti-burla (o portão de verdade):** se o `_fonte` de uma chave **mudou
no diff** contra `origin/main`, os valores não-base daquela chave têm de ter
mudado também, **OU** estar `pendente`, **OU** a linha carregar o marcador
literal `# revisado-sem-alteracao` (o caso legítimo: typo no inglês que não
altera as traduções — auditável, greppável, contável).

> **Recalcular o hash sem traduzir é violação, não atalho.** É a primeira ideia
> de um agente instruído a "deixar o CI verde", e é exatamente o que esta regra
> existe para matar. Se você não vai traduzir agora, escreva `pendente`.

O diff é medido com `git` contra `${BASE_REF:-origin/main}`; **diff
incalculável ⇒ ERROR**, nunca skip. No boot a regra não roda (container não tem
git nem `origin/main`) — ela é do CI, por construção do checkout `fetch-depth: 0`.

### Checklist do validador — rode ANTES do push

```bash
cd services/<celula> && python -m pytest -q     # inclui o validador (entrada a)
make -C services/<celula> ci                    # lint + type + testes + freeze
bash ci/orcamento-de-mudanca.sh                 # orçamento / lane traducoes
```

O que ele reprova, item a item (se um destes ficar vermelho, é isto que ele está
medindo):

1. **Paridade exata** entre idiomas-base: falta E sobra reprovam (idioma não
   declarado no registro dentro de um MessageSpec = FAIL).
2. **Template ↔ catálogo nas DUAS direções**: chave usada e não definida, e
   chave definida e não usada em nenhum template. Só `*.js.*` é isenta da
   segunda (a ilha consome por `json_script`).
3. **Placeholders idênticos** entre idiomas e **restritos** (sem `{a.b}`,
   `{a[0]}`, `{a!r}`, `{a:>10}`).
4. **Plural CLDR do idioma**, consultado no `babel` pinado — exatamente as
   categorias daquele idioma, nunca lista à mão.
5. **Glossário de não-traduzir**: se o termo protegido aparece no `en`, tem de
   aparecer **literal** em toda tradução daquela chave. Os termos são a união
   dos glossários de todos os sites do registro.
6. **Overlay de variante**: presente sem a base reprova; idêntico à base
   reprova; ausência herda.
7. **Escape e `.html`**: whitelist de tags, nada de `on*=` nem `javascript:`;
   todo o resto escapado por padrão.
8. **YAML estrito**: chave duplicada, âncora, alias, tag explícita, folha
   não-string, chave não-string, mapeamento vazio, segmento fora de
   `[a-z0-9_]+`.
9. **`{% t %}` literal-only** e **tag `url` crua proibida** em template i18n.
10. **`_fonte`** presente, válido (6 hex ou `pendente`), igual a `hash(en)`, e a
    regra anti-burla acima.

Estados ([INV-CI01]): **PASS** mediu e está certo · **FAIL** mediu e achou
violação (conserte o catálogo) · **ERROR** não conseguiu medir (conserte o
ambiente — jamais leia como "quase passou").

### O que a máquina NÃO protege (D8) — sua responsabilidade, agente

Os portões acima verificam **integridade**. Nenhum verifica se a tradução está
**boa**. Numa página de cadastro de curso pago, copy é o produto:

- **Namespace jurídico** (termos de uso, privacidade, consentimento) **exige
  revisão humana antes de publicar** — e desde 23/08/2026 o marcador do D8.2
  **existe e tem dente**. Marque a chave com `_juridico: "true"` e declare a
  revisão em `_revisado_humano`, um mapa **idioma → "Quem revisou AAAA-MM-DD"**
  com uma entrada **por idioma** (revisar o inglês não valida o espanhol); o
  `_fonte` não pode estar `pendente`. Sem isso é FAIL no CI **e o boot recusa
  subir**. A declaração **expira**: se o texto daquele idioma mudar no diff,
  ela tem de mudar junto. Você não inventa o nome que vai ali — **peça a
  revisão ao mantenedor e registre o que ele responder**.
  ⛔ A outra guarda do D8.3, a **retrotradução**, continua NÃO implementada:
  depende de modelo externo (chave de API, custo) e é decisão do mantenedor —
  não escreva stub que finja fazê-la.
- **Nunca concatene frases** para montar um período — ordem de palavras e
  gênero mudam por idioma. Uma frase = uma chave.
- **Nunca traduza termo do glossário** (Meshcraft, Roblox, Roblox Studio, nomes
  de produto). O portão pega o caso fácil; o julgamento é seu.
- **`pt-br` é a janela de auditoria do mantenedor** — ele não lê inglês.
  Tradução **fiel ao sentido, nunca adaptação criativa**: se o pt-br "melhorar"
  o inglês, a única auditoria interna que existe deixa de funcionar. Risco
  estrutural ABERTO (D8.5) — só humano nativo ou conversão medida resolve.
- **Texto dentro de imagem é dívida**: um asset por idioma. Texto fica em HTML.

### CSS de página multilíngue

Propriedades **lógicas** em todo CSS novo: `margin-inline-start`,
`padding-inline-end`, `inset-inline`, `text-align: start/end`. **Nunca
`left`/`right`** — a direção vem do `dir` do registro, e o dia do primeiro RTL
vira flip de dado em vez de varredura de folha de estilo.

### Armadilhas já pagas (não redescubra)

`ARMADILHAS.md` **§4.10** (`path_info` vs `path` — o resolver reescreve
`path_info`; `request.path` segue completo e é dele que sai o canonical) ·
**§4.5** (isenção do `/healthz`; rota de máquina nunca se localiza — `/healthz`,
`/static/`, `/sitemap.xml`, `/api/**`, `/webhooks/**`) · **§4.6** e **§4.7**
(Host válido em todo teste, mock por endpoint, cache de sites limpo entre
testes) · **§4.14** (tags coladas quando a saída tem de ficar byte-idêntica) ·
**§5.1** (orçamento) · **§5.11** (a lane e a catraca) · **§6.1.1** (evidência
vermelho→verde por **patch**, nunca `git stash` — em lote o pop devolve o stash
de outro agente).

`services/funil/LICOES.md`: `{% extends %}` é a primeira tag, sempre · o
autoescape transforma `&` em `&amp;` (a asserção espera o escapado) · **o lint
lê os COMENTÁRIOS do template** — comentário que escreve a sintaxe proibida
derruba o `django.setup()` inteiro · `hreflang="es"` continua na **âncora** do
seletor mesmo com `noindex`; a asserção negativa mira
`<link rel="alternate" hreflang="es"`, nunca o atributo solto.

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
