import uuid
from datetime import datetime, timezone

import pytest

from apps.quiz.campanhas import funil_por_etapa, relatorio_campanhas
from apps.quiz.models import (
    Question,
    Quiz,
    QuizVersion,
    Site,
    Submission,
    TelemetryEvent,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz():
    site = Site.objects.create(id="site-funil", host="funil.exemplo.com", name="Funil")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    versao = QuizVersion.objects.create(quiz=quiz, key="a")
    Question.objects.create(version=versao, order=1, text="Primeira")
    Question.objects.create(version=versao, order=2, text="Segunda")
    return quiz


def instante(dia, hora=15):
    return datetime(2026, 10, dia, hora, tzinfo=timezone.utc)


def evento(quiz, sessao, tipo, quando, element_id="", metadata=None, versao="a"):
    return TelemetryEvent.objects.create(
        session_id=sessao,
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        version_key=versao,
        event_type=tipo,
        element_id=element_id,
        metadata=metadata or {},
        occurred_at=quando,
    )


def abre(quiz, sessao, dia=1, context=None, utm=None):
    meta = {"utm": utm or {}}
    if context is not None:
        meta["context"] = context
    return evento(quiz, sessao, "view_quiz", instante(dia), metadata=meta)


def conclui(quiz, sessao, context=None):
    return Submission.objects.create(
        quiz=quiz,
        version=quiz.versions.get(key="a"),
        session_id=sessao,
        site_id=quiz.site_id,
        score=1,
        result_key="alto",
        answers={},
        lead_email="privado@exemplo.com",
        context=context or {},
    )


def etapa(funil, posicao):
    return funil["versoes"][0]["etapas"][posicao]


def test_funil_por_etapa_conta_sessoes_distintas_e_nao_infla_com_refresh(quiz):
    p1, p2 = [str(q.id) for q in quiz.versions.get(key="a").questions.all()]
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    for sessao in (a, b, c):
        abre(quiz, sessao)
    # a atualiza a página duas vezes: nada disso cria visita ou etapa nova
    abre(quiz, a, dia=1)
    abre(quiz, a, dia=1)
    for sessao in (a, b, c):
        evento(quiz, sessao, "view_question", instante(1), p1)
        evento(quiz, sessao, "click_option", instante(1), "7", {"question_id": p1})
    evento(quiz, a, "view_question", instante(1), p1)
    evento(quiz, a, "click_option", instante(1), "8", {"question_id": p1})
    for sessao in (a, b):
        evento(quiz, sessao, "view_question", instante(1, 16), p2)
    # c abandona na primeira pergunta; atualizar também emite abandono, e conta uma vez
    evento(quiz, c, "abandon", instante(1, 16), p1)
    evento(quiz, c, "abandon", instante(1, 17), p1)
    # a conclui e sai pelo checkout real; b abandona na segunda pergunta
    conclui(quiz, a)
    evento(quiz, a, "checkout_exit", instante(1, 18), "alto", {})
    evento(quiz, b, "abandon", instante(1, 18), p2)

    funil = funil_por_etapa(quiz)
    versao = funil["versoes"][0]
    assert funil["periodo"]["fuso"] == "America/Sao_Paulo"
    assert "sessões distintas" in funil["denominador"]
    assert versao["visitas_elegiveis"] == 3
    primeira, segunda, lead = versao["etapas"]
    assert (primeira["viram"], primeira["clicaram"], primeira["abandonaram"]) == (3, 3, 1)
    assert primeira["avancaram"] == 2 and primeira["perda"] == 1
    assert primeira["taxa_abandono"]["numerador"] == 1
    assert primeira["taxa_abandono"]["denominador"] == 3
    assert primeira["taxa_abandono"]["inconclusiva"] is True
    assert (segunda["viram"], segunda["abandonaram"]) == (2, 1)
    assert segunda["avancaram"] == 1  # conclusões
    assert lead["viram"] is None and lead["medida"] is False
    assert versao["conclusoes"] == 1
    assert versao["saidas_reais"] == 1 and versao["saidas_demonstracao"] == 0
    assert versao["taxa_conclusao"]["numerador"] == 1
    assert versao["taxa_conclusao"]["denominador"] == 3


def test_abandono_por_atualizacao_nao_conta_quando_a_sessao_segue_adiante(quiz):
    p1, p2 = [str(q.id) for q in quiz.versions.get(key="a").questions.all()]
    sessao = uuid.uuid4()
    abre(quiz, sessao)
    evento(quiz, sessao, "view_question", instante(1), p1)
    evento(quiz, sessao, "abandon", instante(1, 16), p1)  # atualizou a página
    abre(quiz, sessao)
    evento(quiz, sessao, "view_question", instante(1, 17), p1)
    evento(quiz, sessao, "view_question", instante(1, 17), p2)
    versao = funil_por_etapa(quiz)["versoes"][0]
    assert versao["etapas"][0]["abandonaram"] == 0
    assert versao["etapas"][1]["abandonaram"] == 0


def test_saida_de_demonstracao_e_distinta_da_saida_real(quiz):
    reais, demos = uuid.uuid4(), uuid.uuid4()
    for sessao in (reais, demos):
        abre(quiz, sessao)
        conclui(quiz, sessao)
    evento(quiz, reais, "checkout_exit", instante(1, 18), "alto", {})
    evento(quiz, demos, "checkout_exit", instante(1, 18), "alto", {"demonstracao": True})
    versao = funil_por_etapa(quiz)["versoes"][0]
    assert versao["saidas"] == 2
    assert versao["saidas_reais"] == 1
    assert versao["saidas_demonstracao"] == 1
    assert versao["conclusoes_sem_saida"] == 0
    linha = relatorio_campanhas(quiz)["campanhas"][0]
    assert (linha["saidas"], linha["saidas_reais"], linha["saidas_demonstracao"]) == (2, 1, 1)


def test_trafego_de_teste_fica_fora_das_taxas_e_conclusao_sem_visita_e_contada_a_parte(
    quiz,
):
    real, teste_src, teste_cpg, sem_visita = (uuid.uuid4() for _ in range(4))
    abre(quiz, real, context={"src": "instagram", "cpg": "outubro"})
    abre(quiz, teste_src, context={"src": "teste"})
    abre(quiz, teste_cpg, context={"cpg": "Teste-interno"})
    conclui(quiz, teste_src, context={"src": "teste"})
    conclui(quiz, sem_visita)
    funil = funil_por_etapa(quiz)
    assert funil["visitas_elegiveis"] == 1
    assert funil["teste"] == {"visitas": 2, "conclusoes": 1, "conclusoes_sem_visita": 0}
    assert funil["conclusoes_sem_visita"] == 1
    versao = funil["versoes"][0]
    assert versao["visitas_elegiveis"] == 1 and versao["conclusoes"] == 0
    assert versao["teste"] == {"visitas": 2, "conclusoes": 1}


def test_periodo_usa_o_dia_da_primeira_visita_em_sao_paulo(quiz):
    noite = uuid.uuid4()
    # 01h UTC do dia 2 ainda é dia 1 em São Paulo
    evento(quiz, noite, "view_quiz", datetime(2026, 10, 2, 1, tzinfo=timezone.utc))
    dia_1 = funil_por_etapa(quiz, "2026-10-01", "2026-10-01")
    dia_2 = funil_por_etapa(quiz, "2026-10-02", "2026-10-02")
    assert dia_1["versoes"][0]["visitas_elegiveis"] == 1
    assert dia_2["versoes"][0]["visitas_elegiveis"] == 0
    assert dia_1["periodo"] == {
        "inicio": "2026-10-01",
        "fim": "2026-10-01",
        "fuso": "America/Sao_Paulo",
    }


def test_colunas_comerciais_dizem_sem_dados_de_compra_na_leitura(quiz):
    abre(quiz, uuid.uuid4())
    versao = funil_por_etapa(quiz)["versoes"][0]
    assert versao["comercial"]["estado"] == "sem dados de compra"
    assert versao["comercial"]["receita"] is None and versao["comercial"]["ltv"] is None


def test_relatorio_traz_utm_term_e_o_funil(quiz):
    sessao = uuid.uuid4()
    abre(quiz, sessao, utm={"source": "g", "term": "lucro"})
    relatorio = relatorio_campanhas(quiz)
    assert relatorio["campanhas"][0]["term"] == "lucro"
    assert relatorio["fuso"] == "America/Sao_Paulo"
    assert relatorio["funil"]["versoes"][0]["visitas_elegiveis"] == 1
