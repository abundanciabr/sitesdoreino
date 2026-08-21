# [RECEITA:R10 v1]
# Fixtures da célula ficam aqui (não em conftest.py, para caber no orçamento de
# arquivos do despacho): o quiz não consome API de nenhuma outra célula — o
# cadastro de sites é LOCAL (ver services/quiz/LICOES.md, AGENTS.quiz.md).
import pytest

from apps.quiz.models import Option, Question, Quiz, ResultBand, Site, Submission

HOST_A = "quiz-a.exemplo.com"
HOST_B = "quiz-b.exemplo.com"
HOST_DESCONHECIDO = "nao-cadastrado.exemplo.com"

SITE_A_ID = "site-aaa"
SITE_B_ID = "site-bbb"


@pytest.fixture
def site_a(db):
    return Site.objects.create(id=SITE_A_ID, host=HOST_A, name="Site A")


@pytest.fixture
def site_b(db):
    return Site.objects.create(id=SITE_B_ID, host=HOST_B, name="Site B")


@pytest.fixture
def quiz_a(site_a):
    quiz = Quiz.objects.create(site=site_a, slug="crivo", title="Crivo")
    pergunta = Question.objects.create(quiz=quiz, order=1, text="Pergunta 1")
    Option.objects.create(question=pergunta, order=1, text="Zero pontos", points=0)
    Option.objects.create(question=pergunta, order=2, text="Dez pontos", points=10)
    ResultBand.objects.create(
        quiz=quiz, key="baixo", title="Baixo", min_score=0, max_score=4
    )
    ResultBand.objects.create(
        quiz=quiz, key="alto", title="Alto", min_score=5, max_score=10
    )
    return quiz


@pytest.mark.smoke_quiz
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
def test_host_desconhecido_e_404_nunca_um_site_padrao(client, quiz_a):
    resp = client.get(f"/quiz/{quiz_a.slug}/", HTTP_HOST=HOST_DESCONHECIDO)
    assert resp.status_code == 404


@pytest.mark.django_db
@pytest.mark.smoke_quiz
def test_caminho_feliz_form_ate_resultado(client, quiz_a):
    pergunta = quiz_a.questions.get(order=1)
    opcao_dez = pergunta.options.get(points=10)

    formulario = client.get(f"/quiz/{quiz_a.slug}/", HTTP_HOST=HOST_A)
    assert formulario.status_code == 200
    assert b"Pergunta 1" in formulario.content

    resp = client.post(
        f"/quiz/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": opcao_dez.id,
            "email": "lead@exemplo.com",
            "nome": "Lead",
        },
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 302
    assert resp["Location"].startswith(f"/quiz/{quiz_a.slug}/resultado?lead=")

    submissao = Submission.objects.get()
    assert submissao.score == 10
    assert submissao.result_key == "alto"
    assert submissao.lead_email == "lead@exemplo.com"

    resultado = client.get(resp["Location"], HTTP_HOST=HOST_A)
    assert resultado.status_code == 200
    assert b"Alto" in resultado.content
