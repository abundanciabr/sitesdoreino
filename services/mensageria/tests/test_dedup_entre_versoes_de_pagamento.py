# tests/test_dedup_entre_versoes_de_pagamento.py — TAR-549
#
# O invariante: "UMA mensagem por fato", mesmo quando o MESMO pagamento chega
# uma vez como `pagamento.*.v1` e outra como `pagamento.*.v2` — dois envelopes
# com `event_id` diferente, então a dedup existente (unicidade de `event_id`,
# `EventoProcessado`) não pega essa repetição sozinha.
#
# A identidade lógica que atravessa as duas versões vem do contrato congelado
# (`x-ponte-do-v1` em `contracts/eventos/pagamento.aprovado.v2.json` e
# `pagamento.recusado.v2.json`), e as DUAS pontes são diferentes de propósito:
#
# - `pagamento.aprovado`: o par `provider` + `provider_reference_id` (no v1 o
#   par é sempre implícito `mercadopago` + `mp_payment_id`).
# - `pagamento.recusado`: só `payment_id` — o v1 da recusa NUNCA carregou
#   referência de provedor, nem sob o nome `mp_payment_id`.
#
# Nem `order_id` nem `payment_id`-do-aprovado servem para essa chave (o
# schema v2 do aprovado diz isso com todas as letras); por isso cada par de
# envelopes abaixo usa `order_id` DIFERENTE entre a v1 e a v2 do "mesmo fato":
# se o teste passasse só por `order_id` coincidir, ele estaria provando a
# trava errada.
import json
import os
import threading
from unittest.mock import patch
from uuid import uuid4

import pytest
import redis
from django.db import connection

from apps.eventos.handlers import ao_pagamento_aprovado, ao_pagamento_recusado
from apps.eventos.management.commands import consume_eventos
from apps.eventos.management.commands.consume_eventos import (
    GRUPO,
    identidade_do_fato,
    processar_envelope,
)
from apps.eventos.models import EnvioRegistrado, FatoDeProvedorVisto

pytestmark = pytest.mark.django_db(transaction=True)


# --------------------------------------------------------------------------
# Construtores de envelope — um por (evento, versão)
# --------------------------------------------------------------------------


def _envelope_aprovado_v1(
    *, mp_payment_id: str, order_id: str, site_id: str = "site-abc"
) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid4()),
        "occurred_at": "2026-09-20T12:00:00Z",
        "data": {
            "site_id": site_id,
            "payment_id": f"pay-interno-{order_id}",
            "order_id": order_id,
            "amount_cents": 1000,
            "method": "pix",
            "mp_payment_id": mp_payment_id,
            "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
        },
    }


def _envelope_aprovado_v2(
    *,
    provider: str,
    provider_reference_id: str,
    order_id: str,
    site_id: str = "site-abc",
) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 2,
        "event_id": str(uuid4()),
        "occurred_at": "2026-09-20T12:05:00Z",
        "data": {
            "platform_site_id": site_id,
            "payment_id": f"pay-interno-{order_id}",
            "order_id": order_id,
            "amount_cents": 1000,
            "method": "pix",
            "provider": provider,
            "provider_reference_id": provider_reference_id,
            "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
        },
    }


def _envelope_recusado_v1(
    *, payment_id: str, order_id: str, site_id: str = "site-abc"
) -> dict:
    return {
        "event": "pagamento.recusado",
        "version": 1,
        "event_id": str(uuid4()),
        "occurred_at": "2026-09-20T12:00:00Z",
        "data": {
            "site_id": site_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount_cents": 1000,
            "method": "card",
            "reason_code": "cc_rejected_insufficient_amount",
            "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
        },
    }


def _envelope_recusado_v2(
    *,
    payment_id: str,
    order_id: str,
    provider: str = "appmax",
    provider_reference_id: str = "ref-qualquer",
    site_id: str = "site-abc",
) -> dict:
    return {
        "event": "pagamento.recusado",
        "version": 2,
        "event_id": str(uuid4()),
        "occurred_at": "2026-09-20T12:05:00Z",
        "data": {
            "platform_site_id": site_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount_cents": 1000,
            "method": "card",
            "provider": provider,
            "provider_reference_id": provider_reference_id,
            "reason_code": "cc_rejected_insufficient_amount",
            "customer": {"email": "cliente@example.com", "name": "Cliente Um"},
        },
    }


