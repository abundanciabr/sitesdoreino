"""O aviso de pagamento chega em duas versões ao mesmo tempo, e o mesmo fato
só pode acontecer uma vez.

`pagamento.aprovado.v2` e `pagamento.recusado.v2` tiraram o nome do fornecedor
do contrato: saiu `mp_payment_id`, entrou o par `provider` mais
`provider_reference_id`, e `site_id` virou `platform_site_id`. O v1 continua
sendo emitido até o último consumidor migrar, então o MESMO pagamento chega
aqui nas duas versões, com `event_id` DIFERENTE em cada uma. Deduplicar por
`event_id` não serviria para nada.

Quem manda na chave é o contrato, no campo `x-ponte-do-v1` de cada schema v2, e
as duas cartas NÃO usam a mesma:

- `pagamento.aprovado`: o par (`provider`, `provider_reference_id`). No v1 o
  `provider` é o literal `mercadopago` e a referência vem de `mp_payment_id`.
- `pagamento.recusado`: só o `payment_id`. A recusa v1 nunca carregou
  referência do fornecedor, nem sob outro nome, então é o id local que
  atravessa as versões.

`test_a_ponte_com_o_v1_e_a_que_o_contrato_publica` compara a transcrição do
consumer com os schemas em disco: se o Rito de Contrato mudar a regra, este
arquivo reprova em vez de a célula duplicar pedido em produção.
"""

import json
import os
import threading
from pathlib import Path

import pytest
import redis as redis_lib
from django.db import connection

from apps.pedidos.management.commands import consume_eventos
from apps.pedidos.management.commands.consume_eventos import (
    AVISOS,
    GRUPO,
    AvisoDesconhecido,
    _processar,
    aplicar,
)
from apps.pedidos.models import FatoAplicado, Order
from conftest import aprovado_v1, aprovado_v2, recusado_v1, recusado_v2

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"
STREAM_APROVADO = "eventos.pagamento.aprovado"
TODOS_OS_STREAMS = (
    "eventos.pagamento.aprovado",
    "eventos.pagamento.recusado",
    "eventos.pix.expirado",
)


def _pedido(api, sessao_a) -> Order:
    resp = api.post(
        f"/api/checkout/sessoes/{sessao_a['id']}/pedido",
        {
            "customer": {"email": "cliente@exemplo.com", "name": "Cliente"},
            "method": "pix",
        },
    )
    assert resp.status_code == 201, resp.content
    return Order.objects.get(pk=resp.json()["order_id"])


# ---------------------------------------------------------------------------
# A regra de deduplicação é a que o contrato publica, não a que o consumer acha
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("evento", ["pagamento.aprovado", "pagamento.recusado"])
def test_a_ponte_com_o_v1_e_a_que_o_contrato_publica(evento):
    """O consumer transcreve `x-ponte-do-v1`; o schema em disco é a fonte. As
    duas cartas têm pontes DIFERENTES, e trocá-las duplicaria pedido pago."""
    schema = json.loads((CONTRATOS / f"{evento}.v2.json").read_text(encoding="utf-8"))
    ponte = schema["x-ponte-do-v1"]

    assert AVISOS[evento]["chave_entre_versoes"] == tuple(ponte["chave_entre_versoes"])
    assert AVISOS[evento]["no_v1"] == ponte["no_v1"]


def test_a_recusa_nao_deduplica_pelo_par_do_fornecedor():
    """A recusa v1 nunca teve referência do fornecedor: usar o par aqui faria
    todo v1 recusado virar um fato novo, e o pedido mudaria de estado duas
    vezes. O contrato manda usar `payment_id`, e é o que vale."""
    assert AVISOS["pagamento.recusado"]["chave_entre_versoes"] == ("payment_id",)
    assert AVISOS["pagamento.aprovado"]["chave_entre_versoes"] == (
        "provider",
        "provider_reference_id",
    )


# ---------------------------------------------------------------------------
# Cada versão sozinha, e as duas juntas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_v1_sozinho_paga_o_pedido(api, rede, sessao_a):
    order = _pedido(api, sessao_a)

    assert aplicar(aprovado_v1(order, mp_payment_id="mp-1")) is True

    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
def test_v2_sozinho_paga_o_pedido(api, rede, sessao_a):
    """O v2 não tem `mp_payment_id` e chama o site de `platform_site_id`: antes
    desta tarefa ele estourava no consumer e terminava na fila morta, com a
    compra paga e o pedido preso em "aguardando confirmação"."""
    order = _pedido(api, sessao_a)

    assert aplicar(aprovado_v2(order, provider_reference_id="appmax-1")) is True

    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
