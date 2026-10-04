"""Respostas legíveis no evento e na API interna, e a captura parcial identificada."""

import uuid
from datetime import timedelta

import pytest
from django.core import signing
from django.test import Client, override_settings
from django.utils import timezone

from apps.quiz.models import (
    CapturaParcial,
    Option,
    OutboxEvent,
    Question,
    Quiz,
    QuizVersion,
    ResultBand,
    Submission,
)
from apps.quiz.tasks import SILENCIO_DA_CAPTURA, publicar_capturas_paradas
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO
from tests.test_campanhas_direcionadas import abrir as abrir_campanha
from tests.test_campanhas_direcionadas import campanha  # noqa: F401
from tests.test_importar_quiz import documento, site  # noqa: F401
from tests.test_smoke import HOST_A, HOST_B, SITE_A_ID, SITE_B_ID, site_a, site_b  # noqa: F401

pytestmark = pytest.mark.django_db

TOKEN = "token-admin-de-teste"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.fixture
def quiz(site_a):  # noqa: F811
    quiz = Quiz.objects.create(site=site_a, slug="objetivo", title="Seu objetivo")
    versao = QuizVersion.objects.create(quiz=quiz, key="v1", weight=100, active=True)
    p1 = Question.objects.create(version=versao, order=1, text="Qual o seu objetivo?")
    Option.objects.create(question=p1, order=1, text="Aprender do zero", points=0)
    Option.objects.create(question=p1, order=2, text="Vender online", points=10)
    p2 = Question.objects.create(version=versao, order=2, text="Quanto tempo por dia?")
    Option.objects.create(question=p2, order=1, text="Menos de 1 hora", points=0)
    Option.objects.create(question=p2, order=2, text="Mais de 2 horas", points=10)
    ResultBand.objects.create(
        version=versao, key="comeco", title="Começando", min_score=0, max_score=9
    )
    ResultBand.objects.create(
        version=versao, key="pronto", title="Pronto", min_score=10, max_score=20
    )
    return quiz


def perguntas(quiz):
    return list(quiz.versions.get().questions.order_by("order"))


def opcao(pergunta, texto):
    return pergunta.options.get(text=texto)


def abrir(client, quiz, host=HOST_A):
    resposta = client.get(f"/{quiz.slug}/", HTTP_HOST=host)
    assert resposta.status_code == 200
    cookie = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    return cookie["quizzes"][quiz.slug]


def concluir(client, quiz, email="ana@exemplo.com", telefone="", host=HOST_A):
    p1, p2 = perguntas(quiz)
    return client.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{p1.id}": opcao(p1, "Vender online").id,
            f"pergunta_{p2.id}": opcao(p2, "Menos de 1 hora").id,
            "email": email,
            "nome": "Ana",
            "telefone": telefone,
        },
        HTTP_HOST=host,
    )


def capturar(client, quiz, host=HOST_A, **campos):
    return client.post(f"/{quiz.slug}/captura", campos, HTTP_HOST=host)


def depois_do_silencio():
    """Um instante em que a captura já ficou parada o bastante para o aviso."""
    return timezone.now() + SILENCIO_DA_CAPTURA + timedelta(minutes=1)


def avisos():
    return list(OutboxEvent.objects.filter(event="quiz.captura_parcial").order_by("id"))


# ---------------------------------------------------------------------------
# Evento quiz.completado com respostas
# ---------------------------------------------------------------------------
def test_quiz_completado_leva_respostas_legiveis_sem_perder_campos_antigos(client, quiz):
    entrada = abrir(client, quiz)
    assert concluir(client, quiz).status_code == 302
    p1, p2 = perguntas(quiz)
    submissao = Submission.objects.get()
    dados = OutboxEvent.objects.get(event="quiz.completado").payload

    for campo in ("site_id", "quiz_slug", "result_key", "score", "version_key", "lead", "utm"):
        assert campo in dados
    assert dados["lead"] == {"email": "ana@exemplo.com", "name": "Ana"}
    assert dados["submissao_id"] == str(submissao.id)
    assert dados["sessao"] == entrada["session_id"]
    assert "captura_parcial_id" not in dados
    assert dados["respostas"] == [
        {
            "pergunta_id": p1.id,
            "pergunta": "Qual o seu objetivo?",
            "respostas": [{"id": opcao(p1, "Vender online").id, "texto": "Vender online"}],
            "valor_livre": None,
        },
        {
            "pergunta_id": p2.id,
            "pergunta": "Quanto tempo por dia?",
            "respostas": [{"id": opcao(p2, "Menos de 1 hora").id, "texto": "Menos de 1 hora"}],
            "valor_livre": None,
        },
    ]


