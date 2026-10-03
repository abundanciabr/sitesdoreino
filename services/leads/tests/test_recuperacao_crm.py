import uuid
import json

import pytest
from django.core.management import call_command

from apps.core.handlers import (
    ao_pagamento_aprovado, ao_pagamento_recusado, ao_pix_expirado,
    ao_reversao_confirmada,
    processar_envelope,
)
from apps.core.models import Lead, Oportunidade, ReversaoDePagamento, TimelineEvent


pytestmark = pytest.mark.django_db


def _dados(pedido="pedido-1", site="site-a"):
    return {
        "site_id": site, "order_id": pedido, "payment_id": "pay-1",
        "amount_cents": 990, "method": "card",
        "reason_code": "recusado",
        "customer": {"email": "ana@example.com", "name": "Ana"},
    }


def _evento(nome, handler, dados):
    return processar_envelope(
        {"event_id": str(uuid.uuid4()), "data": dados}, handler
    )


def test_recusa_repetida_e_aprovacao_fecham_mesma_oportunidade():
    dados = _dados()
    _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    assert Oportunidade.objects.count() == 1
    aprovado = {**dados, "mp_payment_id": "mp-1"}
    _evento("pagamento.aprovado", ao_pagamento_aprovado, aprovado)
    oportunidade = Oportunidade.objects.get()
    assert oportunidade.etapa == "ganha"
    assert oportunidade.historico.count() == 2


def test_aprovado_antes_do_pix_vencido_nao_conta_recuperacao_falsa():
    dados = _dados()
    _evento("pagamento.aprovado", ao_pagamento_aprovado,
            {**dados, "mp_payment_id": "mp-2"})
    _evento("pix.expirado", ao_pix_expirado, dados)
    assert Oportunidade.objects.count() == 0


def test_mesmo_pedido_em_outro_site_nao_fecha_oportunidade():
    _evento("pagamento.recusado", ao_pagamento_recusado, _dados())
    _evento("pagamento.aprovado", ao_pagamento_aprovado,
            {**_dados(site="site-b"), "mp_payment_id": "mp-3"})
    assert Oportunidade.objects.get().etapa == "nova"


def test_backfill_pode_rodar_duas_vezes_sem_duplicar():
    lead = Lead.objects.create(site_id="site-a", email="ana@example.com")
    dados = _dados()
    TimelineEvent.objects.create(lead=lead, event="pagamento.recusado", payload=dados)
    TimelineEvent.objects.create(lead=lead, event="pagamento.aprovado", payload=dados)
    call_command("backfill_recuperacao")
    call_command("backfill_recuperacao")
    assert Oportunidade.objects.count() == 1
    assert Oportunidade.objects.get().etapa == "ganha"


def test_backfill_aprovacao_anterior_a_falha_nao_conta_recuperacao():
    lead = Lead.objects.create(site_id="site-a", email="ana@example.com")
    dados = _dados()
    TimelineEvent.objects.create(lead=lead, event="pagamento.aprovado", payload=dados)
    TimelineEvent.objects.create(lead=lead, event="pagamento.recusado", payload=dados)
    call_command("backfill_recuperacao")
    assert Oportunidade.objects.count() == 0


def test_reversao_tira_compra_das_recuperadas_e_registra_timeline():
    dados = _dados()
    _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    _evento("pagamento.aprovado", ao_pagamento_aprovado,
            {**dados, "mp_payment_id": "mp-1"})
    reversao = {
        "platform_site_id": "site-a", "order_id": "pedido-1",
        "provider": "appmax", "provider_reference_id": "ap-1", "motivo": "estorno",
    }
    _evento("pagamento.reversao_confirmada", ao_reversao_confirmada, reversao)
    assert Oportunidade.objects.get().etapa == "desqualificada"
    assert ReversaoDePagamento.objects.count() == 1
    assert TimelineEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 1


def test_reversao_sem_customer_antes_da_aprovacao_e_aplicada_depois():
    dados = _dados()
    _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    _evento("pagamento.reversao_confirmada", ao_reversao_confirmada, {
        "platform_site_id": "site-a", "order_id": "pedido-1",
        "provider": "appmax", "provider_reference_id": "ap-1", "motivo": "estorno",
    })
    assert TimelineEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 0
    _evento("pagamento.aprovado", ao_pagamento_aprovado,
            {**dados, "mp_payment_id": "mp-1"})
    assert Oportunidade.objects.get().etapa == "desqualificada"
    assert TimelineEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 1