# --------------------------------------------------------------------------
# identidade_do_fato() — a função pura
# --------------------------------------------------------------------------


def test_identidade_do_fato_aprovado_v1_e_v2_do_mesmo_pagamento_e_igual():
    v1 = identidade_do_fato(
        "pagamento.aprovado", 1, {"site_id": "site-a", "mp_payment_id": "mp-1"}
    )
    v2 = identidade_do_fato(
        "pagamento.aprovado",
        2,
        {
            "platform_site_id": "site-a",
            "provider": "mercadopago",
            "provider_reference_id": "mp-1",
        },
    )
    assert v1 == v2


def test_identidade_do_fato_aprovado_v2_de_provedor_diferente_nao_e_igual_a_v1():
    """O par inteiro importa: um v2 da Appmax com a MESMA string de referência
    que um mp_payment_id do Mercado Pago não é o mesmo fato."""
    v1 = identidade_do_fato(
        "pagamento.aprovado", 1, {"site_id": "site-a", "mp_payment_id": "123"}
    )
    v2 = identidade_do_fato(
        "pagamento.aprovado",
        2,
        {
            "platform_site_id": "site-a",
            "provider": "appmax",
            "provider_reference_id": "123",
        },
    )
    assert v1 != v2


def test_identidade_do_fato_aprovado_mesmo_par_em_sites_diferentes_nao_e_igual():
    """[INV-P11] A fronteira de site é PARTE da identidade: o mesmo
    provider+provider_reference_id em dois sites são DOIS fatos, nunca um."""
    site_a = identidade_do_fato(
        "pagamento.aprovado",
        2,
        {
            "platform_site_id": "site-a",
            "provider": "appmax",
            "provider_reference_id": "123",
        },
    )
    site_b = identidade_do_fato(
        "pagamento.aprovado",
        2,
        {
            "platform_site_id": "site-b",
            "provider": "appmax",
            "provider_reference_id": "123",
        },
    )
    assert site_a != site_b


def test_identidade_do_fato_recusado_ignora_provider_so_o_payment_id_importa():
    """A ponte do recusado é OUTRA: não existe par provider+referência no v1,
    então a chave é só `payment_id` — mesmo que a v2 traga provider e
    provider_reference_id diferentes, o fato é o mesmo."""
    v1 = identidade_do_fato(
        "pagamento.recusado", 1, {"site_id": "site-a", "payment_id": "pay-9"}
    )
    v2 = identidade_do_fato(
        "pagamento.recusado",
        2,
        {
            "platform_site_id": "site-a",
            "payment_id": "pay-9",
            "provider": "appmax",
            "provider_reference_id": "ref-x",
        },
    )
    assert v1 == v2


def test_identidade_do_fato_recusado_mesmo_payment_id_em_sites_diferentes_nao_e_igual():
    """[INV-P11] Mesma fronteira para a ponte do recusado: `payment_id` sozinho
    não é a identidade — o site escopa."""
    site_a = identidade_do_fato(
        "pagamento.recusado", 1, {"site_id": "site-a", "payment_id": "pay-9"}
    )
    site_b = identidade_do_fato(
        "pagamento.recusado", 1, {"site_id": "site-b", "payment_id": "pay-9"}
    )
    assert site_a != site_b


def test_identidade_do_fato_evento_sem_ponte_devolve_none():
    assert identidade_do_fato("pix.expirado", 1, {}) is None


# --------------------------------------------------------------------------
# pagamento.aprovado — v1 sozinho, v2 sozinho, e as duas ordens
# --------------------------------------------------------------------------


def test_aprovado_v1_sozinho_processa():
    envelope = _envelope_aprovado_v1(
        mp_payment_id="mp-solo-1", order_id="order-v1-solo"
    )
    with patch("apps.eventos.handlers.enviar_notificacao"):
        assert processar_envelope(envelope, ao_pagamento_aprovado) is True
    assert EnvioRegistrado.objects.filter(order_id="order-v1-solo").count() == 1


