# tests/test_inv_leads_dedup_entre_versoes.py  # [RECEITA:R5 v1]
# Nome do arquivo = o invariante da célula: o MESMO pagamento, chegando como
# pagamento.aprovado/recusado v1 e depois como v2 (RITOS.md §3, migração em
# voo), gera UMA única entrada de timeline — não uma por versão.
#
# A identidade lógica do fato vem de `x-ponte-do-v1` em cada contrato, NÃO do
# brief desta tarefa (que erra para o recusado): pagamento.aprovado.v2 e
# pagamento.recusado.v2 concordam em ter `provider`/`provider_reference_id`,
# mas só o aprovado usa esse par para deduplicar. O recusado nunca teve
# referência do provedor no v1 — ali quem atravessa as duas versões é
# `payment_id` (contracts/eventos/pagamento.recusado.v2.json, `x-ponte-do-v1`).
import threading
import uuid

import pytest
from django.db import connection

from apps.core.handlers import (
    ao_pagamento_aprovado,
    ao_pagamento_recusado,
    processar_envelope,
)
from apps.core.models import FatoDePagamentoProcessado, Lead, TimelineEvent

pytestmark = pytest.mark.django_db


def _envelope(evento: str, version: int, data: dict) -> dict:
    return {
        "event": evento,
        "version": version,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-20T12:00:00Z",
        "data": data,
    }


def _aprovado_v1(
    mp_payment_id: str,
    order_id: str = "ord-1",
    payment_id: str = "",
    site_id: str = "site-a",
) -> dict:
    return _envelope(
        "pagamento.aprovado",
        1,
        {
            "site_id": site_id,
            "payment_id": payment_id or f"pay-{order_id}",
            "order_id": order_id,
            "amount_cents": 990,
            "method": "pix",
            "mp_payment_id": mp_payment_id,
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    )


def _aprovado_v2(
    provider: str,
    provider_reference_id: str,
    order_id: str = "ord-1",
    payment_id: str = "",
    site_id: str = "site-a",
) -> dict:
    return _envelope(
        "pagamento.aprovado",
        2,
        {
            "platform_site_id": site_id,
            "payment_id": payment_id or f"pay-{order_id}",
            "order_id": order_id,
            "amount_cents": 990,
            "method": "pix",
            "provider": provider,
            "provider_reference_id": provider_reference_id,
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    )


def _recusado_v1(
    payment_id: str, order_id: str = "ord-2", site_id: str = "site-a"
) -> dict:
    return _envelope(
        "pagamento.recusado",
        1,
        {
            "site_id": site_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount_cents": 990,
            "method": "card",
            "reason_code": "cc_rejected_insufficient_amount",
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    )


def _recusado_v2(
    payment_id: str, order_id: str = "ord-2", site_id: str = "site-a"
) -> dict:
    return _envelope(
        "pagamento.recusado",
        2,
        {
            "platform_site_id": site_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "amount_cents": 990,
            "method": "card",
            "provider": "mercadopago",
            "provider_reference_id": "mp-ref-999",
            "reason_code": "cc_rejected_insufficient_amount",
            "customer": {"email": "ana@example.com", "name": "Ana"},
        },
    )


# ---------------------------------------------------------------- aprovado --


def test_aprovado_v1_sozinho_gera_uma_entrada():
    processar_envelope(_aprovado_v1("mp-1"), ao_pagamento_aprovado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )


def test_aprovado_v2_sozinho_gera_uma_entrada():
    processar_envelope(_aprovado_v2("mercadopago", "mp-2"), ao_pagamento_aprovado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )


def test_aprovado_v1_seguido_de_v2_do_mesmo_fato_gera_uma_unica_entrada():
    """v1 chega primeiro (mp_payment_id="mp-3"); o mesmo pagamento chega depois
    como v2 (provider="mercadopago", provider_reference_id="mp-3" — a mesma
    equivalência que o contrato declara em `x-ponte-do-v1`). `payment_id`
    DIFERE entre as duas entregas de propósito: é local à célula pagamentos e
    o próprio contrato diz que não serve para deduplicar — se o código
    confundisse as duas coisas, esta seria a prova."""
    processar_envelope(
        _aprovado_v1("mp-3", payment_id="pay-local-v1"), ao_pagamento_aprovado
    )
    processar_envelope(
        _aprovado_v2("mercadopago", "mp-3", payment_id="pay-local-v2"),
        ao_pagamento_aprovado,
    )

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )


def test_aprovado_ordem_invertida_v2_seguido_de_v1_do_mesmo_fato_gera_uma_unica_entrada():
    processar_envelope(
        _aprovado_v2("mercadopago", "mp-4", payment_id="pay-local-v2"),
        ao_pagamento_aprovado,
    )
    processar_envelope(
        _aprovado_v1("mp-4", payment_id="pay-local-v1"), ao_pagamento_aprovado
    )

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )


def test_aprovado_payment_id_igual_nao_junta_fatos_diferentes():
    """O espelho do teste anterior: dois pagamentos DE VERDADE diferentes que,
    por coincidência da célula pagamentos, compartilham o mesmo `payment_id`
    local não podem ser confundidos — a identidade é o par
    provider/provider_reference_id, nunca payment_id."""
    processar_envelope(
        _aprovado_v1("mp-7a", order_id="ord-7a", payment_id="pay-coincidente"),
        ao_pagamento_aprovado,
    )
    processar_envelope(
        _aprovado_v2(
            "mercadopago", "mp-7b", order_id="ord-7b", payment_id="pay-coincidente"
        ),
        ao_pagamento_aprovado,
    )

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 2
    )


