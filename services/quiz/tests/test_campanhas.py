import json
import uuid
from datetime import datetime, timezone
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.quiz.campanhas import relatorio_campanhas
from apps.quiz.models import Quiz, QuizVersion, Site, Submission, TelemetryEvent


pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz():
    site = Site.objects.create(
        id="site-campanhas", host="campanhas.exemplo.com", name="Campanhas"
    )
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    QuizVersion.objects.create(quiz=quiz, key="a")
    return quiz


def instante(dia, hora):
    return datetime(2026, 9, dia, hora, tzinfo=timezone.utc)


def evento(quiz, sessao, tipo, quando, utm=None, version_key="a", context=None):
    return TelemetryEvent.objects.create(
        session_id=sessao,
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        version_key=version_key,
        event_type=tipo,
        metadata={
            "utm": utm or {},
            **({"context": context} if context is not None else {}),
        },
        occurred_at=quando,
    )


def submissao(quiz, sessao, utm=None, context=None, version=None, site_id=None):
    return Submission.objects.create(
        quiz=quiz,
        version=version or quiz.versions.get(key="a"),
        session_id=sessao,
        site_id=site_id or quiz.site_id,
        score=1,
        result_key="alto",
        answers={},
        lead_email="privado@exemplo.com",
        utm=utm or {},
        context=context or {},
    )


def test_primeira_visita_fixa_dia_campanha_e_versao_mesmo_com_refresh_e_saida_depois(
    quiz,
):
    sessao = uuid.uuid4()
    utm = {"source": "ig", "medium": "cpc", "campaign": "oferta", "content": "a"}
    evento(quiz, sessao, "view_quiz", instante(21, 2), utm)
    evento(quiz, sessao, "view_quiz", instante(22, 4), {"source": "outra"}, "b")
    evento(quiz, sessao, "checkout_exit", instante(23, 4), {"source": "outra"}, "a")
    evento(quiz, sessao, "checkout_exit", instante(23, 5), {"source": "outra"}, "a")
    submissao(quiz, sessao, utm)

    relatorio = relatorio_campanhas(quiz, inicio="2026-09-20", fim="2026-09-20")
    assert len(relatorio["campanhas"]) == 1
    linha = relatorio["campanhas"][0]
    assert {
        chave: linha[chave]
        for chave in (
            "dia_origem",
            "source",
            "medium",
            "campaign",
            "content",
            "version_key",
        )
    } == {
        "dia_origem": "2026-09-20",
        "source": "ig",
        "medium": "cpc",
        "campaign": "oferta",
        "content": "a",
        "version_key": "a",
    }
    assert (linha["visitas"], linha["submissoes"], linha["saidas"]) == (1, 1, 1)
    assert relatorio_campanhas(quiz, inicio="2026-09-22")["campanhas"] == []


def test_perdas_e_submissoes_sem_visita_nao_criam_denominador(quiz):
    utm = {"source": "email", "campaign": "lancamento"}
    concluir = uuid.uuid4()
    visitar = uuid.uuid4()
    evento(quiz, concluir, "view_quiz", instante(21, 15), utm)
    evento(quiz, visitar, "view_quiz", instante(21, 15), utm)
    submissao(quiz, concluir, utm)
    submissao(quiz, uuid.uuid4(), {"source": "sem-vista"})
    relatorio = relatorio_campanhas(quiz)
    linha = relatorio["campanhas"][0]
    assert (linha["visitas"], linha["submissoes"], linha["saidas"]) == (2, 1, 0)
    assert linha["perda_ate_conclusao"] == linha["conclusoes_sem_clique"] == 1
    assert len(linha["alertas"]) == 2
    avulsa = relatorio["sem_visita_registrada"][0]
    assert avulsa["submissoes"] == 1
    assert avulsa["dia_origem"] is None and avulsa["visitas"] is None
    assert "privado@" not in json.dumps(relatorio)