# ---------------------------------------------------------------------------
# API interna
# ---------------------------------------------------------------------------
@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_api_exige_token_do_admin(client, quiz):
    abrir(client, quiz)
    concluir(client, quiz)
    submissao = Submission.objects.get()
    rota = f"/interno/crm/submissoes/{submissao.id}?site_id={SITE_A_ID}"
    assert client.get(rota).status_code == 401
    assert client.get(rota, HTTP_AUTHORIZATION="Bearer outro").status_code == 401
    assert client.get(rota, **AUTH).status_code == 200
    lista = f"/interno/crm/submissoes?site_id={SITE_A_ID}&email=ana@exemplo.com"
    assert client.get(lista).status_code == 401
    assert client.get(f"/interno/crm/capturas/{uuid.uuid4()}?site_id=x").status_code == 401


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_api_devolve_perguntas_e_respostas_legiveis_da_submissao(client, quiz):
    abrir(client, quiz)
    concluir(client, quiz, telefone="(11) 98888-7777")
    submissao = Submission.objects.get()

    corpo = client.get(
        f"/interno/crm/submissoes/{submissao.id}?site_id={SITE_A_ID}", **AUTH
    ).json()

    assert corpo["id"] == str(submissao.id)
    assert corpo["quiz_slug"] == "objetivo"
    assert corpo["quiz_titulo"] == "Seu objetivo"
    assert corpo["version_key"] == "v1"
    assert corpo["resultado"] == {"chave": "pronto", "titulo": "Pronto", "pontuacao": 10}
    assert corpo["contato"] == {
        "nome": "Ana",
        "email": "ana@exemplo.com",
        "telefone": "(11) 98888-7777",
    }
    assert [(r["pergunta"], r["respostas"][0]["texto"]) for r in corpo["respostas"]] == [
        ("Qual o seu objetivo?", "Vender online"),
        ("Quanto tempo por dia?", "Menos de 1 hora"),
    ]
    assert corpo["captura_parcial_id"] is None


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_api_nunca_mostra_submissao_de_outro_site(client, quiz):
    abrir(client, quiz)
    concluir(client, quiz)
    submissao = Submission.objects.get()
    assert (
        client.get(f"/interno/crm/submissoes/{submissao.id}?site_id={SITE_B_ID}", **AUTH).status_code
        == 404
    )
    assert client.get(f"/interno/crm/submissoes/{submissao.id}", **AUTH).status_code == 400
    assert (
        client.get(f"/interno/crm/submissoes/{uuid.uuid4()}?site_id={SITE_A_ID}", **AUTH).status_code
        == 404
    )


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_lista_por_contato_acha_por_email_e_telefone_e_separa_sites(quiz, site_b):  # noqa: F811
    quiz_b = Quiz.objects.create(site=site_b, slug="objetivo", title="Outro site")
    versao_b = QuizVersion.objects.create(quiz=quiz_b, key="v1", weight=100)
    Submission.objects.create(
        quiz=quiz_b,
        version=versao_b,
        session_id=uuid.uuid4(),
        site_id=SITE_B_ID,
        score=0,
        result_key="x",
        answers={},
        lead_email="ana@exemplo.com",
        lead_phone="11988887777",
    )
    ana = Client()
    abrir(ana, quiz)
    concluir(ana, quiz, email="Ana@Exemplo.com", telefone="+55 (11) 98888-7777")
    outra = Client()
    abrir(outra, quiz)
    concluir(outra, quiz, email="bia@exemplo.com", telefone="(21) 97777-6666")

    cliente = Client()
    por_email = cliente.get(
        "/interno/crm/submissoes",
        {"site_id": SITE_A_ID, "email": "ana@exemplo.com"},
        **AUTH,
    ).json()
    assert [s["site_id"] for s in por_email["submissoes"]] == [SITE_A_ID]
    assert por_email["submissoes"][0]["resultado"]["chave"] == "pronto"
    assert "contato" not in por_email["submissoes"][0]

    por_telefone = cliente.get(
        "/interno/crm/submissoes",
        {"site_id": SITE_A_ID, "telefone": "11 98888-7777"},
        **AUTH,
    ).json()
    assert [s["id"] for s in por_telefone["submissoes"]] == [
        s["id"] for s in por_email["submissoes"]
    ]
    assert por_telefone["capturas_parciais"] == []

    assert (
        cliente.get("/interno/crm/submissoes", {"site_id": SITE_A_ID}, **AUTH).status_code
        == 400
    )
    assert (
        cliente.get(
            "/interno/crm/submissoes", {"email": "ana@exemplo.com"}, **AUTH
        ).status_code
        == 400
    )


