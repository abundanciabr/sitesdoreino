import uuid

import pytest

from apps.core.handlers import ao_pagamento_recusado
from apps.core.models import Lead, Oportunidade, TimelineEvent


pytestmark = pytest.mark.django_db


@pytest.fixture
def autorizado(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-quiz")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-quiz")
    return {"HTTP_AUTHORIZATION": "Bearer admin-quiz"}


def evento(lead, nome, payload=None):
    return TimelineEvent.objects.create(lead=lead, event=nome, payload=payload or {})


def test_lista_e_ficha_separam_captura_do_quiz_de_cadastro_e_compra(client, autorizado):
    aluno = Lead.objects.create(site_id="a", email="aluno@dominio.com", source="escola")
    evento(aluno, "pedido.criado")
    evento(aluno, "pagamento.aprovado")
    origem = Lead.objects.create(site_id="a", email="origem@dominio.com", source="quiz:crivo")
    historico = Lead.objects.create(site_id="a", email="hist@dominio.com", source="checkout")
    evento(historico, "quiz.completado")
    evento(historico, "quiz.completado")
    captura = Lead.objects.create(site_id="a", email="captura@dominio.com", source="escola")
    evento(captura, "lead.upsert", {"source": "quiz-crivo"})
    Lead.objects.create(site_id="b", email="hist@dominio.com", source="escola")

    resposta = client.get("/api/leads/leads", {"origem": "quiz", "por_pagina": 2}, **autorizado)
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 3
    assert len(resposta.json()["itens"]) == 2
    assert resposta.json()["tem_mais"] is True
    encontrados = client.get("/api/leads/leads", {"origem": "quiz"}, **autorizado).json()
    assert {item["id"] for item in encontrados["itens"]} == {
        str(origem.pk), str(historico.pk), str(captura.pk)
    }
    assert client.get(f"/api/leads/leads/{aluno.pk}", {"origem": "quiz"}, **autorizado).status_code == 404
    assert client.get(f"/api/leads/leads/{historico.pk}", {"origem": "quiz"}, **autorizado).status_code == 200
    # A memória do serviço permanece disponível para seus consumidores internos.
    assert client.get(f"/api/leads/leads/{aluno.pk}", **autorizado).status_code == 200
    assert Lead.objects.count() == 5


def test_crm_conta_so_quiz_e_nao_abre_oportunidade_de_cadastro_direto(client, autorizado):
    for indice, origem in enumerate(("quiz:crivo", "escola")):
        email = f"pessoa{indice}@dominio.com"
        Lead.objects.create(site_id="a", email=email, source=origem)
        ao_pagamento_recusado(str(uuid.uuid4()), {
            "site_id": "a", "order_id": f"pedido-{indice}", "payment_id": f"p-{indice}",
            "customer": {"email": email}, "method": "card", "amount_cents": 990,
            "reason_code": "recusado",
        })
    resposta = client.get("/api/leads/crm", {"testes": "mostrar"}, **autorizado)
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1
    assert resposta.json()["resumo"]["contatos"] == 1
    assert resposta.json()["resumo"]["sem_oportunidade"] == 0
    assert resposta.json()["resumo"]["abertas"] == 1
    fora = Oportunidade.objects.get(lead__source="escola")
    assert client.get(f"/api/leads/crm/{fora.pk}", **autorizado).status_code == 404
    assert client.post(f"/api/leads/crm/{fora.pk}/history", data='{"descricao":"nota"}',
                       content_type="application/json", **autorizado).status_code == 404
    assert fora.historico.count() == 1
    assert Oportunidade.objects.count() == 2