def test_aprovado_v2_sozinho_processa():
    """Vermelho antes do conserto: o handler lia `data['site_id']`, e o v2 só
    tem `platform_site_id` — este teste é quem prova o `KeyError` sumiu."""
    envelope = _envelope_aprovado_v2(
        provider="appmax", provider_reference_id="ref-solo-2", order_id="order-v2-solo"
    )
    with patch("apps.eventos.handlers.enviar_notificacao"):
        assert processar_envelope(envelope, ao_pagamento_aprovado) is True
    assert EnvioRegistrado.objects.filter(order_id="order-v2-solo").count() == 1


def test_aprovado_v1_seguido_de_v2_do_mesmo_fato_gera_um_unico_envio():
    referencia = f"mp-{uuid4().hex}"
    v1 = _envelope_aprovado_v1(mp_payment_id=referencia, order_id="order-v1-a")
    v2 = _envelope_aprovado_v2(
        provider="mercadopago", provider_reference_id=referencia, order_id="order-v2-a"
    )

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v1, ao_pagamento_aprovado) is True
        assert processar_envelope(v2, ao_pagamento_aprovado) is False

    assert mock_enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(tipo="boas_vindas", canal="email").count() == 1
    )
    assert EnvioRegistrado.objects.filter(order_id="order-v2-a").count() == 0
    assert (
        FatoDeProvedorVisto.objects.filter(
            evento="pagamento.aprovado", chave=f"site-abc:mercadopago:{referencia}"
        ).count()
        == 1
    )


def test_aprovado_ordem_invertida_v2_seguido_de_v1_do_mesmo_fato_gera_um_unico_envio():
    """Ordem invertida: o v2 chega primeiro (produtor já migrado), o v1 chega
    depois (relay atrasado ou reprocesso). A chave é simétrica: não importa
    qual versão grava a linha primeiro."""
    referencia = f"mp-{uuid4().hex}"
    v2 = _envelope_aprovado_v2(
        provider="mercadopago", provider_reference_id=referencia, order_id="order-v2-b"
    )
    v1 = _envelope_aprovado_v1(mp_payment_id=referencia, order_id="order-v1-b")

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v2, ao_pagamento_aprovado) is True
        assert processar_envelope(v1, ao_pagamento_aprovado) is False

    assert mock_enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(tipo="boas_vindas", canal="email").count() == 1
    )
    assert EnvioRegistrado.objects.filter(order_id="order-v1-b").count() == 0


def test_aprovado_reentrega_do_mesmo_evento_v2_gera_um_unico_envio():
    """A metade que já existia (dedup por `event_id`) continua valendo para o
    v2: o MESMO envelope, reentregue com o MESMO `event_id`, não duplica."""
    envelope = _envelope_aprovado_v2(
        provider="appmax",
        provider_reference_id="ref-reentrega",
        order_id="order-reentrega",
    )
    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(envelope, ao_pagamento_aprovado) is True
        assert processar_envelope(envelope, ao_pagamento_aprovado) is False

    assert mock_enviar.call_count == 1
    assert EnvioRegistrado.objects.filter(order_id="order-reentrega").count() == 1


def test_aprovado_fatos_diferentes_nao_colidem():
    """Controle negativo: sem isto, um bug que gravasse sempre a MESMA chave
    (ex.: só o nome do evento) passaria despercebido pelos testes acima."""
    v1 = _envelope_aprovado_v1(mp_payment_id="mp-A", order_id="order-A")
    v2 = _envelope_aprovado_v2(
        provider="appmax", provider_reference_id="ref-B", order_id="order-B"
    )

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v1, ao_pagamento_aprovado) is True
        assert processar_envelope(v2, ao_pagamento_aprovado) is True

    assert mock_enviar.call_count == 2
    assert (
        EnvioRegistrado.objects.filter(tipo="boas_vindas", canal="email").count() == 2
    )