# ---------------------------------------------------------------------------
# Captura parcial
# ---------------------------------------------------------------------------
def test_captura_parcial_registra_e_publica_uma_vez_por_sessao(client, quiz):
    entrada = abrir(client, quiz)
    p1, p2 = perguntas(quiz)
    resposta = capturar(
        client,
        quiz,
        email="ana@exemplo.com",
        **{f"pergunta_{p1.id}": opcao(p1, "Vender online").id},
    )
    assert resposta.status_code == 201
    assert resposta.json() == {"estado": "registrada"}

    captura = CapturaParcial.objects.get()
    assert str(captura.session_id) == entrada["session_id"]
    assert captura.site_id == SITE_A_ID
    # O aviso espera a pessoa parar: quem conclui em seguida não gera abandono.
    assert avisos() == []
    assert publicar_capturas_paradas() == 0

    # Repetir completa a mesma linha; o aviso sai uma vez, com o contato todo.
    resposta = capturar(
        client,
        quiz,
        email="",
        nome="Ana",
        telefone="(11) 98888-7777",
        **{f"pergunta_{p2.id}": opcao(p2, "Mais de 2 horas").id},
    )
    assert resposta.status_code == 200
    assert resposta.json() == {"estado": "atualizada"}
    assert CapturaParcial.objects.count() == 1
    captura.refresh_from_db()
    assert captura.lead_email == "ana@exemplo.com"  # vazio não apaga
    assert captura.lead_name == "Ana"
    assert captura.lead_phone == "(11) 98888-7777"
    assert set(captura.answers) == {str(p1.id), str(p2.id)}

    agora = depois_do_silencio()
    assert publicar_capturas_paradas(agora) == 1
    [evento] = avisos()
    assert evento.payload == {
        "captura_id": str(captura.id),
        "site_id": SITE_A_ID,
        "sessao": entrada["session_id"],
        "quiz_slug": "objetivo",
        "version_key": "v1",
        "lead": {
            "email": "ana@exemplo.com",
            "name": "Ana",
            "phone": "(11) 98888-7777",
        },
        "respostas": [
            {
                "pergunta_id": p1.id,
                "pergunta": "Qual o seu objetivo?",
                "respostas": [{"id": opcao(p1, "Vender online").id, "texto": "Vender online"}],
                "valor_livre": None,
            },
            {
                "pergunta_id": p2.id,
                "pergunta": "Quanto tempo por dia?",
                "respostas": [{"id": opcao(p2, "Mais de 2 horas").id, "texto": "Mais de 2 horas"}],
                "valor_livre": None,
            },
        ],
        "utm": {},
        "publicacao": 1,
    }

    # Rodar de novo, ou repetir o mesmo contato, não publica outra vez.
    assert publicar_capturas_paradas(agora) == 0
    capturar(client, quiz, email="ana@exemplo.com", nome="Ana")
    assert publicar_capturas_paradas(agora + SILENCIO_DA_CAPTURA * 2) == 0
    assert len(avisos()) == 1


