"""A célula ganhou VOZ: o cadastro passa a ser um fato anunciado.

Degrau 1 do `PLANO-SEQUENCIAS-DE-MENSAGENS` (TAR-056). Até 31/08/2026 esta
célula cunhava a `Identidade` e não contava a ninguém — por isso o pedido mais
óbvio do mantenedor, *"após o cadastro, mandar boas-vindas"*, não tinha o que
escutar.

Os modos de falha medidos aqui são os que uma outbox existe para impedir, mais
os dois que este degrau acrescenta:

1. **evento fora da transação do fato** — sobreviveria a um rollback, e a
   plataforma passaria a acreditar em algo que não aconteceu;
2. **relay republicando** o que já publicou;
3. **reentrar virando cadastro de novo** — boas-vindas para sempre à mesma
   pessoa;
4. **anunciar com o site errado** — quem escuta usa esse campo para escolher
   template e remetente, e a mensagem sairia com a marca de outro site. Sem
   site confiável, o certo é cunhar e ficar calado.

E o de sempre nesta célula: **nenhum dado pessoal no evento**. Nem nome, nem
e-mail, nem provedor.
"""

import json
import uuid

import pytest
from django.db import transaction

from apps.core import sessao as ses
from apps.core.views import site_seguro
from apps.identidade import eventos
from apps.identidade.models import Identidade, OutboxEvent
from apps.identidade.tasks import relay_outbox

SITE = "site-mesh"


@pytest.mark.django_db
def test_cadastrar_anuncia_o_fato_na_mesma_transacao():
    identidade = ses.cunhar_ou_recuperar(
        email="alguem@exemplo.com", nome="Alguém", site_id=SITE
    )

    evento = OutboxEvent.objects.get()
    assert evento.event == "identidade.pessoa-cadastrada"
    assert evento.version == 1
    assert evento.payload == {"site_id": SITE, "pessoa_id": identidade.id}
    assert evento.published_at is None  # publicar é do relay, depois do commit


@pytest.mark.django_db
def test_reentrar_nao_anuncia_de_novo():
    """Reentrar não é cadastrar-se. Um evento por login mandaria boas-vindas
    para sempre à mesma pessoa."""
    ses.cunhar_ou_recuperar(email="alguem@exemplo.com", nome="Alguém", site_id=SITE)
    ses.cunhar_ou_recuperar(email="alguem@exemplo.com", nome="Outro Nome", site_id=SITE)

    assert Identidade.objects.count() == 1
    assert OutboxEvent.objects.count() == 1


@pytest.mark.django_db
def test_sem_site_a_pessoa_entra_e_o_fato_nao_e_anunciado(caplog):
    """A degradação escolhida, e ela é o lado seguro: publicar com o site
    errado faria a mensagem sair com a marca de outro site. Entrar continua
    funcionando, que é o que não pode quebrar nunca."""
    identidade = ses.cunhar_ou_recuperar(email="alguem@exemplo.com", nome="Alguém")

    assert Identidade.objects.filter(pk=identidade.pk).exists()
    assert OutboxEvent.objects.count() == 0
    assert "sem site_id" in caplog.text.lower()


@pytest.mark.django_db
def test_o_evento_nao_carrega_dado_pessoal_nenhum():
    """`additionalProperties: false` no contrato existe para que um campo "que
    seria útil" não entre despercebido. Este guarda mede o outro lado: o que
    saiu daqui."""
    ses.cunhar_ou_recuperar(email="lucas@exemplo.com", nome="Lucas Nunes", site_id=SITE)

    cru = json.dumps(OutboxEvent.objects.get().payload, ensure_ascii=False)
    assert "lucas@exemplo.com" not in cru
    assert "Lucas" not in cru
    assert "google" not in cru
    assert set(json.loads(cru)) == {"site_id", "pessoa_id"}


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_de_transacao_estoura():
    """A Lei 1 aplicada: em vez de confiar que todo ponto de emissão futuro se
    lembre do `atomic`, a própria função recusa a escrita."""
    with pytest.raises(eventos.EventoForaDaTransacao):
        eventos.pessoa_cadastrada(site_id=SITE, pessoa_id="idt-1")

    assert OutboxEvent.objects.count() == 0


# ---------------------------------------------------------------------------
# O relay
# ---------------------------------------------------------------------------
class RedisDublado:
    """O Redis Streams com a superfície que o relay usa, e nada mais."""

    def __init__(self):
        self.publicados = []

    def xadd(self, stream, campos):
        self.publicados.append((stream, campos))

    @classmethod
    def from_url(cls, _url, instancia=None):  # pragma: no cover - fábrica
        return instancia


@pytest.fixture
def redis_dublado(monkeypatch):
    dublê = RedisDublado()
    monkeypatch.setenv("REDIS_STREAMS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr("redis.from_url", lambda _url: dublê)
    return dublê


@pytest.mark.django_db
def test_o_relay_publica_no_stream_do_evento(redis_dublado):
    with transaction.atomic():
        eventos.pessoa_cadastrada(site_id=SITE, pessoa_id="idt-1")

    assert relay_outbox() == 1

    stream, campos = redis_dublado.publicados[0]
    assert stream == "eventos.identidade.pessoa-cadastrada"
    envelope = json.loads(campos["json"])
    assert envelope["event"] == "identidade.pessoa-cadastrada"
    assert envelope["version"] == 1
    assert uuid.UUID(envelope["event_id"])
    assert envelope["data"] == {"site_id": SITE, "pessoa_id": "idt-1"}
    assert OutboxEvent.objects.get().published_at is not None


@pytest.mark.django_db
def test_o_relay_nao_republica_o_que_ja_publicou(redis_dublado):
    """Segunda passada não republica: é o que torna a task periódica segura de
    rodar a cada minuto."""
    with transaction.atomic():
        eventos.pessoa_cadastrada(site_id=SITE, pessoa_id="idt-1")
    relay_outbox()

    assert relay_outbox() == 0
    assert len(redis_dublado.publicados) == 1


@pytest.mark.django_db
def test_o_relay_publica_antes_de_marcar(redis_dublado, monkeypatch):
    """A ordem é intocável. Marcar primeiro trocaria "republicar no pior caso"
    por "perder evento em silêncio" — e este guarda mede a ordem encenando a
    morte do processo no meio: se `xadd` estoura, nada fica marcado."""
    with transaction.atomic():
        eventos.pessoa_cadastrada(site_id=SITE, pessoa_id="idt-1")

    def morrer(*_args, **_kwargs):
        raise RuntimeError("o processo morreu no meio da publicação")

    monkeypatch.setattr(redis_dublado, "xadd", morrer)
    with pytest.raises(RuntimeError):
        relay_outbox()

    assert OutboxEvent.objects.get().published_at is None


# ---------------------------------------------------------------------------
# O site que chega pela porta
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cru",
    ["site-mesh", "site_123", "abc.def", "A" * 64],
)
def test_site_com_forma_de_id_passa(cru):
    assert site_seguro(cru) == cru


@pytest.mark.parametrize(
    "cru",
    [
        None,
        "",
        "   ",
        "com espaço",
        "../outro",
        "<script>",
        "A" * 65,
        "-comeca-com-hifen",
    ],
)
def test_site_estranho_vira_vazio_em_vez_de_erro(cru):
    """Entrada de rede: nunca vira caminho, nunca vira eco, nunca estoura. E
    vazio tem um significado definido lá na frente — cunha e não anuncia."""
    assert site_seguro(cru) == ""
