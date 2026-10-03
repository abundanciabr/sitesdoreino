import importlib
import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.apps import apps
from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone

from apps.quiz.management.commands.seed_laboratorio_crivo import (
    EMAIL,
    SLUG,
    semear_laboratorio,
)
from apps.quiz.models import (
    Option,
    OutboxEvent,
    Question,
    Quiz,
    QuizVersion,
    ResultBand,
    Site,
    Submission,
    TelemetryEvent,
)
from apps.quiz.views import COOKIE_SESSAO, SALT_SESSAO, MAX_AGE_SESSAO

pytestmark = pytest.mark.django_db
HOST = "meshcraft.top"
UTM = {"source": "laboratorio", "campaign": SLUG, "content": "foco"}


@pytest.fixture
def laboratorio():
    site = Site.objects.create(id="site-laboratorio", host=HOST, name="Laboratório")
    return semear_laboratorio(site)


def rodada(quiz, chave="original", origem=None):
    cliente = Client()
    versao = quiz.versions.get(key=chave)
    entrada = {
        "session_id": str(uuid.uuid4()),
        "version_id": versao.id,
        "version_key": versao.key,
        "site_id": quiz.site_id,
        "utm": origem if origem is not None else UTM,
    }
    cliente.cookies[COOKIE_SESSAO] = signing.dumps(
        {"quizzes": {SLUG: entrada}}, salt=SALT_SESSAO
    )
    return cliente, versao, entrada


def enviar(cliente, versao, pontos, **extra):
    dados = {
        f"pergunta_{q.id}": q.options.get(points=p).id
        for q, p in zip(versao.questions.all(), pontos)
    }
    dados.update({"email": EMAIL, **extra})
    return cliente.post(f"/{SLUG}/", dados, HTTP_HOST=HOST)


@pytest.mark.parametrize("chave", ["original", "conversa"])
@pytest.mark.parametrize(
    "pontos,resultado",
    [
        ([0, 0, 0], "foco"),
        ([1, 0, 0], "foco"),
        ([2, 0, 0], "ritmo"),
        ([2, 1, 1], "ritmo"),
        ([2, 2, 1], "entrega"),
        ([2, 2, 2], "entrega"),
    ],
)
def test_as_fronteiras_das_duas_versoes_no_servidor(
    laboratorio, chave, pontos, resultado
):
    cliente, versao, _ = rodada(laboratorio, chave)
    resposta = enviar(cliente, versao, pontos, score=9999)
    assert resposta.status_code == 302
    gravada = Submission.objects.get()
    assert gravada.score == sum(pontos)
    assert gravada.result_key == resultado
    evento = OutboxEvent.objects.get()
    assert evento.payload["utm"] == UTM
    pagina = cliente.get(resposta["Location"], HTTP_HOST=HOST).content.decode()
    faixa = versao.bands.get(key=resultado)
    assert faixa.title in pagina and faixa.description in pagina
    assert faixa.botao_rotulo in pagina
    if resultado == "entrega":
        assert f'action="/{SLUG}/sair"' in pagina
        assert f'href="{faixa.botao_destino}"' not in pagina
    else:
        assert f'href="{faixa.botao_destino}"' in pagina


def test_o_semeador_preserva_crivo_e_edicoes_e_nao_duplica(laboratorio):
    crivo = Quiz.objects.create(
        site=laboratorio.site, slug="crivo", title="Crivo preservado"
    )
    pergunta = laboratorio.versions.get(key="original").questions.first()
    pergunta.text = "Texto editado pelo mantenedor"
    pergunta.save()
    quantidade = tuple(
        m.objects.count() for m in (Quiz, QuizVersion, Question, Option, ResultBand)
    )
    call_command("seed_laboratorio_crivo", host=HOST, stdout=StringIO())
    call_command("seed_laboratorio_crivo", host=HOST, stdout=StringIO())
    assert quantidade == tuple(
        m.objects.count() for m in (Quiz, QuizVersion, Question, Option, ResultBand)
    )
    pergunta.refresh_from_db()
    crivo.refresh_from_db()
    assert pergunta.text == "Texto editado pelo mantenedor"
    assert crivo.title == "Crivo preservado"
    assert list(laboratorio.versions.values_list("weight", flat=True)) == [100, 100]


def test_a_migracao_publica_no_site_existente_sem_criar_outro(laboratorio):
    migracao = importlib.import_module("apps.quiz.migrations.0005_laboratorio_crivo")
    migracao.semear(apps, None)
    migracao.semear(apps, None)
    assert Quiz.objects.count() == 1
    assert Site.objects.count() == 1


def test_site_nao_cadastrado_e_recusado_sem_gravar():
    with pytest.raises(CommandError, match="Confira o cadastro"):
        call_command("seed_laboratorio_crivo", host=HOST)
    assert Quiz.objects.count() == 0


