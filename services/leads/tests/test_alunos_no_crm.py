import json

import pytest

from apps.core.alunos import sincronizar_matricula
from apps.core.models import Lead, Oportunidade, TimelineEvent

pytestmark = pytest.mark.django_db


def matricula(**dados):
    return {
        "id": "mat-1",
        "site_id": "escola-a",
        "email": "marina@dominio.com",
        "nome_completo": "Marina",
        "whatsapp": "11987654321",
        "status": "ativa",
        "product_id": "curso-atual",
        "turma": "Turma 1",
        "origem": "liberado",
        "criada_em": "2026-08-01T10:00:00Z",
        **dados,
    }


@pytest.fixture
def painel(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-alunos")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-alunos")
    return {"HTTP_AUTHORIZATION": "Bearer admin-alunos"}


def test_duas_matriculas_e_repeticao_preservam_um_contato_e_uma_oportunidade():
    sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(id="mat-2", product_id="curso-2"))
    sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(id="mat-2", product_id="curso-2"))
    assert Lead.objects.count() == Oportunidade.objects.count() == 1
    assert TimelineEvent.objects.count() == 2
    oportunidade = Oportunidade.objects.get()
    assert oportunidade.fonte_referencia_id == "proximo-curso"
    assert oportunidade.historico.count() == 1
    assert oportunidade.etapa == "nova"
    assert oportunidade.compras.count() == 0


def test_quiz_existente_mantem_id_origem_consentimento_e_historico():
    lead = Lead.objects.create(
        site_id="escola-a",
        email="Marina@dominio.com",
        source="quiz:crivo",
        tags=["interessada"],
        consent={"whatsapp": False},
    )
    TimelineEvent.objects.create(lead=lead, event="quiz.completado", payload={})
    resultado = sincronizar_matricula(matricula(email=" MARINA@dominio.com "))
    assert resultado["contato_id"] == str(lead.pk) and not resultado["contato_criado"]
    lead.refresh_from_db()
    assert lead.source == "quiz:crivo" and lead.consent == {"whatsapp": False}
    assert lead.tags == ["interessada", "aluno"]
    assert lead.timeline.filter(event="quiz.completado").count() == 1


def test_mesma_pessoa_em_escolas_distintas_tem_contatos_distintos():
    sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(site_id="escola-b"))
    assert Lead.objects.count() == Oportunidade.objects.count() == 2


@pytest.mark.parametrize("status", ["aguardando", "recusada"])
def test_pedido_de_entrada_sem_matricula_nao_vira_aluno(status):
    assert sincronizar_matricula(matricula(status=status))["ignorada"]
    assert Lead.objects.count() == Oportunidade.objects.count() == 0


def test_situacao_nova_nao_reabre_oportunidade_encerrada():
    sincronizar_matricula(matricula())
    oportunidade = Oportunidade.objects.get()
    from django.utils import timezone

    oportunidade.etapa = "desqualificada"
    oportunidade.desfecho_encerrada_em = timezone.now()
    oportunidade.save()
    sincronizar_matricula(matricula(status="encerrada"))
    oportunidade.refresh_from_db()
    assert oportunidade.encerrada and oportunidade.etapa == "desqualificada"
    assert Oportunidade.objects.count() == 1


def test_aluno_aparece_na_lista_ficha_quadro_e_busca_do_crm(client, painel):
    resultado = sincronizar_matricula(matricula())
    compra_sem_matricula = Lead.objects.create(
        site_id="escola-a", email="compra@dominio.com", source="checkout"
    )
    resposta = client.get("/api/leads/leads", {"origem": "crm"}, **painel).json()
    assert resposta["total"] == 1
    assert resposta["itens"][0]["id"] == resultado["contato_id"]
    ficha = client.get(
        "/api/leads/leads/" + resultado["contato_id"], {"origem": "crm"}, **painel
    )
    assert (
        ficha.status_code == 200 and ficha.json()["matriculas"][0]["status"] == "ativa"
    )
    assert (
        client.get(
            f"/api/leads/leads/{compra_sem_matricula.pk}", {"origem": "crm"}, **painel
        ).status_code
        == 404
    )
    quadro = client.get("/api/leads/crm", {"q": "Marina"}, **painel).json()
    assert quadro["total"] == 1 and quadro["resumo"]["contatos"] == 1
    assert (
        client.get(
            "/api/leads/crm/" + resultado["oportunidade_id"], **painel
        ).status_code
        == 200
    )
    assert (
        client.get("/api/leads/leads", {"origem": "quiz"}, **painel).json()["total"]
        == 0
    )


def test_importacao_pelo_painel_repetida_nao_duplica(client, painel):
    for i in range(2):
        resposta = client.post(
            "/api/leads/alunos/sincronizar",
            data=json.dumps({"matriculas": [matricula()]}),
            content_type="application/json",
            **painel,
        )
        assert resposta.status_code == 200
        assert resposta.json()["contatos_criados"] == (1 if i == 0 else 0)
        assert resposta.json()["oportunidades_criadas"] == (1 if i == 0 else 0)


def test_importacao_recusa_token_de_outro_consumidor(client, settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("outro-par")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-alunos")
    resposta = client.post(
        "/api/leads/alunos/sincronizar",
        data=json.dumps({"matriculas": [matricula()]}),
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer outro-par",
    )
    assert resposta.status_code == 403 and Lead.objects.count() == 0


def test_aluno_de_teste_segue_fora_dos_totais_habituais(client, painel):
    sincronizar_matricula(matricula(email="teste@example.com"))
    assert (
        client.get("/api/leads/leads", {"origem": "crm"}, **painel).json()["total"] == 0
    )
    assert (
        client.get(
            "/api/leads/leads", {"origem": "crm", "testes": "mostrar"}, **painel
        ).json()["total"]
        == 1
    )
    assert client.get("/api/leads/crm", **painel).json()["total"] == 0


def test_compra_do_curso_atual_nao_fecha_proximo_curso():
    from apps.core.handlers import ao_pagamento_aprovado
    import uuid

    sincronizar_matricula(matricula())
    ao_pagamento_aprovado(
        str(uuid.uuid4()),
        {
            "site_id": "escola-a",
            "order_id": "curso-atual-pago",
            "mp_payment_id": "pagamento-atual",
            "amount_cents": 9900,
            "customer": {"email": "marina@dominio.com"},
            "product_id": "curso-atual",
        },
    )
    oportunidade = Oportunidade.objects.get(fonte_referencia_id="proximo-curso")
    assert oportunidade.etapa == "nova" and not oportunidade.encerrada
    assert oportunidade.compras.count() == 0