def test_aprovado_mesmo_fato_em_sites_diferentes_gera_dois_envios():
    """[INV-P11] `provider_reference_id` é opaco e vem do PROVEDOR: nada
    garante que ele seja único ENTRE sites (tenants) desta plataforma. Sem o
    site escopando a chave, o segundo site seria descartado como duplicado do
    primeiro — e a pessoa que pagou no site B nunca receberia confirmação."""
    referencia = f"ref-colisao-{uuid4().hex}"
    do_site_a = _envelope_aprovado_v2(
        provider="appmax",
        provider_reference_id=referencia,
        order_id="order-site-a",
        site_id="site-a",
    )
    do_site_b = _envelope_aprovado_v2(
        provider="appmax",
        provider_reference_id=referencia,
        order_id="order-site-b",
        site_id="site-b",
    )

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(do_site_a, ao_pagamento_aprovado) is True
        assert processar_envelope(do_site_b, ao_pagamento_aprovado) is True

    assert mock_enviar.call_count == 2
    assert (
        EnvioRegistrado.objects.filter(
            order_id="order-site-a", site_id="site-a"
        ).count()
        == 1
    )
    assert (
        EnvioRegistrado.objects.filter(
            order_id="order-site-b", site_id="site-b"
        ).count()
        == 1
    )


# --------------------------------------------------------------------------
# pagamento.recusado — a ponte É OUTRA: só `payment_id`
# --------------------------------------------------------------------------


def test_recusado_v1_sozinho_processa():
    envelope = _envelope_recusado_v1(
        payment_id="pay-solo-1", order_id="order-rec-v1-solo"
    )
    with patch("apps.eventos.handlers.enviar_notificacao"):
        assert processar_envelope(envelope, ao_pagamento_recusado) is True
    assert EnvioRegistrado.objects.filter(order_id="order-rec-v1-solo").count() == 1


def test_recusado_v2_sozinho_processa():
    """Mesmo vermelho do aprovado: `platform_site_id` em vez de `site_id`."""
    envelope = _envelope_recusado_v2(
        payment_id="pay-solo-2", order_id="order-rec-v2-solo"
    )
    with patch("apps.eventos.handlers.enviar_notificacao"):
        assert processar_envelope(envelope, ao_pagamento_recusado) is True
    assert EnvioRegistrado.objects.filter(order_id="order-rec-v2-solo").count() == 1


def test_recusado_v1_seguido_de_v2_do_mesmo_fato_gera_um_unico_envio():
    """A prova da correção ao brief: o v2 desta tentativa traz um `provider` e
    um `provider_reference_id` que NÃO aparecem no v1 nenhum — e mesmo assim
    precisa deduplicar, porque a ponte do recusado é só `payment_id`."""
    payment_id = f"pay-{uuid4().hex}"
    v1 = _envelope_recusado_v1(payment_id=payment_id, order_id="order-rec-v1-c")
    v2 = _envelope_recusado_v2(
        payment_id=payment_id,
        order_id="order-rec-v2-c",
        provider="appmax",
        provider_reference_id="ref-nao-existia-no-v1",
    )

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v1, ao_pagamento_recusado) is True
        assert processar_envelope(v2, ao_pagamento_recusado) is False

    assert mock_enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(
            tipo="recuperacao_recusado", canal="email"
        ).count()
        == 1
    )
    assert EnvioRegistrado.objects.filter(order_id="order-rec-v2-c").count() == 0


def test_recusado_ordem_invertida_v2_seguido_de_v1_do_mesmo_fato_gera_um_unico_envio():
    payment_id = f"pay-{uuid4().hex}"
    v2 = _envelope_recusado_v2(payment_id=payment_id, order_id="order-rec-v2-d")
    v1 = _envelope_recusado_v1(payment_id=payment_id, order_id="order-rec-v1-d")

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v2, ao_pagamento_recusado) is True
        assert processar_envelope(v1, ao_pagamento_recusado) is False

    assert mock_enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(
            tipo="recuperacao_recusado", canal="email"
        ).count()
        == 1
    )


def test_recusado_payment_id_diferente_nao_colide():
    v1 = _envelope_recusado_v1(payment_id="pay-X", order_id="order-rec-X")
    v2 = _envelope_recusado_v2(payment_id="pay-Y", order_id="order-rec-Y")

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(v1, ao_pagamento_recusado) is True
        assert processar_envelope(v2, ao_pagamento_recusado) is True

    assert mock_enviar.call_count == 2


