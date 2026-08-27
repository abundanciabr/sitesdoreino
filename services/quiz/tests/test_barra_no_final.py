"""O middleware `BarraNoFinal` no quiz — e o laço que a regra 1 impede.

O sintoma foi medido em produção pelo mantenedor em 27/08/2026 e consertado
primeiro na `sugestoes` (PR #284). Esta é a quarta e última célula da série, e a
mais delicada das quatro: **o urlconf do quiz mistura as duas convenções de
propósito.**

    path("quiz/<slug>/",          formulario)   <- canônica COM barra
    path("quiz/<slug>/resultado", resultado)    <- canônica SEM barra

O Django já redireciona `/quiz/crivo` → `/quiz/crivo/` sozinho (`APPEND_SLASH`).
Um middleware que fizesse o caminho contrário sem a regra 1 poria os dois em
**laço infinito**. Há teste medindo exatamente isso — não é preocupação teórica,
é a coisa que quebraria a página mais visitada desta célula.

As fixtures moram aqui, e não num `conftest.py`, pela mesma razão declarada em
`test_smoke.py`: o quiz cadastra sites LOCALMENTE e a célula economiza arquivos.
"""

import pytest

from apps.quiz.models import Option, Question, Quiz, ResultBand, Site, Submission

HOST = "quiz-barra.exemplo.com"

pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz_a(db):
    site = Site.objects.create(id="site-barra", host=HOST, name="Site da Barra")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    pergunta = Question.objects.create(quiz=quiz, order=1, text="Pergunta 1")
    Option.objects.create(question=pergunta, order=1, text="Zero", points=0)
    Option.objects.create(question=pergunta, order=2, text="Dez", points=10)
    ResultBand.objects.create(
        quiz=quiz, key="alto", title="Alto", min_score=0, max_score=10
    )
    return quiz


def pegar(client, caminho, **extra):
    return client.get(caminho, HTTP_HOST=HOST, **extra)


# ---------------------------------------------------------------------------
# O laço — o que a regra 1 impede
# ---------------------------------------------------------------------------


def test_o_formulario_com_barra_nao_entra_em_laco_com_o_append_slash(client, quiz_a):
    """O guarda mais importante deste arquivo.

    `/quiz/crivo/` é a forma CANÔNICA (o urlconf a declara com barra) e o Django
    manda `/quiz/crivo` para lá. Se o middleware agisse sobre a forma com barra,
    os dois ficariam se empurrando para sempre e a página principal do quiz
    morreria em `ERR_TOO_MANY_REDIRECTS`.

    A regra 1 ("não age quando a forma COM barra resolve") impede isso por
    construção. Aqui isso é medido, não confiado.
    """
    resposta = pegar(client, f"/quiz/{quiz_a.slug}/")
    assert resposta.status_code == 200, (
        "a página do quiz deixou de responder — se virou redirecionamento, o "
        "middleware entrou em laço com o APPEND_SLASH do Django"
    )


def test_a_forma_sem_barra_continua_indo_para_a_canonica(client, quiz_a):
    """O sentido que o Django já resolvia continua intacto: o middleware novo
    não pode desfazer o `APPEND_SLASH`."""
    resposta = pegar(client, f"/quiz/{quiz_a.slug}")
    assert resposta.status_code in (301, 302)
    assert resposta["Location"].rstrip("/").endswith(f"/quiz/{quiz_a.slug}")
    assert resposta["Location"].endswith("/"), (
        "a forma canônica do formulário é COM barra; o middleware inverteu o "
        "destino do APPEND_SLASH"
    )


# ---------------------------------------------------------------------------
# O que ele conserta
# ---------------------------------------------------------------------------


