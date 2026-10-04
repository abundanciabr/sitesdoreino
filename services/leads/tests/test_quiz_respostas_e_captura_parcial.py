import uuid

import pytest

from apps.core.handlers import ao_quiz_captura_parcial, ao_quiz_completado, processar_envelope
from apps.core.models import Lead, Oportunidade, QuizDoLead, TimelineEvent


pytestmark = pytest.mark.django_db


@pytest.fixture
def autorizado(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-respostas")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-respostas")
    return {"HTTP_AUTHORIZATION": "Bearer admin-respostas"}


RESPOSTAS = [
    {"pergunta_id": "q1", "pergunta": "Quanto tempo você tem por semana?",
     "respostas": [{"id": "o2", "texto": "Menos de 2 horas"}], "valor_livre": None},
    {"pergunta_id": "q2", "pergunta": "O que você quer alcançar?",
     "respostas": [], "valor_livre": "Trabalhar com isso"},
]


def completo(email="maria@gmail.com", slug="crivo", site="a", **extra):
    data = {
        "site_id": site, "quiz_slug": slug, "result_key": "iniciante", "score": 7,
        "version_key": "v2", "lead": {"email": email, "name": "Maria"},
        "utm": {"utm_campaign": "outubro"}, "respostas": RESPOSTAS,
    }
    data.update(extra)
    ao_quiz_completado(str(uuid.uuid4()), data)


def parcial(email="maria@gmail.com", slug="crivo", site="a", sessao="s-1", respostas=None,
            **extra):
    data = {
        "site_id": site, "session_id": sessao, "quiz_slug": slug, "version_key": "v2",
        "contato": {"nome": "Maria", "email": email, "telefone": "+5511999990000"},
        "respostas": RESPOSTAS[:1] if respostas is None else respostas,
        "utm": {"utm_campaign": "outubro"},
    }
    data.update(extra)
    event_id = str(uuid.uuid4())
    ao_quiz_captura_parcial(event_id, data)
    return event_id


def test_quiz_completo_guarda_respostas_legiveis_e_ficha_mostra(client, autorizado):
    completo()
    lead = Lead.objects.get()
    quiz = QuizDoLead.objects.get()
    assert quiz.situacao == "completo"
    assert quiz.resultado == "iniciante" and quiz.pontuacao == 7 and quiz.versao == "v2"
    assert quiz.respostas[0]["respostas"] == [{"id": "o2", "texto": "Menos de 2 horas"}]
    assert quiz.respostas[1]["valor_livre"] == "Trabalhar com isso"
    assert quiz.campanha == "outubro"

    resposta = client.get(f"/api/leads/leads/{lead.pk}/respostas", **autorizado)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["lead_id"] == str(lead.pk)
    assert corpo["quizzes"][0]["respostas"][0]["pergunta"] == "Quanto tempo você tem por semana?"

    ficha = client.get(f"/api/leads/leads/{lead.pk}", {"origem": "quiz"}, **autorizado).json()
    assert ficha["quizzes"][0]["quiz_slug"] == "crivo"
    assert ficha["perfil"] is None


def test_respostas_pedem_token_do_painel_e_lead_existente(client, autorizado, settings):
    completo()
    lead = Lead.objects.get()
    settings.TOKENS_ACEITOS.add("outro")
    assert client.get(f"/api/leads/leads/{lead.pk}/respostas",
                      HTTP_AUTHORIZATION="Bearer outro").status_code == 403
    assert client.get(f"/api/leads/leads/{uuid.uuid4()}/respostas", **autorizado).status_code == 404
    assert client.get("/api/leads/leads/nada/respostas", **autorizado).status_code == 404


def test_respostas_de_um_lead_nao_aparecem_em_outro(client, autorizado):
    completo("maria@gmail.com")
    completo("joao@gmail.com", respostas=[{"pergunta_id": "q9", "pergunta": "Outra",
                                           "respostas": [], "valor_livre": "segredo do joao"}])
    completo("maria@gmail.com", site="b")
    maria = Lead.objects.get(email="maria@gmail.com", site_id="a")
    corpo = client.get(f"/api/leads/leads/{maria.pk}/respostas", **autorizado).json()
    assert len(corpo["quizzes"]) == 1
    assert "segredo do joao" not in str(corpo)


def test_captura_parcial_cria_contato_do_quiz_e_abre_oferta(client, autorizado):
    parcial()
    lead = Lead.objects.get()
    assert lead.source == "quiz:crivo" and lead.phone == "+5511999990000"
    assert TimelineEvent.objects.filter(lead=lead, event="quiz.captura_parcial").count() == 1
    oferta = Oportunidade.objects.get()
    assert oferta.fonte_referencia_id == "oferta:crivo" and oferta.etapa == "nova"
    quiz = QuizDoLead.objects.get()
    assert quiz.situacao == "parcial" and quiz.sessao == "s-1" and len(quiz.respostas) == 1
    lista = client.get("/api/leads/leads", {"origem": "quiz"}, **autorizado).json()
    assert [item["email"] for item in lista["itens"]] == ["maria@gmail.com"]


def test_capturas_seguintes_atualizam_a_mesma_tentativa_sem_duplicar():
    parcial()
    parcial(respostas=RESPOSTAS)
    parcial(respostas=[])  # captura atrasada com menos respostas não apaga as anteriores
    assert QuizDoLead.objects.count() == 1
    assert len(QuizDoLead.objects.get().respostas) == 2
    assert TimelineEvent.objects.filter(event="quiz.captura_parcial").count() == 1
    assert Oportunidade.objects.count() == 1