def test_comando_json_e_validacao_de_datas_e_site(quiz):
    outro = Site.objects.create(id="outro", host="outro.exemplo.com", name="Outro")
    Quiz.objects.create(site=outro, slug=quiz.slug, title="Outro")
    saida = StringIO()
    call_command(
        "campanhas",
        slug=quiz.slug,
        site_id=quiz.site_id,
        inicio="2026-09-20",
        fim="2026-09-21",
        stdout=saida,
    )
    assert json.loads(saida.getvalue())["site_id"] == quiz.site_id
    with pytest.raises(CommandError, match="--site-id"):
        call_command("campanhas", slug=quiz.slug)
    with pytest.raises(CommandError, match="AAAA-MM-DD"):
        call_command(
            "campanhas", slug=quiz.slug, site_id=quiz.site_id, inicio="21/09/2026"
        )
    with pytest.raises(CommandError, match="posterior"):
        call_command(
            "campanhas",
            slug=quiz.slug,
            site_id=quiz.site_id,
            inicio="2026-09-22",
            fim="2026-09-21",
        )


def test_contexto_direcionado_separa_campanhas_sem_confundir_utm(quiz):
    utm = {
        "source": "ig",
        "medium": "paid",
        "campaign": "externa",
        "content": "criativo",
    }
    primeiro = uuid.uuid4()
    segundo = uuid.uuid4()
    base = {
        "fmt": "text",
        "seg": "iniciante",
        "src": "parceria",
        "med": "email",
        "cpg": "interna",
        "ctv": "A",
    }
    outro = {**base, "ctv": "B"}
    evento(quiz, primeiro, "view_quiz", instante(21, 15), utm, context=base)
    evento(quiz, segundo, "view_quiz", instante(21, 15), utm, context=outro)
    evento(quiz, primeiro, "view_quiz", instante(22, 15), utm, context=outro)
    submissao(quiz, primeiro, utm, context=outro)
    relatorio = relatorio_campanhas(quiz)
    assert [
        (linha["ctv"], linha["visitas"], linha["submissoes"])
        for linha in relatorio["campanhas"]
    ] == [("A", 1, 1), ("B", 1, 0)]
    assert all(
        linha["source"] == "ig" and linha["src"] == "parceria"
        for linha in relatorio["campanhas"]
    )


def test_contexto_avulso_e_legado(quiz):
    sessao = uuid.uuid4()
    evento(quiz, sessao, "view_quiz", instante(21, 15))
    submissao(quiz, sessao)
    submissao(
        quiz, uuid.uuid4(), context={"fmt": "video", "seg": "avancado", "src": "email"}
    )
    relatorio = relatorio_campanhas(quiz)
    assert all(
        relatorio["campanhas"][0][campo] == ""
        for campo in ("fmt", "seg", "src", "med", "cpg", "ctv")
    )
    avulsa = relatorio["sem_visita_registrada"][0]
    assert (avulsa["fmt"], avulsa["seg"], avulsa["src"]) == (
        "video",
        "avancado",
        "email",
    )
    assert avulsa["visitas"] is None


def test_conclusao_e_saida_exigem_site_sessao_e_versao_correspondentes(quiz):
    outra_versao = QuizVersion.objects.create(quiz=quiz, key="b")
    visita_sem_conclusao = uuid.uuid4()
    visita_certa = uuid.uuid4()
    outro_site = uuid.uuid4()
    evento(quiz, visita_sem_conclusao, "view_quiz", instante(21, 15))
    evento(quiz, visita_certa, "view_quiz", instante(21, 15))
    evento(quiz, outro_site, "view_quiz", instante(21, 15))
    submissao(quiz, visita_sem_conclusao, version=outra_versao)
    submissao(quiz, visita_certa)
    submissao(quiz, outro_site, site_id="site-alheio")
    evento(quiz, visita_sem_conclusao, "checkout_exit", instante(22, 15))
    evento(quiz, visita_certa, "checkout_exit", instante(22, 15), version_key="b")
    evento(quiz, visita_certa, "checkout_exit", instante(22, 16))
    evento(quiz, outro_site, "checkout_exit", instante(22, 16))

    relatorio = relatorio_campanhas(quiz)
    linha = relatorio["campanhas"][0]
    assert (linha["visitas"], linha["submissoes"], linha["saidas"]) == (3, 1, 1)
    assert relatorio["submissoes_sem_correspondencia"][0]["submissoes"] == 1
    assert relatorio["submissoes_sem_correspondencia"][0]["visitas"] is None
    assert "compra" not in json.dumps(relatorio).lower()


def test_periodo_cli_exige_data_iso_com_hifens(quiz):
    with pytest.raises(CommandError, match="AAAA-MM-DD"):
        call_command("campanhas", slug=quiz.slug, inicio="20260921")
