import uuid

import pytest
from django.core.management import call_command

from apps.core.handlers import ao_pagamento_aprovado, ao_pedido_criado, ao_quiz_completado
from apps.core.models import Lead, Oportunidade, TimelineEvent


pytestmark = pytest.mark.django_db


@pytest.fixture
def autorizado(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-oferta")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-oferta")
    return {"HTTP_AUTHORIZATION": "Bearer admin-oferta"}


def quiz(email="maria@gmail.com", slug="crivo"):
    ao_quiz_completado(str(uuid.uuid4()), {
        "site_id": "a", "quiz_slug": slug, "result_key": "iniciante",
        "lead": {"email": email, "name": "Maria"},
    })


def pedido(email="maria@gmail.com"):
    ao_pedido_criado(str(uuid.uuid4()), {
        "site_id": "a", "order_id": "ped-1", "amount_cents": 990,
        "customer": {"email": email},
    })


def pagamento(email="maria@gmail.com"):
    ao_pagamento_aprovado(str(uuid.uuid4()), {
        "site_id": "a", "order_id": "ped-1", "payment_id": "pay-1", "amount_cents": 990,
        "method": "pix", "mp_payment_id": "mp-1", "customer": {"email": email},
    })


def test_quiz_abre_oferta_pedido_negocia_e_pagamento_vira_venda():
    quiz()
    quiz()
    oferta = Oportunidade.objects.get(fonte_tipo="quiz")
    assert oferta.etapa == "nova"
    assert "crivo" in oferta.passo_descricao and "iniciante" in oferta.passo_descricao
    pedido()
    oferta.refresh_from_db()
    assert oferta.etapa == "negociacao"
    assert "ped-1" in oferta.passo_descricao
    pagamento()
    oferta.refresh_from_db()
    assert oferta.etapa == "ganha" and oferta.encerrada
    assert Oportunidade.objects.filter(fonte_tipo="quiz").count() == 1


def test_backfill_abre_oferta_para_quem_ja_respondeu_e_respeita_compra(capsys):
    pagou = Lead.objects.create(site_id="a", email="pagou@gmail.com", source="quiz:crivo")
    TimelineEvent.objects.create(lead=pagou, event="quiz.completado", payload={"quiz_slug": "crivo"})
    TimelineEvent.objects.create(lead=pagou, event="pagamento.aprovado", payload={
        "site_id": "a", "order_id": "ped-antigo", "amount_cents": 990,
    })
    Lead.objects.create(site_id="a", email="parado@gmail.com", source="quiz:cura")
    Lead.objects.create(site_id="a", email="aluno@gmail.com", source="escola")

    call_command("backfill_ofertas_quiz")
    call_command("backfill_ofertas_quiz")

    ofertas = Oportunidade.objects.filter(fonte_tipo="quiz")
    assert ofertas.count() == 2
    assert ofertas.get(lead=pagou).etapa == "ganha"
    assert ofertas.get(lead__email="parado@gmail.com").fonte_referencia_id == "oferta:cura"
    assert "criadas: 0" in capsys.readouterr().out.strip().splitlines()[-1]


def test_contatos_e_quadro_escondem_testes(client, autorizado):
    quiz()
    quiz("teste@example.com")
    lista = client.get("/api/leads/leads", {"origem": "quiz"}, **autorizado).json()
    assert [item["email"] for item in lista["itens"]] == ["maria@gmail.com"]
    resumo = client.get("/api/leads/crm", **autorizado).json()["resumo"]
    assert resumo["contatos"] == 1
    assert resumo["sem_oportunidade"] == 0
    assert resumo["abertas"] == 1
