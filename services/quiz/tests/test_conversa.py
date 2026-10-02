"""Conversa com IA (fmt=ai): dublê do cliente, nenhuma chamada real."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core import signing
from django.core.cache import cache

from apps.quiz import conversa as conv
from apps.quiz.models import OutboxEvent, Submission, TelemetryEvent
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO
from tests.test_campanhas_direcionadas import campanha  # noqa: F401
from tests.test_importar_quiz import documento, site  # noqa: F401

pytestmark = pytest.mark.django_db

CHAVE_FALSA = "chave-de-teste-nao-real"


class ClienteDuble:
    """Devolve, em ordem, (fala, opcao_id) e guarda os pedidos recebidos."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos = []
        self.messages = self

    def create(self, **pedido):
        self.pedidos.append(pedido)
        fala, opcao_id = self.respostas.pop(0)
        bloco = SimpleNamespace(
            type="tool_use", input={"fala": fala, "opcao_id": opcao_id}
        )
        return SimpleNamespace(content=[bloco])


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    cache.clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHAVE_FALSA)
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    monkeypatch.delenv("QUIZ_IA_LIMITE_DIA", raising=False)
    yield
    cache.clear()


@pytest.fixture
def quiz(campanha):  # noqa: F811
    versao = campanha.versions.get(key="B2")
    versao.experience["formats"]["ai"] = {
        "headline": "Converse com a gente",
        "subheadline": "Rápido",
        "instructions": "Seja gentil e objetivo.",
    }
    versao.save()
    return campanha


def abrir(client, quiz):
    resposta = client.get(
        f"/{quiz.slug}/conversa?v=B2&fmt=ai", HTTP_HOST=quiz.site.host
    )
    assert resposta.status_code == 200
    cookie = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    return resposta, cookie["quizzes"][quiz.slug]


def enviar(client, quiz, resposta, entrada, mensagem, **extra):
    corpo = {
        "quiz_attempt": entrada["session_id"],
        "estado": resposta.context["estado_token"],
        "acao": "mensagem",
        "mensagem": mensagem,
        **extra,
    }
    return client.post(f"/{quiz.slug}/conversa", corpo, HTTP_HOST=quiz.site.host)


def opcao(quiz, ordem_pergunta, texto):
    pergunta = quiz.versions.get(key="B2").questions.all()[ordem_pergunta]
    return pergunta, pergunta.options.get(text=texto)


def concluir(client, quiz, resposta, entrada, email="ana@example.com"):
    return client.post(
        f"/{quiz.slug}/conversa",
        {
            "quiz_attempt": entrada["session_id"],
            "estado": resposta.context["estado_token"],
            "acao": "concluir",
            "email": email,
        },
        HTTP_HOST=quiz.site.host,
    )


def test_conversa_completa_leva_a_oferta_da_faixa_certa(client, quiz):
    _, avanco = opcao(quiz, 0, "Avançando")
    _, rapido = opcao(quiz, 1, "Rápido")
    duble = ClienteDuble(
        [("Legal! E o ritmo?", avanco.id), ("Obrigado!", rapido.id)]
    )
    resposta, entrada = abrir(client, quiz)
    assert not resposta.context["fallback"]
    assert "Em que momento está?" in resposta.content.decode()
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        resposta = enviar(client, quiz, resposta, entrada, "Estou avançando bem")
        assert resposta.status_code == 200
        assert not resposta.context["completo"]
        resposta = enviar(client, quiz, resposta, entrada, "Bem rápido")
    assert resposta.context["completo"]
    assert "e-mail" in resposta.content.decode()
    # O modelo recebeu as instruções da versão e as opções com id.
    sistema = duble.pedidos[0]["system"]
    assert "Seja gentil e objetivo." in sistema
    assert f"opcao_id {avanco.id}" in sistema
    assert duble.pedidos[0]["model"] == "claude-haiku-4-5-20251001"

    final = concluir(client, quiz, resposta, entrada)
    assert final.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.score == 5
    assert submissao.result_key == "alto"
    assert submissao.context["fmt"] == "ai"
    assert submissao.context["ai"] == {
        "turnos": 2,
        "modelo": "claude-haiku-4-5-20251001",
    }
    evento = OutboxEvent.objects.get()
    assert evento.event == "quiz.completado"
    assert evento.payload["context"]["fmt"] == "ai"
    percurso = TelemetryEvent.objects.get(event_type="ai_percurso")
    assert [t[0] for t in percurso.metadata["percurso"]] == ["u", "a", "u", "a"]
    assert CHAVE_FALSA not in str(percurso.metadata)
    # O funil enxerga a conversa como enxerga o formulário.
    tipos = list(
        TelemetryEvent.objects.exclude(event_type="ai_percurso")
        .order_by("id").values_list("event_type", flat=True)
    )
    assert tipos == [
        "view_quiz", "view_question", "click_option", "view_question", "click_option",
    ]
    abertura = TelemetryEvent.objects.get(event_type="view_quiz")
    assert abertura.metadata["context"]["fmt"] == "ai" and abertura.version_key == "B2"
    pagina = client.get(final["Location"], HTTP_HOST=quiz.site.host).content.decode()
    assert "Curso avançado" in pagina or "Avanço" in pagina