def test_v1_e_depois_v2_do_mesmo_fato_pagam_uma_vez_so(api, rede, sessao_a):
    order = _pedido(api, sessao_a)
    referencia = "mp-42"

    assert aplicar(aprovado_v1(order, mp_payment_id=referencia)) is True
    # Mesmo pagamento, outra versão: `event_id` diferente, `payment_id` local
    # diferente, e a MESMA referência no fornecedor.
    assert aplicar(aprovado_v2(order, provider_reference_id=referencia)) is False

    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
def test_ordem_invertida_v2_antes_do_v1_paga_uma_vez_so(api, rede, sessao_a):
    order = _pedido(api, sessao_a)
    referencia = "mp-42"

    assert aplicar(aprovado_v2(order, provider_reference_id=referencia)) is True
    assert aplicar(aprovado_v1(order, mp_payment_id=referencia)) is False

    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("versao", [1, 2])
def test_reentrega_do_mesmo_evento_nao_repete_o_efeito(api, rede, sessao_a, versao):
    """Entrega at-least-once: o transporte reentrega o MESMO envelope."""
    order = _pedido(api, sessao_a)
    envelope = (
        aprovado_v1(order, mp_payment_id="mp-7")
        if versao == 1
        else aprovado_v2(order, provider_reference_id="mp-7")
    )

    assert aplicar(envelope) is True
    assert aplicar(envelope) is False
    assert aplicar(envelope) is False

    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
def test_a_mesma_referencia_em_fornecedores_diferentes_sao_dois_fatos(
    api, rede, sessao_a
):
    """`provider_reference_id` sozinho NÃO identifica o fato: é opaco e cada
    fornecedor numera do seu jeito, então dois provedores podem emitir a mesma
    string. Quem deduplicasse só pela referência engoliria o segundo aviso."""
    order = _pedido(api, sessao_a)

    assert (
        aplicar(aprovado_v2(order, provider="mercadopago", provider_reference_id="7"))
        is True
    )
    assert (
        aplicar(aprovado_v2(order, provider="appmax", provider_reference_id="7"))
        is True
    )

    assert FatoAplicado.objects.count() == 2


@pytest.mark.django_db
def test_a_recusa_atravessa_as_versoes_pelo_payment_id(api, rede, sessao_a):
    """A ponte da recusa é o `payment_id`. O v2 carrega um par de fornecedor
    que o v1 não tinha, e ainda assim os dois são o MESMO fato."""
    order = _pedido(api, sessao_a)

    assert aplicar(recusado_v1(order, payment_id="pag-99")) is True
    assert aplicar(recusado_v2(order, payment_id="pag-99")) is False

    order.refresh_from_db()
    assert order.status == "recusado"
    assert FatoAplicado.objects.count() == 1


@pytest.mark.django_db
def test_aviso_de_versao_desconhecida_estoura_com_instrucao(api, rede, sessao_a):
    """Versão fora do contrato não pode ser engolida em silêncio: estourar
    deixa a mensagem no PEL, e a fila morta a recolhe com o event_id."""
    order = _pedido(api, sessao_a)
    envelope = aprovado_v1(order, mp_payment_id="mp-1")
    envelope["version"] = 99

    with pytest.raises(AvisoDesconhecido) as erro:
        aplicar(envelope)

    assert "pagamento.aprovado v99" in str(erro.value)
    assert "Rito de Contrato" in str(erro.value)
    order.refresh_from_db()
    assert order.status == "aguardando_pagamento"


@pytest.mark.django_db
def test_efeito_que_estoura_nao_deixa_o_fato_marcado(api, rede, sessao_a, monkeypatch):
    """Marcar o fato ANTES e aplicar o efeito DEPOIS, fora da mesma transação,
    é o erro que já saiu caro em três células (RETROSPECTIVA-FASE-D §4): a
    reentrega chega, encontra o fato marcado, descarta o evento em silêncio, e
    a compra fica paga com o pedido preso em "aguardando confirmação". Aqui o
    efeito que estoura tem de derrubar o registro junto, e a reentrega tem de
    voltar a encontrar trabalho a fazer."""
    order = _pedido(api, sessao_a)
    envelope = aprovado_v1(order, mp_payment_id="mp-1")

    def cair(*args, **kwargs):
        raise RuntimeError("o efeito estourou no meio da transação")

    monkeypatch.setattr(consume_eventos.OrderModel.objects, "filter", cair)
    with pytest.raises(RuntimeError):
        aplicar(envelope)

    assert FatoAplicado.objects.count() == 0, "o fato ficou marcado sem o efeito"

    monkeypatch.undo()  # a reentrega, mais tarde, com o banco de volta
    assert aplicar(envelope) is True
    order.refresh_from_db()
    assert order.status == "pago"