def test_aprovado_reentrega_do_mesmo_evento_gera_uma_unica_entrada():
    envelope = _aprovado_v2("mercadopago", "mp-5")

    processar_envelope(envelope, ao_pagamento_aprovado)
    processar_envelope(envelope, ao_pagamento_aprovado)  # reentrega — mesmo event_id

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )


def test_aprovado_fatos_diferentes_nao_sao_confundidos():
    """Controle negativo: dois pagamentos DE VERDADE diferentes não podem colidir
    na mesma chave só por serem do mesmo provedor."""
    processar_envelope(_aprovado_v1("mp-6a", order_id="ord-6a"), ao_pagamento_aprovado)
    processar_envelope(
        _aprovado_v2("mercadopago", "mp-6b", order_id="ord-6b"), ao_pagamento_aprovado
    )

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 2
    )


def test_aprovado_site_diferente_e_um_fato_diferente_inv_p11():
    """[INV-P11] A identidade do fato é escopada pelo site, não só o par
    provider/provider_reference_id. Um aviso com o site ERRADO (bug do
    publicador, ou mensagem injetada) não pode consumir a chave do aviso
    LEGÍTIMO: se consumisse, o aviso certo chegaria depois, bateria na
    unicidade e seria descartado como duplicado, sem erro em lugar nenhum, e a
    timeline do site certo nunca receberia o fato. Mesmo `provider` mais
    `provider_reference_id`, dois sites diferentes são dois fatos."""
    processar_envelope(
        _aprovado_v2("mercadopago", "mp-p11", site_id="site-errado"),
        ao_pagamento_aprovado,
    )
    processar_envelope(
        _aprovado_v2("mercadopago", "mp-p11", site_id="site-certo"),
        ao_pagamento_aprovado,
    )

    lead_errado = Lead.objects.get(site_id="site-errado", email="ana@example.com")
    lead_certo = Lead.objects.get(site_id="site-certo", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(
            lead=lead_errado, event="pagamento.aprovado"
        ).count()
        == 1
    )
    assert (
        TimelineEvent.objects.filter(
            lead=lead_certo, event="pagamento.aprovado"
        ).count()
        == 1
    )


# ---------------------------------------------------------------- recusado --