def test_opcao_invalida_do_modelo_e_recusada(client, quiz):
    outra, opcao_da_outra = opcao(quiz, 1, "Rápido")
    duble = ClienteDuble([("Anotado!", opcao_da_outra.id), ("Anotado!", 999999)])
    resposta, entrada = abrir(client, quiz)
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        resposta = enviar(client, quiz, resposta, entrada, "rápido")
        estado = conv._ler_estado(resposta.context["estado_token"], entrada)
        assert estado["r"] == {}
        assert "Não consegui entender" in resposta.content.decode()
        resposta = enviar(client, quiz, resposta, entrada, "qualquer coisa")
    estado = conv._ler_estado(resposta.context["estado_token"], entrada)
    assert estado["r"] == {}
    assert not resposta.context["completo"]
    assert Submission.objects.count() == 0


def test_teto_diario_cai_no_fallback_e_conclui_com_a_mesma_pontuacao(
    client, quiz, monkeypatch
):
    monkeypatch.setenv("QUIZ_IA_LIMITE_DIA", "1")
    _, avanco = opcao(quiz, 0, "Avançando")
    duble = ClienteDuble([("Legal!", avanco.id), ("não deve ser chamado", None)])
    resposta, entrada = abrir(client, quiz)
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        resposta = enviar(client, quiz, resposta, entrada, "avançando")
        assert not resposta.context["fallback"]
        resposta = enviar(client, quiz, resposta, entrada, "outra")
    assert len(duble.pedidos) == 1
    assert resposta.status_code == 200
    assert resposta.context["fallback"]
    corpo = resposta.content.decode()
    assert "Qual ritmo?" in corpo and 'type="radio"' in corpo
    # Nova visita com o teto já estourado abre direto nas perguntas fixas.
    outra, entrada2 = abrir(Client_novo(), quiz)
    assert outra.context["fallback"]

    _, rapido = opcao(quiz, 1, "Rápido")
    pergunta_ritmo = rapido.question
    final = client.post(
        f"/{quiz.slug}/conversa",
        {
            "quiz_attempt": entrada["session_id"],
            "estado": resposta.context["estado_token"],
            "acao": "concluir",
            "email": "ana@example.com",
            f"pergunta_{pergunta_ritmo.id}": rapido.id,
        },
        HTTP_HOST=quiz.site.host,
    )
    assert final.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.score == 5 and submissao.result_key == "alto"
    assert submissao.context["ai"]["fallback"] == "teto_diario"


def Client_novo():
    from django.test import Client

    return Client()


def test_sem_chave_cai_no_fallback_sem_503(client, quiz, monkeypatch, caplog):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with caplog.at_level("WARNING"):
        resposta, entrada = abrir(client, quiz)
    assert resposta.status_code == 200
    assert resposta.context["fallback"]
    assert "sem_chave" in caplog.text
    corpo = resposta.content.decode()
    assert "Em que momento está?" in corpo and "Qual ritmo?" in corpo
    post = {
        "quiz_attempt": entrada["session_id"],
        "estado": resposta.context["estado_token"],
        "acao": "concluir",
        "email": "ana@example.com",
    }
    for pergunta in quiz.versions.get(key="B2").questions.all():
        post[f"pergunta_{pergunta.id}"] = pergunta.options.order_by("points").first().id
    final = client.post(f"/{quiz.slug}/conversa", post, HTTP_HOST=quiz.site.host)
    assert final.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.result_key == "baixo"
    assert submissao.context["ai"]["fallback"] == "sem_chave"