def test_observacao_calcula_so_a_rodada_e_esconde_contato_e_origem_livre(laboratorio):
    # guarda: services/quiz/apps/quiz/management/commands/funil.py:27
    cliente, versao, entrada = rodada(
        laboratorio, origem={"content": "segredo-pessoal@exemplo.test"}
    )
    enviar(cliente, versao, [2, 1, 1], nome="NOME-SECRETO", telefone="TELEFONE-SECRETO")
    inicio = timezone.now()
    pergunta = versao.questions.first()
    for tipo, segundo in (
        ("view_quiz", 0),
        ("view_question", 1),
        ("click_option", 4),
        ("click_option", 6),
        ("abandon", 8),
    ):
        TelemetryEvent.objects.create(
            site_id=laboratorio.site_id,
            quiz_slug=SLUG,
            version_key=versao.key,
            session_id=entrada["session_id"],
            event_type=tipo,
            element_id=str(pergunta.id),
            metadata={"question_id": str(pergunta.id), "utm": entrada["utm"]},
            occurred_at=inicio + timedelta(seconds=segundo),
        )
    TelemetryEvent.objects.create(
        site_id=laboratorio.site_id,
        quiz_slug=SLUG,
        version_key=versao.key,
        session_id=entrada["session_id"],
        event_type="view_question",
        element_id=f"{pergunta.id}:\nCONTATO-ADULTERADO@exemplo.test",
        metadata={"utm": entrada["utm"]},
        occurred_at=inicio,
    )
    # Outra rodada não entra no relatório do navegador.
    TelemetryEvent.objects.create(
        site_id=laboratorio.site_id,
        quiz_slug=SLUG,
        version_key=versao.key,
        session_id=uuid.uuid4(),
        event_type="view_quiz",
        metadata={},
        occurred_at=inicio,
    )
    resposta = cliente.get(f"/{SLUG}/observacao/", HTTP_HOST=HOST)
    rodada_atual = resposta.context["rodada"]
    assert rodada_atual["visitas"] == 1
    assert rodada_atual["submissao"].score == 4
    assert "conversao: 1 de 1" in rodada_atual["relatorio"]
    assert rodada_atual["relatorio"].count("conversao:") == 1
    assert "hesitaram 1" in rodada_atual["relatorio"]
    assert "tempo medio 3.0s" in rodada_atual["relatorio"]
    html = resposta.content.decode()
    for segredo in (
        EMAIL,
        "NOME-SECRETO",
        "TELEFONE-SECRETO",
        entrada["session_id"],
        "segredo-pessoal@exemplo.test",
        "CONTATO-ADULTERADO@exemplo.test",
    ):
        assert segredo not in html
    assert len(rodada_atual["respostas"]) == 3


def test_eventos_sinteticos_separados_sem_ligar_a_uma_resposta(laboratorio):
    cliente, versao, _ = rodada(laboratorio)
    enviar(cliente, versao, [0, 0, 0])
    evento = OutboxEvent.objects.get()
    evento.published_at = None
    evento.save()
    OutboxEvent.objects.create(
        event="quiz.completado",
        payload={
            "site_id": "outro-site",
            "quiz_slug": SLUG,
            "lead": {"email": EMAIL},
            "utm": UTM,
        },
    )
    OutboxEvent.objects.create(
        event="quiz.completado",
        payload={
            "site_id": laboratorio.site_id,
            "quiz_slug": SLUG,
            "lead": {"email": "outra-pessoa@exemplo.test"},
            "utm": UTM,
        },
    )
    pagina = cliente.get(f"/{SLUG}/observacao/", HTTP_HOST=HOST)
    assert pagina.context["pendentes"] == 1 and pagina.context["entregues"] == 0
    evento.published_at = timezone.now()
    evento.save()
    pagina = cliente.get(f"/{SLUG}/observacao/", HTTP_HOST=HOST)
    assert pagina.context["pendentes"] == 0 and pagina.context["entregues"] == 1


def test_observacao_sem_rodada_e_entre_sites(laboratorio):
    outro = Site.objects.create(
        id="outro-site", host="outro.exemplo.test", name="Outro"
    )
    semear_laboratorio(outro)
    cliente, versao, _ = rodada(laboratorio)
    enviar(cliente, versao, [2, 2, 2])
    pagina = cliente.get(f"/{SLUG}/observacao/", HTTP_HOST=outro.host)
    assert pagina.context["rodada"] is None
    cliente.cookies[COOKIE_SESSAO] = "cookie-invalido"
    pagina = cliente.get(f"/{SLUG}/observacao/", HTTP_HOST=HOST)
    assert "Abra o laboratório" in pagina.content.decode()
    assert cliente.get("/crivo/observacao/", HTTP_HOST=HOST).status_code == 404


def test_sessao_expirada_abre_nova_rodada_e_resultado_inexistente_e_404(
    laboratorio, monkeypatch
):
    cliente, _, entrada = rodada(laboratorio)
    import time

    instante = time.time()
    monkeypatch.setattr(time, "time", lambda: instante + MAX_AGE_SESSAO + 10)
    pagina = cliente.get(f"/{SLUG}/", HTTP_HOST=HOST)
    assert pagina.status_code == 200
    cookie = signing.loads(cliente.cookies[COOKIE_SESSAO].value, salt=SALT_SESSAO)
    assert cookie["quizzes"][SLUG]["session_id"] != entrada["session_id"]
    assert (
        cliente.get(
            f"/{SLUG}/resultado?lead={uuid.uuid4()}", HTTP_HOST=HOST
        ).status_code
        == 404
    )


def test_pergunta_vazia_e_sem_faixa_ou_botao(laboratorio):
    cliente, versao, _ = rodada(laboratorio)
    resposta = cliente.post(f"/{SLUG}/", {"email": EMAIL}, HTTP_HOST=HOST)
    assert resposta.status_code == 422 and Submission.objects.count() == 0
    versao.bands.all().delete()
    resposta = enviar(cliente, versao, [1, 1, 1])
    pagina = cliente.get(resposta["Location"], HTTP_HOST=HOST).content.decode()
    assert "Recebemos suas respostas" in pagina
    assert "Refazer o quiz" in pagina
    assert Submission.objects.get().result_key == "sem_faixa"


def test_sem_versao_elegivel_e_404_sem_gravar(laboratorio):
    laboratorio.versions.update(weight=0)
    assert Client().get(f"/{SLUG}/", HTTP_HOST=HOST).status_code == 404
    assert Submission.objects.count() == 0
