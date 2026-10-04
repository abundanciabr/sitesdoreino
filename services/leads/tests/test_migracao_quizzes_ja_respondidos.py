import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


ANTES = [("core", "0005_reversaodepagamento")]
DEPOIS = [("core", "0006_perfil_respostas_e_acompanhamento")]


@pytest.mark.django_db(transaction=True)
def test_quem_respondeu_antes_aparece_com_o_quiz_na_ficha():
    executor = MigrationExecutor(connection)
    executor.migrate(ANTES)
    antigos = executor.loader.project_state(ANTES).apps
    Lead = antigos.get_model("core", "Lead")
    TimelineEvent = antigos.get_model("core", "TimelineEvent")
    lead = Lead.objects.create(site_id="a", email="antigo@gmail.com", source="quiz:crivo")
    evento = uuid.uuid4()
    TimelineEvent.objects.create(lead=lead, event="quiz.completado", event_id=evento, payload={
        "site_id": "a", "quiz_slug": "crivo", "result_key": "avancado", "score": 9,
        "version_key": "v1", "lead": {"email": "antigo@gmail.com"},
        "utm": {"utm_campaign": "setembro"},
    })
    TimelineEvent.objects.create(lead=lead, event="pedido.criado", payload={})

    executor = MigrationExecutor(connection)
    executor.migrate(DEPOIS)
    novos = executor.loader.project_state(DEPOIS).apps
    QuizDoLead = novos.get_model("core", "QuizDoLead")
    quiz = QuizDoLead.objects.get()
    assert (quiz.lead_id, quiz.quiz_slug, quiz.situacao) == (lead.pk, "crivo", "completo")
    assert (quiz.resultado, quiz.pontuacao, quiz.versao) == ("avancado", 9, "v1")
    assert quiz.campanha == "setembro" and quiz.respostas == []
    assert quiz.ultimo_event_id == evento and quiz.completado_em is not None
