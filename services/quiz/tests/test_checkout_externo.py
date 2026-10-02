from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client

from apps.quiz.models import ResultBand, Submission, TelemetryEvent
from tests.test_botao_por_faixa import HOST, quiz_a  # noqa: F401

pytestmark = pytest.mark.django_db


def concluir(client, quiz, pontos=0):
    client.get(
        f"/{quiz.slug}/?utm_source=instagram&utm_campaign=outubro", HTTP_HOST=HOST
    )
    pergunta = quiz.versions.get().questions.get()
    resposta = client.post(
        f"/{quiz.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=pontos).id,
            "email": "pessoa@example.com",
            "nome": "Pessoa privada",
        },
        HTTP_HOST=HOST,
    )
    return resposta, Submission.objects.get(session_id__isnull=False)


@pytest.fixture
def externo(quiz_a):
    for key, minimo, maximo in (("base", 0, 4), ("avancar", 5, 10)):
        ResultBand.objects.create(
            version=quiz_a.versions.get(),
            key=key,
            title=key,
            min_score=minimo,
            max_score=maximo,
            botao_destino=f"https://checkout.example/{key}?produto=1#pagar",
            botao_rotulo="Conhecer oferta",
        )
    return quiz_a


@pytest.mark.parametrize("pontos,oferta", [(0, "base"), (10, "avancar")])
def test_sai_para_oferta_calculada_com_origem_sem_contato(
    client, externo, pontos, oferta
):
    resultado, submissao = concluir(client, externo, pontos)
    pagina = client.get(resultado["Location"], HTTP_HOST=HOST)
    assert 'action="/crivo/sair"' in pagina.content.decode()
    resposta = client.post(
        "/crivo/sair",
        {"resposta": submissao.id, "destino": "https://outro.example"},
        HTTP_HOST=HOST,
    )
    assert resposta.status_code == 302
    url = urlsplit(resposta["Location"])
    assert url.netloc == "checkout.example"
    assert url.path == f"/{oferta}"
    assert url.fragment == "pagar"
    assert parse_qs(url.query) == {
        "produto": ["1"],
        "utm_source": ["instagram"],
        "utm_campaign": ["outubro"],
    }
    assert resposta["Referrer-Policy"] == "no-referrer"
    assert resposta["Cache-Control"] == "no-store"
    evento = TelemetryEvent.objects.get(event_type="checkout_exit")
    assert evento.session_id == submissao.session_id
    assert evento.element_id == oferta
    assert evento.metadata == {"utm": submissao.utm}
    assert "pessoa" not in resposta["Location"]


def test_duplo_clique_nao_duplica_saida(client, externo):
    _, submissao = concluir(client, externo)
    for _ in range(2):
        assert (
            client.post(
                "/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST
            ).status_code
            == 302
        )
    assert TelemetryEvent.objects.filter(event_type="checkout_exit").count() == 1


def test_saida_exige_post_csrf_e_sessao_da_resposta(client, externo):
    _, submissao = concluir(client, externo)
    assert client.get("/crivo/sair", HTTP_HOST=HOST).status_code == 405
    assert (
        Client()
        .post("/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST)
        .status_code
        == 404
    )
    protegido = Client(enforce_csrf_checks=True)
    protegido.cookies = client.cookies
    assert (
        protegido.post(
            "/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST
        ).status_code
        == 403
    )
    assert TelemetryEvent.objects.count() == 0


def test_utm_existente_do_checkout_e_preservada(client, externo):
    externo.versions.get().bands.filter(key="base").update(
        botao_destino="https://checkout.example/base?utm_source=parceiro&cupom=10"
    )
    _, submissao = concluir(client, externo)
    resposta = client.post("/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST)
    assert parse_qs(urlsplit(resposta["Location"]).query)["utm_source"] == ["parceiro"]


def test_resposta_antiga_nao_usa_faixa_da_nova_sessao(client, externo):
    _, submissao = concluir(client, externo)
    client.post("/crivo/refazer", HTTP_HOST=HOST)
    assert (
        client.post(
            "/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST
        ).status_code
        == 404
    )


def test_destino_nao_https_nao_e_aceito_na_saida(client, externo):
    _, submissao = concluir(client, externo)
    externo.versions.get().bands.filter(key="base").update(
        botao_destino="javascript:alert(1)"
    )
    assert (
        client.post(
            "/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST
        ).status_code
        == 404
    )


def test_link_compartilhado_continua_funcionando_sem_atribuir_clique(client, externo):
    resultado, _ = concluir(client, externo)
    pagina = Client().get(resultado["Location"], HTTP_HOST=HOST).content.decode()
    assert 'href="https://checkout.example/base?produto=1#pagar"' in pagina
    assert 'action="/crivo/sair"' not in pagina


def test_preserva_bytes_dos_parametros_originais(client, externo):
    externo.versions.get().bands.filter(key="base").update(
        botao_destino="https://checkout.example/base?token=a%20b&item=%2f&flag"
    )
    _, submissao = concluir(client, externo)
    resposta = client.post("/crivo/sair", {"resposta": submissao.id}, HTTP_HOST=HOST)
    assert resposta["Location"].startswith(
        "https://checkout.example/base?token=a%20b&item=%2f&flag&utm_source="
    )