def test_mensagem_longa_e_turnos_alem_do_limite(client, quiz):
    resposta, entrada = abrir(client, quiz)
    longa = enviar(client, quiz, resposta, entrada, "x" * (conv.LIMITE_MENSAGEM + 1))
    assert longa.status_code == 422
    vazia = enviar(client, quiz, resposta, entrada, "   ")
    assert vazia.status_code == 422
    duble = ClienteDuble([("Pode repetir?", None)] * conv.LIMITE_TURNOS)
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        for _ in range(conv.LIMITE_TURNOS):
            resposta = enviar(client, quiz, resposta, entrada, "hum")
            assert not resposta.context["fallback"]
        resposta = enviar(client, quiz, resposta, entrada, "hum")
    assert len(duble.pedidos) == conv.LIMITE_TURNOS
    assert resposta.context["fallback"]
    assert conv._ler_estado(resposta.context["estado_token"], entrada)["fb"] == (
        "limite_de_turnos"
    )


def test_erro_da_api_cai_no_fallback(client, quiz):
    class Quebrado:
        messages = SimpleNamespace(
            create=lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))
        )

    resposta, entrada = abrir(client, quiz)
    with patch("apps.quiz.conversa._cliente", return_value=Quebrado()):
        resposta = enviar(client, quiz, resposta, entrada, "oi")
    assert resposta.status_code == 200 and resposta.context["fallback"]


def test_abas_diferentes_nao_se_misturam(client, quiz):
    _, avanco = opcao(quiz, 0, "Avançando")
    duble = ClienteDuble([("Legal!", avanco.id)])
    resposta_a, entrada_a = abrir(client, quiz)
    # Segunda aba, mesma campanha, outra tentativa.
    resposta_b = client.get(
        f"/{quiz.slug}/conversa?v=B2&fmt=ai&utm_campaign=outra",
        HTTP_HOST=quiz.site.host,
    )
    cookie = signing.loads(client.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    entrada_b = cookie["quizzes"][quiz.slug]
    assert entrada_a["session_id"] != entrada_b["session_id"]
    with patch("apps.quiz.conversa._cliente", return_value=duble):
        resposta_a = enviar(client, quiz, resposta_a, entrada_a, "avançando")
    estado_a = conv._ler_estado(resposta_a.context["estado_token"], entrada_a)
    assert len(estado_a["r"]) == 1
    # O estado da aba A não vale na tentativa B: a conversa B recomeça.
    cruzada = client.post(
        f"/{quiz.slug}/conversa",
        {
            "quiz_attempt": entrada_b["session_id"],
            "estado": resposta_a.context["estado_token"],
            "acao": "mensagem",
            "mensagem": "oi",
        },
        HTTP_HOST=quiz.site.host,
    )
    assert cruzada.status_code == 422
    assert conv._ler_estado(cruzada.context["estado_token"], entrada_b)["r"] == {}
    # Tentativa inexistente é 404 e nada é gravado.
    inexistente = client.post(
        f"/{quiz.slug}/conversa",
        {"quiz_attempt": "00000000-0000-0000-0000-000000000000", "acao": "mensagem"},
        HTTP_HOST=quiz.site.host,
    )
    assert inexistente.status_code == 404
    assert Submission.objects.count() == 0


@pytest.mark.parametrize("fmt", ["ai", "ai_agent"])
def test_entrada_principal_com_fmt_de_ia_abre_a_conversa(client, quiz, fmt):
    resposta = client.get(f"/{quiz.slug}/?v=B2&fmt={fmt}", HTTP_HOST=quiz.site.host)
    assert resposta.status_code == 200
    assert "estado_token" in resposta.context