def test_recusado_mesmo_payment_id_em_sites_diferentes_gera_dois_envios():
    """[INV-P11] Mesma fronteira de site para a ponte do recusado: um
    `payment_id` que colidisse entre dois sites não pode calar o segundo
    aviso de recusa."""
    payment_id = f"pay-colisao-{uuid4().hex}"
    do_site_a = _envelope_recusado_v1(
        payment_id=payment_id, order_id="order-rec-site-a", site_id="site-a"
    )
    do_site_b = _envelope_recusado_v1(
        payment_id=payment_id, order_id="order-rec-site-b", site_id="site-b"
    )

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        assert processar_envelope(do_site_a, ao_pagamento_recusado) is True
        assert processar_envelope(do_site_b, ao_pagamento_recusado) is True

    assert mock_enviar.call_count == 2


# --------------------------------------------------------------------------
# Concorrência real: dois workers, Redis de verdade, mesma corrida do banco
# --------------------------------------------------------------------------
# Redis vem de REDIS_STREAMS_URL, igual a `tests/test_reentrega_pel.py` — fail,
# não skip, se a env faltar (§5.6: pular aqui seria um verde falso).


@pytest.fixture()
def r():
    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        pytest.fail(
            "REDIS_STREAMS_URL ausente — este teste exige Redis real "
            "(sessão: export REDIS_STREAMS_URL=<a da bancada>)"
        )
    cliente = redis.from_url(url)
    cliente.ping()
    yield cliente
    cliente.close()


@pytest.fixture()
def stream(r):
    nome = f"eventos.teste-dedup-versoes.{uuid4().hex}"
    yield nome
    r.delete(nome, f"{nome}.dlq")


def test_concorrencia_real_v1_e_v2_do_mesmo_fato_produzem_um_unico_envio(r, stream):
    """Dois workers reais, cada um com sua própria mensagem do MESMO Redis
    Stream (uma v1, uma v2 do MESMO fato) — e as duas chamadas a
    `_processar_e_ack` disparadas ao mesmo tempo por `threading.Barrier`. O que
    decide quem grava não é a ordem de agendamento: é a UniqueConstraint do
    Postgres sob corrida de verdade, a mesma trava provada sem Redis acima."""
    referencia = f"mp-{uuid4().hex}"
    v1 = _envelope_aprovado_v1(mp_payment_id=referencia, order_id="order-conc-v1")
    v2 = _envelope_aprovado_v2(
        provider="mercadopago",
        provider_reference_id=referencia,
        order_id="order-conc-v2",
    )

    r.xadd(stream, {"json": json.dumps(v1)})
    r.xadd(stream, {"json": json.dumps(v2)})
    r.xgroup_create(stream, GRUPO, id="0")
    resp = r.xreadgroup(GRUPO, "worker-teste", {stream: ">"}, count=2)
    mensagens = resp[0][1]
    assert len(mensagens) == 2

    barreira = threading.Barrier(2)
    erros: list[Exception] = []

    def processar(msg_id, campos):
        try:
            barreira.wait(timeout=5)
            consume_eventos._processar_e_ack(
                r, stream, ao_pagamento_aprovado, msg_id, campos
            )
        except Exception as exc:  # pragma: no cover - não engolir falha da thread
            erros.append(exc)
        finally:
            connection.close()

    with patch("apps.eventos.handlers.enviar_notificacao") as mock_enviar:
        threads = [
            threading.Thread(target=processar, args=(msg_id, campos))
            for msg_id, campos in mensagens
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not erros, erros
    assert mock_enviar.call_count == 1
    assert (
        EnvioRegistrado.objects.filter(tipo="boas_vindas", canal="email").count() == 1
    )
    assert (
        FatoDeProvedorVisto.objects.filter(
            evento="pagamento.aprovado", chave=f"site-abc:mercadopago:{referencia}"
        ).count()
        == 1
    )
    # as duas mensagens saíram do PEL — vencedora e perdedora são ACKadas
    assert r.xpending(stream, GRUPO)["pending"] == 0