def test_contato_novo_depois_do_aviso_publica_a_mesma_captura_atualizada(client, quiz):
    abrir(client, quiz)
    capturar(client, quiz, email="ana@exemplo.com")
    assert publicar_capturas_paradas(depois_do_silencio()) == 1

    capturar(client, quiz, telefone="(11) 98888-7777")
    assert CapturaParcial.objects.count() == 1
    assert publicar_capturas_paradas(timezone.now() + timedelta(minutes=1)) == 0  # recém mexida
    assert publicar_capturas_paradas(depois_do_silencio() + SILENCIO_DA_CAPTURA) == 1

    primeiro, segundo = avisos()
    assert primeiro.payload["captura_id"] == segundo.payload["captura_id"]
    assert (primeiro.payload["publicacao"], segundo.payload["publicacao"]) == (1, 2)
    assert segundo.payload["lead"] == {
        "email": "ana@exemplo.com",
        "phone": "(11) 98888-7777",
    }


def test_quem_conclui_antes_do_silencio_nao_gera_aviso_de_abandono(client, quiz):
    abrir(client, quiz)
    capturar(client, quiz, email="ana@exemplo.com")
    assert concluir(client, quiz).status_code == 302
    assert publicar_capturas_paradas(depois_do_silencio()) == 0
    assert avisos() == []
    assert OutboxEvent.objects.filter(event="quiz.completado").count() == 1


def test_captura_esquecida_de_quem_concluiu_so_e_ligada_sem_aviso(client, quiz):
    """Concluiu sem a captura enxergar (ex.: captura chegou depois): só liga."""
    abrir(client, quiz)
    capturar(client, quiz, email="ana@exemplo.com")
    submissao = Submission.objects.create(
        quiz=quiz,
        version=quiz.versions.get(),
        session_id=CapturaParcial.objects.get().session_id,
        site_id=SITE_A_ID,
        score=0,
        result_key="comeco",
        answers={},
        lead_email="ana@exemplo.com",
    )
    assert publicar_capturas_paradas(depois_do_silencio()) == 0
    assert CapturaParcial.objects.get().submissao_id == submissao.id
    assert avisos() == []


def test_quiz_completo_depois_da_captura_liga_as_duas_coisas(client, quiz):
    abrir(client, quiz)
    capturar(client, quiz, email="ana@exemplo.com")
    assert concluir(client, quiz).status_code == 302

    captura = CapturaParcial.objects.get()
    submissao = Submission.objects.get()
    assert captura.submissao_id == submissao.id
    completado = OutboxEvent.objects.get(event="quiz.completado").payload
    assert completado["captura_parcial_id"] == str(captura.id)
    assert completado["sessao"] == str(captura.session_id)
    assert completado["lead"]["email"] == "ana@exemplo.com"

    # Depois de concluir, a captura não faz mais nada.
    resposta = capturar(client, quiz, email="outra@exemplo.com")
    assert resposta.json() == {"estado": "concluida"}
    assert avisos() == []
    captura.refresh_from_db()
    assert captura.lead_email == "ana@exemplo.com"


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_captura_aparece_na_api_por_contato_e_por_id(client, quiz):
    abrir(client, quiz)
    p1, _ = perguntas(quiz)
    capturar(
        client,
        quiz,
        telefone="(11) 98888-7777",
        nome="Ana",
        **{f"pergunta_{p1.id}": opcao(p1, "Aprender do zero").id},
    )
    captura = CapturaParcial.objects.get()
    api = Client()

    lista = api.get(
        "/interno/crm/submissoes",
        {"site_id": SITE_A_ID, "telefone": "5511988887777"},
        **AUTH,
    ).json()
    assert lista["submissoes"] == []
    [item] = lista["capturas_parciais"]
    assert item["id"] == str(captura.id)
    assert item["contato"] == {"nome": "Ana", "email": "", "telefone": "(11) 98888-7777"}
    assert item["respostas"][0]["respostas"] == [
        {"id": opcao(p1, "Aprender do zero").id, "texto": "Aprender do zero"}
    ]
    assert item["concluida"] is False

    unica = api.get(f"/interno/crm/capturas/{captura.id}?site_id={SITE_A_ID}", **AUTH)
    assert unica.status_code == 200
    assert unica.json()["sessao"] == str(captura.session_id)
    assert (
        api.get(f"/interno/crm/capturas/{captura.id}?site_id={SITE_B_ID}", **AUTH).status_code
        == 404
    )


