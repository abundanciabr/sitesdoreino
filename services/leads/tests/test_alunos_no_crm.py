import json

import pytest

from apps.core.alunos import sincronizar_matricula
from apps.core.models import Lead, Oportunidade, RegistroHistoricoOportunidade, TimelineEvent

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


def test_duas_matriculas_e_repeticao_preservam_contato_sem_criar_venda():
    primeiro = sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(id="mat-2", product_id="curso-2"))
    sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(id="mat-2", product_id="curso-2"))
    assert Lead.objects.count() == 1
    assert Oportunidade.objects.count() == 0
    assert primeiro["oportunidade_criada"] is False
    assert primeiro["oportunidade_id"] is None
    assert TimelineEvent.objects.count() == 2
    assert Lead.objects.get().tags == ["aluno"]


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
    assert Lead.objects.count() == 2
    assert Oportunidade.objects.count() == 0


@pytest.mark.parametrize("status", ["aguardando", "recusada"])
def test_pedido_de_entrada_sem_matricula_nao_vira_aluno(status):
    assert sincronizar_matricula(matricula(status=status))["ignorada"]
    assert Lead.objects.count() == Oportunidade.objects.count() == 0


def test_matricula_preserva_todas_oportunidades_comerciais_preexistentes():
    from django.utils import timezone

    lead = Lead.objects.create(site_id="escola-a", email="marina@dominio.com", source="quiz:crivo")
    abertas = [
        Oportunidade.objects.create(
            lead=lead, etapa="qualificada", titular_id="comercial",
            fonte_tipo=fonte, fonte_referencia_id=referencia,
            passo_descricao="Conversar", passo_executar_ate=timezone.now(),
            passo_evidencia_esperada="Resposta",
        )
        for fonte, referencia in (
            ("quiz", "oferta:curso-2"),
            ("timeline_lead", "proximo-curso"),
        )
    ]
    encerrada = Oportunidade.objects.create(
        lead=lead, etapa="desqualificada", titular_id="comercial",
        fonte_tipo="timeline_lead", fonte_referencia_id="interesse-antigo",
        passo_descricao="Encerrada", passo_executar_ate=timezone.now(),
        passo_evidencia_esperada="Resposta", desfecho_encerrada_em=timezone.now(),
    )
    registro = RegistroHistoricoOportunidade.objects.create(
        oportunidade=abertas[0], autor_id="comercial", tipo="nota",
        descricao="Interesse comercial confirmado.",
    )
    resultado = sincronizar_matricula(matricula())
    sincronizar_matricula(matricula(status="encerrada"))
    assert resultado["contato_id"] == str(lead.pk)
    assert resultado["oportunidade_criada"] is False
    assert set(Oportunidade.objects.values_list("pk", flat=True)) == {
        abertas[0].pk, abertas[1].pk, encerrada.pk,
    }
    assert Oportunidade.objects.filter(etapa="qualificada").count() == 2
    encerrada.refresh_from_db()
    assert encerrada.encerrada and encerrada.etapa == "desqualificada"
    assert RegistroHistoricoOportunidade.objects.get(pk=registro.pk).descricao == "Interesse comercial confirmado."


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
    assert quadro["total"] == 0
    assert quadro["resumo"]["contatos"] == 1
    assert quadro["resumo"]["sem_oportunidade"] == 1
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
        assert resposta.json()["oportunidades_criadas"] == 0


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


def test_compra_do_curso_atual_nao_cria_proximo_curso():
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
    assert not Oportunidade.objects.filter(fonte_referencia_id="proximo-curso").exists()