@pytest.mark.django_db
def test_aviso_com_o_site_errado_nao_queima_a_identidade_do_fato(api, rede, sessao_a):
    """[INV-P11] Um aviso cujo site não é o do pedido não move nada, e não pode
    levar junto a identidade do fato: o aviso legítimo do mesmo pagamento chega
    depois e tem de pagar o pedido, em vez de ser descartado como duplicado."""
    order = _pedido(api, sessao_a)
    de_outro_site = aprovado_v1(order, mp_payment_id="mp-1")
    de_outro_site["data"]["site_id"] = "site-de-outro-lugar"

    aplicar(de_outro_site)
    order.refresh_from_db()
    assert order.status == "aguardando_pagamento"

    assert aplicar(aprovado_v1(order, mp_payment_id="mp-1")) is True
    order.refresh_from_db()
    assert order.status == "pago"


# ---------------------------------------------------------------------------
# Concorrência, com Redis real e dois consumidores do mesmo grupo
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_real():
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        pytest.fail(
            "REDIS_STREAMS_URL ausente: este teste exige um Redis REAL (no CI o "
            "serviço redis:7 do ci-celula já fornece; localmente suba um "
            "container da sessão e exporte a variável)."
        )
    conexao = redis_lib.from_url(url)
    conexao.ping()  # sem Redis de pé isto é ERROR, nunca um verde silencioso
    conexao.delete(*TODOS_OS_STREAMS)
    try:
        conexao.xgroup_create(STREAM_APROVADO, GRUPO, id="0", mkstream=True)
    except redis_lib.ResponseError:
        pass  # grupo já existe
    yield conexao
    conexao.delete(*TODOS_OS_STREAMS)
    conexao.close()


@pytest.mark.django_db(transaction=True)
def test_dois_consumidores_ao_mesmo_tempo_pagam_o_pedido_uma_vez_so(
    api, rede, sessao_a, redis_real
):
    """O pior caso real: v1 e v2 do mesmo pagamento são DUAS mensagens, então o
    grupo do Redis as entrega a consumidores diferentes, que as processam ao
    mesmo tempo. Quem segura a linha é o índice único da chave lógica no banco:
    um dos dois grava, o outro bate no índice e não aplica efeito nenhum."""
    order = _pedido(api, sessao_a)
    referencia = "mp-concorrente"
    for envelope in (
        aprovado_v1(order, mp_payment_id=referencia),
        aprovado_v2(order, provider_reference_id=referencia),
    ):
        redis_real.xadd(STREAM_APROVADO, {"json": json.dumps(envelope)})

    partida = threading.Barrier(2)
    erros = []

    def consumidor(nome):
        try:
            lidas = redis_real.xreadgroup(
                GRUPO, nome, {STREAM_APROVADO: ">"}, count=1, block=5000
            )
            assert lidas, f"{nome} não recebeu mensagem nenhuma do grupo"
            partida.wait(timeout=10)  # os dois processam na mesma janela
            for stream, mensagens in lidas:
                for msg_id, campos in mensagens:
                    _processar(redis_real, stream.decode(), msg_id, campos)
        except BaseException as erro:  # noqa: BLE001 - o teste precisa do motivo
            erros.append(f"{nome}: {erro!r}")
            partida.abort()
        finally:
            connection.close()  # cada thread tem a sua conexão; não a vaze

    fios = [threading.Thread(target=consumidor, args=(f"worker-{n}",)) for n in (1, 2)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=30)
        assert not fio.is_alive(), "um consumidor travou"

    assert not erros, erros
    order.refresh_from_db()
    assert order.status == "pago"
    assert FatoAplicado.objects.count() == 1, "o mesmo fato foi aplicado duas vezes"
    # As duas mensagens foram ACKadas: a perdedora da corrida não volta ao PEL
    # para ser reentregue e reprocessada mais tarde.
    assert redis_real.xpending(STREAM_APROVADO, GRUPO)["pending"] == 0
