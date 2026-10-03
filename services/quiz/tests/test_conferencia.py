"""Conferência dos links: só lê, cobre as faixas e leva a origem até a saída."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import RequestFactory, override_settings

from apps.quiz.conferencia import conferencia
from apps.quiz.conteudo import importar_documento
from apps.quiz.destinos import conectar_checkouts
from apps.quiz.models import OutboxEvent, ResultBand, Submission, TelemetryEvent
from tests.test_importar_quiz import site  # noqa: F401

pytestmark = pytest.mark.django_db
TOKEN = "token-de-teste"
ARQUIVO = (
    Path(__file__).resolve().parents[1]
    / "apps/quiz/conteudos/encontre-sua-solucao-demonstracao.json"
)
DESAFIO = "https://loja.exemplo.com/desafio/?ref=quiz"
CURSO = "https://loja.exemplo.com/curso"


@pytest.fixture
def quiz(site):  # noqa: F811
    return importar_documento(json.loads(ARQUIVO.read_text(encoding="utf-8")), site)


def pedir(quiz, consulta="", token=TOKEN, metodo="get"):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    request = getattr(RequestFactory(), metodo)(
        f"/x?site_id={quiz.site_id}&{consulta}", **cabecalhos
    )
    return conferencia(request, quiz.slug)


def _dados(resposta):
    assert resposta.status_code == 200, resposta.content
    return json.loads(resposta.content)


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_b2_cobre_todas_as_somas_e_mostra_as_duas_ofertas(quiz):
    dados = _dados(pedir(quiz, "v=B2&fmt=text&seg=geral"))
    (b2,) = dados["versoes"]
    assert b2["pontuacao"] == {"min": 0, "max": 12, "possiveis": list(range(13))}
    assert [(f["key"], f["min"], f["max"]) for f in b2["faixas"]] == [
        ("primeiros-passos", 0, 6),
        ("acelerar", 7, 12),
    ]
    assert all(f["alcancavel"] and f["demonstracao"] for f in b2["faixas"])
    limite = b2["faixas"][1]["exemplos"][0]
    assert limite["pontuacao"] == 7
    assert sum(r["pontos"] for r in limite["respostas"]) == 7
    assert b2["problemas"] == []
    assert any("demonstração" in aviso for aviso in b2["avisos"])
    assert dados["resumo"]["problemas"] == 0


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_saida_leva_os_parametros_da_campanha_e_nada_e_gravado(quiz):
    b2 = quiz.versions.get(key="B2")
    b2.experience["formats"]["video"] = {"headline": "Assista e responda", "video_url": None}
    b2.save(update_fields=["experience"])
    conectar_checkouts(
        quiz, {"oferta-primeiros-passos": DESAFIO, "oferta-acelerar": CURSO}
    )
    antes = (
        Submission.objects.count(),
        TelemetryEvent.objects.count(),
        OutboxEvent.objects.count(),
    )
    dados = _dados(
        pedir(
            quiz,
            "v=B2&fmt=video&seg=escalando&src=meta&med=cpc&cpg=qz_escalando_oct26"
            "&ctv=vsl_47s&utm_source=meta&utm_medium=cpc&utm_campaign=qz_escalando_oct26"
            "&utm_content=vsl_47s_cta_comprar&utm_term=quiz",
        )
    )
    assert (
        Submission.objects.count(),
        TelemetryEvent.objects.count(),
        OutboxEvent.objects.count(),
    ) == antes
    (link,) = dados["links"]
    assert link["problemas"] == []
    saidas = {s["faixa"]: s for s in link["saidas"]}
    assert set(saidas) == {"primeiros-passos", "acelerar"}
    curso = parse_qs(urlsplit(saidas["acelerar"]["url_final"]).query)
    assert {k: v[0] for k, v in curso.items()} == {
        "v": "B2",
        "fmt": "video",
        "seg": "escalando",
        "src": "meta",
        "med": "cpc",
        "cpg": "qz_escalando_oct26",
        "ctv": "vsl_47s",
        "utm_source": "meta",
        "utm_medium": "cpc",
        "utm_campaign": "qz_escalando_oct26",
        "utm_content": "vsl_47s_cta_comprar",
        "utm_term": "quiz",
    }
    desafio = saidas["primeiros-passos"]["url_final"]
    assert desafio.startswith(DESAFIO + "&") and saidas["primeiros-passos"]["faltam"] == []
    (experiencia,) = dados["experiencias"]
    assert experiencia["video"] == "pendente"
    assert 'class="video-pendente"' in experiencia["marcas"]
    assert 'data-versao="B2"' in experiencia["marcas"]
    teste = parse_qs(urlsplit(experiencia["teste_url"]).query)
    assert teste["src"] == ["teste"] and teste["v"] == ["B2"]


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_sem_campanha_na_tela_cada_saida_real_e_provada_com_os_12_parametros(quiz):
    # Conferir "todos os links" não traz campanha: a prova usa um anúncio com
    # a origem completa, com src e utm_source diferentes, e os dois chegam.
    conectar_checkouts(
        quiz, {"oferta-primeiros-passos": DESAFIO, "oferta-acelerar": CURSO}
    )
    dados = _dados(pedir(quiz, "v=B2&fmt=text&seg=geral"))
    (b2,) = dados["versoes"]
    provas = {f["key"]: f["prova_origem"] for f in b2["faixas"]}
    assert all(p["faltam"] == [] for p in provas.values())
    curso = parse_qs(urlsplit(provas["acelerar"]["url_final"]).query)
    assert {k: v[0] for k, v in curso.items()} == {
        "v": "B2",
        "fmt": "text",
        "seg": "frio",
        "src": "meta",
        "med": "cpc",
        "cpg": "prova_da_origem",
        "ctv": "anuncio_de_prova",
        "utm_source": "facebook",
        "utm_medium": "paid_social",
        "utm_campaign": "prova_utm_campaign",
        "utm_content": "prova_utm_content",
        "utm_term": "prova_utm_term",
    }
    # O destino que já traz um parâmetro fica como está.
    assert provas["primeiros-passos"]["url_final"].startswith(DESAFIO + "&")
    assert b2["problemas"] == []


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_oferta_de_demonstracao_nao_tem_prova_de_saida(quiz):
    dados = _dados(pedir(quiz, "v=B2&fmt=text&seg=geral"))
    (b2,) = dados["versoes"]
    assert all(f["prova_origem"] is None for f in b2["faixas"])


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_aponta_soma_sem_faixa_faixa_impossivel_e_destino_trocado(quiz):
    conectar_checkouts(
        quiz, {"oferta-primeiros-passos": DESAFIO, "oferta-acelerar": CURSO}
    )
    b2 = quiz.versions.get(key="B2")
    ResultBand.objects.filter(version=b2, key="primeiros-passos").update(max_score=5)
    ResultBand.objects.filter(version=b2, key="acelerar").update(
        min_score=13, max_score=20, botao_destino="https://outra.exemplo.com/"
    )
    dados = _dados(pedir(quiz, "v=B2&fmt=text&seg=geral"))
    (versao,) = dados["versoes"]
    texto = " ".join(versao["problemas"] + versao["avisos"])
    assert "6, 7, 8, 9, 10, 11, 12 pontos fica sem resultado" in texto
    assert "acelerar (13 a 20 pontos) nunca acontece" in texto
    assert "outra.exemplo.com" in texto
    assert dados["resumo"]["problemas"] >= 2


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_calculadora_e_ia_aparecem_na_conferencia(quiz, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dados = _dados(pedir(quiz, "v=B2&fmt=calc,ai&seg=geral"))
    por_formato = {e["fmt"]: e for e in dados["experiencias"]}
    assert por_formato["calc"]["calculo"]["result_label"]
    assert 'id="experiencia-calculadora"' in por_formato["calc"]["marcas"]
    assert por_formato["ai"]["ia"] is False
    assert any("perguntas em botões" in a for a in por_formato["ai"]["avisos"])
    assert dados["ia_ligada"] is False


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_conferencia_exige_bearer_get_e_site(quiz):
    assert pedir(quiz, token=None).status_code == 401
    assert pedir(quiz, token="errado").status_code == 401
    assert pedir(quiz, metodo="post").status_code == 405
    assert pedir(quiz, "v=B9").status_code == 422