def test_captura_sem_sessao_ou_sem_contato_nao_registra(client, quiz):
    assert capturar(client, quiz, email="ana@exemplo.com").status_code == 404
    abrir(client, quiz)
    resposta = capturar(client, quiz, email="nao-e-email", telefone="123")
    assert resposta.status_code == 422
    assert resposta.json() == {"estado": "sem_contato"}
    assert not CapturaParcial.objects.exists()
    assert not OutboxEvent.objects.exists()


def test_captura_ignora_email_invalido_e_fica_com_o_telefone(client, quiz):
    abrir(client, quiz)
    p1, _ = perguntas(quiz)
    resposta = capturar(
        client,
        quiz,
        email="ana@",
        telefone="11 98888-7777",
        **{f"pergunta_{p1.id}": "999999"},  # opção que não é desta pergunta
    )
    assert resposta.status_code == 201
    captura = CapturaParcial.objects.get()
    assert captura.lead_email == ""
    assert captura.answers == {}
    assert publicar_capturas_paradas(depois_do_silencio()) == 1
    assert avisos()[0].payload["lead"] == {"phone": "11 98888-7777"}


def test_captura_de_outra_sessao_vira_outra_captura(quiz):
    for email in ("ana@exemplo.com", "ana@exemplo.com"):
        navegador = Client()
        abrir(navegador, quiz)
        assert capturar(navegador, quiz, email=email).status_code == 201
    assert CapturaParcial.objects.count() == 2


def test_captura_exige_token_csrf(quiz):
    navegador = Client(enforce_csrf_checks=True)
    pagina = navegador.get(f"/{quiz.slug}/", HTTP_HOST=HOST_A)
    assert 'data-captura="/objetivo/captura"' in pagina.content.decode()
    sem_token = capturar(navegador, quiz, email="ana@exemplo.com")
    assert sem_token.status_code == 403
    token = navegador.cookies["quiz_csrf"].value
    com_token = capturar(
        navegador, quiz, email="ana@exemplo.com", csrfmiddlewaretoken=token
    )
    assert com_token.status_code == 201


def test_captura_em_quiz_direcionado_usa_a_tentativa(client, campanha):  # noqa: F811
    entrada = abrir_campanha(client, campanha)
    tentativa_alheia = capturar(
        client,
        campanha,
        host=campanha.site.host,
        email="ana@exemplo.com",
        quiz_attempt=str(uuid.uuid4()),
    )
    assert tentativa_alheia.status_code == 404
    resposta = capturar(
        client,
        campanha,
        host=campanha.site.host,
        email="ana@exemplo.com",
        quiz_attempt=entrada["session_id"],
    )
    assert resposta.status_code == 201
    captura = CapturaParcial.objects.get()
    assert str(captura.session_id) == entrada["session_id"]
    assert captura.context == entrada["context"]
    assert publicar_capturas_paradas(depois_do_silencio()) == 1
    assert avisos()[0].payload["context"] == entrada["context"]


def test_captura_nao_responde_em_host_de_outro_site(client, quiz, site_b):  # noqa: F811
    abrir(client, quiz)
    resposta = capturar(client, quiz, host=HOST_B, email="ana@exemplo.com")
    assert resposta.status_code == 404
    assert not CapturaParcial.objects.exists()