def test_recusado_v1_sozinho_gera_uma_entrada():
    processar_envelope(_recusado_v1("pay-r1"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 1
    )


def test_recusado_v2_sozinho_gera_uma_entrada():
    processar_envelope(_recusado_v2("pay-r2"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 1
    )


def test_recusado_v1_seguido_de_v2_do_mesmo_fato_gera_uma_unica_entrada():
    """O recusado v1 NUNCA teve referência do provedor (nem como mp_payment_id):
    a chave que atravessa as duas versões é `payment_id`
    (contracts/eventos/pagamento.recusado.v2.json, `x-ponte-do-v1`) — não o par
    provider/provider_reference_id do aprovado."""
    processar_envelope(_recusado_v1("pay-r3"), ao_pagamento_recusado)
    processar_envelope(_recusado_v2("pay-r3"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 1
    )


def test_recusado_ordem_invertida_v2_seguido_de_v1_do_mesmo_fato_gera_uma_unica_entrada():
    processar_envelope(_recusado_v2("pay-r4"), ao_pagamento_recusado)
    processar_envelope(_recusado_v1("pay-r4"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 1
    )


def test_recusado_reentrega_do_mesmo_evento_gera_uma_unica_entrada():
    envelope = _recusado_v2("pay-r5")

    processar_envelope(envelope, ao_pagamento_recusado)
    processar_envelope(envelope, ao_pagamento_recusado)  # reentrega — mesmo event_id

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 1
    )


def test_recusado_fatos_diferentes_nao_sao_confundidos():
    processar_envelope(_recusado_v1("pay-r6a"), ao_pagamento_recusado)
    processar_envelope(_recusado_v2("pay-r6b"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 2
    )


def test_recusado_provider_reference_id_igual_nao_junta_pagamentos_diferentes():
    """O espelho do teste do aprovado: duas tentativas recusadas DE VERDADE
    diferentes, ambas em v2 e com o MESMO `provider_reference_id` (todo
    `_recusado_v2` desta suíte usa o literal "mp-ref-999"), não podem ser
    confundidas — a identidade da recusa é `payment_id`, nunca o par do
    provedor, que só existe a partir do v2."""
    processar_envelope(_recusado_v2("pay-r7a"), ao_pagamento_recusado)
    processar_envelope(_recusado_v2("pay-r7b"), ao_pagamento_recusado)

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.recusado").count() == 2
    )


def test_recusado_site_diferente_e_um_fato_diferente_inv_p11():
    """[INV-P11] Mesmo `payment_id`, dois `platform_site_id` diferentes são
    dois fatos. Espelho de `test_aprovado_site_diferente_e_um_fato_diferente_inv_p11`
    para o evento cuja identidade é só `payment_id`."""
    processar_envelope(
        _recusado_v2("pay-p11", site_id="site-errado"), ao_pagamento_recusado
    )
    processar_envelope(
        _recusado_v2("pay-p11", site_id="site-certo"), ao_pagamento_recusado
    )

    lead_errado = Lead.objects.get(site_id="site-errado", email="ana@example.com")
    lead_certo = Lead.objects.get(site_id="site-certo", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(
            lead=lead_errado, event="pagamento.recusado"
        ).count()
        == 1
    )
    assert (
        TimelineEvent.objects.filter(
            lead=lead_certo, event="pagamento.recusado"
        ).count()
        == 1
    )


# -------------------------------------------------------------- concorrência --


@pytest.mark.django_db(transaction=True)
def test_concorrencia_real_v1_e_v2_do_mesmo_fato_batendo_ao_mesmo_tempo_gera_uma_entrada():
    """Duas threads, cada uma com a sua própria conexão real ao Postgres,
    tentando gravar o MESMO fato (v1 e v2) no mesmo instante. Só a constraint
    do banco em (evento, chave) — não um `if` da aplicação, que perderia a
    corrida — garante que a segunda tentativa recua."""
    barreira = threading.Barrier(2)
    erros = []

    def _rodar(envelope):
        try:
            barreira.wait(timeout=5)
            processar_envelope(envelope, ao_pagamento_aprovado)
        except Exception as exc:  # pragma: no cover - não engolir falha da thread
            erros.append(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=_rodar, args=(_aprovado_v1("mp-conc", payment_id="pay-conc-v1"),)
        ),
        threading.Thread(
            target=_rodar,
            args=(_aprovado_v2("mercadopago", "mp-conc", payment_id="pay-conc-v2"),),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros, erros
    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert (
        TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado").count() == 1
    )
    assert (
        FatoDePagamentoProcessado.objects.filter(evento="pagamento.aprovado").count()
        == 1
    )