def test_backfill_reversao_existente_nao_duplica_timeline():
    lead = Lead.objects.create(site_id="site-a", email="ana@example.com")
    dados = _dados()
    reversao = {"platform_site_id": "site-a", "order_id": "pedido-1",
                "provider": "appmax", "provider_reference_id": "ap-1",
                "motivo": "estorno"}
    TimelineEvent.objects.create(lead=lead, event="pagamento.recusado", payload=dados)
    TimelineEvent.objects.create(lead=lead, event="pagamento.aprovado", payload=dados)
    TimelineEvent.objects.create(lead=lead, event="pagamento.reversao_confirmada",
                                 payload=reversao)
    call_command("backfill_recuperacao")
    call_command("backfill_recuperacao")
    assert Oportunidade.objects.get().etapa == "desqualificada"
    assert TimelineEvent.objects.filter(event="pagamento.reversao_confirmada").count() == 1


def test_api_admin_lista_atualiza_e_isola_token(client, settings, monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin")
    settings.TOKENS_ACEITOS.add("admin")
    dados = _dados()
    dados["customer"] = {"email": "ana@cliente.com", "name": "Ana"}
    _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    caminho = "/api/leads/crm"
    cabecalho = {"HTTP_AUTHORIZATION": "Bearer admin"}
    resposta = client.get(caminho, **cabecalho)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["itens"][0]["contato"]["email"] == "ana@cliente.com"
    assert corpo["itens"][0]["registro_de_teste"] is False
    assert corpo["resumo"]["abertas"] == 1
    identificador = corpo["itens"][0]["id"]
    atualizado = client.patch(
        f"{caminho}/{identificador}",
        data=json.dumps({"autor_id": "davi", "etapa": "qualificada",
                         "titular_id": "equipe-vendas"}),
        content_type="application/json", **cabecalho,
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["etapa"] == "qualificada"
    assert atualizado.json()["titular"]["id"] == "equipe-vendas"
    assert atualizado.json()["historico"][-1]["autor_id"] == "davi"
    ganho_manual = client.post(
        f"{caminho}/{identificador}/close",
        data=json.dumps({"autor_id": "davi", "resultado": "ganha",
                         "motivo": "teste", "evidencia": "teste"}),
        content_type="application/json", **cabecalho,
    )
    assert ganho_manual.status_code == 422
    recusado = client.get(caminho, HTTP_AUTHORIZATION="Bearer outro")
    assert recusado.status_code in (401, 403)


def test_crm_oculta_testes_explicitos_por_padrao_sem_perder_contagem(
    client, settings, monkeypatch
):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin")
    settings.TOKENS_ACEITOS.add("admin")

    casos = [
        ("cliente@dominio.com", "Cliente Real", "real"),
        ("sandbox@dominio.com", "Teste Sandbox Appmax", "nome"),
        ("pessoa@example.com", "Pessoa", "email"),
        ("outra@dominio.com", "Pessoa Outra", "origem"),
    ]
    for indice, (email, nome, _) in enumerate(casos):
        dados = _dados(pedido=f"pedido-{indice}")
        dados["payment_id"] = f"pay-{indice}"
        dados["customer"] = {"email": email, "name": nome}
        _evento("pagamento.recusado", ao_pagamento_recusado, dados)
    Lead.objects.filter(email="outra@dominio.com").update(source="sandbox-campanha")

    caminho = "/api/leads/crm"
    cabecalho = {"HTTP_AUTHORIZATION": "Bearer admin"}
    padrao = client.get(caminho, **cabecalho)
    assert padrao.status_code == 200
    assert padrao.json()["total"] == 1
    assert padrao.json()["resumo"] == {
        "contatos": 4, "eventos": 4, "testes": 3, "abertas": 1,
        "atrasadas": 0, "ganhas": 0, "recuperadas": 0, "perdidas": 0,
    }
    assert padrao.json()["itens"][0]["registro_de_teste"] is False

    todos = client.get(f"{caminho}?testes=mostrar", **cabecalho)
    assert todos.json()["total"] == 4
    assert todos.json()["resumo"]["abertas"] == 4
    assert sum(item["registro_de_teste"] for item in todos.json()["itens"]) == 3

    somente = client.get(f"{caminho}?testes=somente", **cabecalho)
    assert somente.json()["total"] == 3
    assert somente.json()["resumo"]["abertas"] == 3
    assert all(item["registro_de_teste"] for item in somente.json()["itens"])

    invalido = client.get(f"{caminho}?testes=qualquer", **cabecalho)
    assert invalido.status_code == 422