def test_quiz_completo_conclui_a_captura_e_nao_duplica_oferta():
    parcial()
    completo()  # versão do quiz que ainda não manda a sessão
    assert Lead.objects.count() == 1
    assert Oportunidade.objects.count() == 1
    quiz = QuizDoLead.objects.get()
    assert quiz.situacao == "completo" and quiz.sessao == "s-1"
    assert len(quiz.respostas) == 2 and quiz.completado_em is not None


def test_quiz_completo_com_sessao_conclui_a_tentativa_da_mesma_sessao():
    parcial(sessao="s-1")
    parcial(sessao="s-2")
    completo(session_id="s-2", submission_id="sub-9")
    tentativas = {q.sessao: q for q in QuizDoLead.objects.all()}
    assert tentativas["s-1"].situacao == "parcial"
    assert tentativas["s-2"].situacao == "completo"
    assert tentativas["s-2"].submissao_id == "sub-9"
    assert Oportunidade.objects.count() == 1


def test_captura_parcial_atrasada_nao_desfaz_quiz_completo():
    completo(session_id="s-1")
    parcial(sessao="s-1", respostas=[])
    quiz = QuizDoLead.objects.get()
    assert quiz.situacao == "completo" and len(quiz.respostas) == 2
    assert not TimelineEvent.objects.filter(event="quiz.captura_parcial").exists()


def test_outro_quiz_abre_outra_oferta():
    parcial(slug="crivo")
    parcial(slug="cura", sessao="s-9")
    assert set(Oportunidade.objects.values_list("fonte_referencia_id", flat=True)) == {
        "oferta:crivo", "oferta:cura"}


def test_captura_parcial_aceita_nomes_alternativos_e_so_telefone_de_contato_conhecido():
    ao_quiz_captura_parcial(str(uuid.uuid4()), {
        "site": "a", "sessao": "x", "quiz": "crivo", "versao": "v1",
        "lead": {"email": "ana@gmail.com", "name": "Ana", "phone": "+55 (11) 98888-7777"},
        "respostas": RESPOSTAS, "origem": {"utm_source": "ig"}, "campanha": "promo",
    })
    quiz = QuizDoLead.objects.get()
    assert quiz.lead.email == "ana@gmail.com" and quiz.campanha == "promo"
    assert quiz.utm == {"utm_source": "ig"}
    # Só telefone, escrito de outro jeito: é o mesmo contato.
    ao_quiz_captura_parcial(str(uuid.uuid4()), {
        "site_id": "a", "session_id": "y", "quiz_slug": "cura",
        "contato": {"telefone": "11988887777"}, "respostas": [],
    })
    # Número curto demais não identifica ninguém.
    ao_quiz_captura_parcial(str(uuid.uuid4()), {
        "site_id": "a", "session_id": "z", "quiz_slug": "cura",
        "contato": {"telefone": "+55 11 2"}, "respostas": [],
    })
    assert Lead.objects.count() == 1
    assert QuizDoLead.objects.filter(quiz_slug="cura").get().lead.email == "ana@gmail.com"


def test_captura_parcial_reentregue_nao_roda_duas_vezes():
    envelope = {"event_id": str(uuid.uuid4()), "data": {
        "site_id": "a", "session_id": "s", "quiz_slug": "crivo",
        "contato": {"email": "bia@gmail.com"}, "respostas": RESPOSTAS,
    }}
    assert processar_envelope(envelope, ao_quiz_captura_parcial) is True
    assert processar_envelope(envelope, ao_quiz_captura_parcial) is False
    assert QuizDoLead.objects.count() == 1


def test_respostas_estranhas_sao_normalizadas():
    completo(respostas=[
        "lixo", {"pergunta_id": 3, "pergunta": "P", "respostas": ["A", {"id": 1, "texto": "B"}]},
    ])
    assert QuizDoLead.objects.get().respostas == [{
        "pergunta_id": "3", "pergunta": "P",
        "respostas": [{"id": "", "texto": "A"}, {"id": "1", "texto": "B"}],
        "valor_livre": None,
    }]


def test_consumer_escuta_captura_parcial():
    from apps.core.management.commands.consume_eventos import STREAMS

    assert STREAMS["eventos.quiz.captura_parcial"] is ao_quiz_captura_parcial


def test_ficha_com_token_comercial_so_do_proprio_site_e_sem_perfil(client, autorizado, settings):
    completo("maria@gmail.com", site="a")
    completo("joao@gmail.com", site="b")
    settings.COMERCIAIS_DO_CRM = {"com-site-b": {"titular_id": "com-b", "site_id": "b"}}
    settings.TOKENS_ACEITOS.add("com-site-b")
    comercial = {"HTTP_AUTHORIZATION": "Bearer com-site-b"}
    maria = Lead.objects.get(email="maria@gmail.com")
    joao = Lead.objects.get(email="joao@gmail.com")
    assert client.get(f"/api/leads/leads/{maria.pk}", **comercial).status_code == 404
    ficha = client.get(f"/api/leads/leads/{joao.pk}", **comercial).json()
    assert ficha["quizzes"] == [] and ficha["perfil"] is None
    lista = client.get("/api/leads/leads", **comercial).json()
    assert [item["email"] for item in lista["itens"]] == ["joao@gmail.com"]
    # O painel continua vendo tudo, com respostas.
    assert client.get(f"/api/leads/leads/{maria.pk}", **autorizado).json()["quizzes"]