def test_a_query_do_resultado_sobrevive_ao_redirecionamento(client, quiz_a):
    """O caso que dá valor ao middleware nesta célula, pela jornada REAL.

    `?lead=<uuid>` não é rastreamento: é o que diz QUAL submissão mostrar. Um
    redirecionamento que a perdesse trocaria um 404 por outro 404 — a pessoa
    clicaria no link do próprio resultado e veria "não encontrado".
    """
    pergunta = quiz_a.questions.get(order=1)
    envio = client.post(
        f"/quiz/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": pergunta.options.get(points=10).id,
            "email": "lead@exemplo.com",
            "nome": "Lead",
        },
        HTTP_HOST=HOST,
    )
    assert envio.status_code == 302
    destino_bom = envio["Location"]
    assert Submission.objects.count() == 1

    caminho, _, query = destino_bom.partition("?")
    resposta = pegar(client, f"{caminho}/?{query}")

    assert resposta.status_code == 302
    assert resposta["Location"] == destino_bom, (
        "o redirecionamento perdeu (ou embaralhou) o `lead` — o link do "
        "resultado da pessoa continua quebrado"
    )
    assert (
        pegar(client, resposta["Location"]).status_code == 200
    ), "seguir o redirecionamento não chegou ao resultado"


def test_healthz_com_barra_nao_vira_caminho_novo_para_a_sonda(client):
    """`/healthz` é rota de MÁQUINA (`armadilhas/086`: uma sonda ganhando uma
    gêmea sem querer). Redirecionar é aceitável; responder como a nua, não."""
    resposta = pegar(client, "/healthz/")
    assert resposta.status_code != 200
    if resposta.status_code == 302:
        assert resposta["Location"] == "/healthz"


def test_e_302_e_nunca_301(client, quiz_a):
    """301 fica cacheado no navegador quase para sempre: se `/…/resultado/`
    ganhar rota própria amanhã, quem já visitou nunca mais a alcança."""
    resposta = pegar(client, f"/quiz/{quiz_a.slug}/resultado/")
    assert resposta.status_code == 302


# ---------------------------------------------------------------------------
# As fronteiras deliberadas
# ---------------------------------------------------------------------------


def test_post_com_barra_nao_e_redirecionado(client, quiz_a):
    """Um 302 num POST vira GET e o corpo é descartado em silêncio. O POST desta
    célula é a RESPOSTA do quiz — com as opções, o e-mail e o nome. Um lead
    redirecionado é um lead perdido sem erro, sem log e sem linha no banco."""
    resposta = client.post(f"/quiz/{quiz_a.slug}/resultado/", HTTP_HOST=HOST)
    assert resposta.status_code != 302, (
        "POST com barra foi redirecionado — a resposta do quiz viraria um GET e "
        "o lead sumiria em silêncio"
    )
    assert Submission.objects.count() == 0


def test_caminho_que_nao_existe_nem_com_nem_sem_barra_segue_404(client, quiz_a):
    """Sem isto o middleware viraria um 302 universal para qualquer typo."""
    assert pegar(client, "/nao-existe/").status_code == 404
    assert pegar(client, "/nao-existe").status_code == 404


def test_a_raiz_nao_e_tocada(client):
    """A raiz desta célula não é rota. O middleware tem de deixá-la em paz — e
    não transformá-la na string vazia, que é o que um `rstrip("/")` ingênuo faria
    e que deixaria o `Location` inválido."""
    assert pegar(client, "/").status_code == 404


def test_host_desconhecido_continua_404_mesmo_com_barra(client, quiz_a):
    """O CONV-SITE fecha para host não cadastrado, e o middleware não pode virar
    uma porta lateral em volta dele: a regra 2 pergunta ao urlconf, mas quem
    responde 404 aqui é a resolução de site — e ela continua mandando."""
    for caminho in (f"/quiz/{quiz_a.slug}/", f"/quiz/{quiz_a.slug}/resultado/"):
        resposta = client.get(caminho, HTTP_HOST="nao-cadastrado.exemplo.com")
        assert resposta.status_code == 404, (
            f"{caminho} respondeu {resposta.status_code} para um host que não "
            "está cadastrado"
        )
