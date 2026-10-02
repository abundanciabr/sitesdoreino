"""Tela de evolução do quiz: leitura de gargalos e propostas, via API privada."""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo/sites/by-host/testserver"
BASE = "http://quiz:8000/interno/editor/quizzes/campanha"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", "http://catalogo:8000/api/catalogo")
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "quiz-teste")


def _cliente():
    respx.get(IDENTIDADE).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "dono-id",
                "nome_exibido": "Dono",
                "papel": None,
                "email": "dono@exemplo.com",
            },
        )
    )
    respx.get(CATALOGO).mock(
        return_value=httpx.Response(
            200, json={"id": "site-teste", "host": "testserver", "menu": {}}
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


LEITURA = {
    "periodo": {"inicio": "2026-10-01", "fim": "2026-10-02", "fuso": "America/Sao_Paulo"},
    "denominador": "sessões distintas com abertura do quiz registrada, sem tráfego de teste",
    "amostra_minima": 30,
    "visitas_elegiveis": 40,
    "teste": {"visitas": 2, "conclusoes": 1},
    "gargalos": [
        {
            "id": "etapa:geral:B1:7",
            "prioridade": "alta",
            "version_key": "B1",
            "escopo": {"nome": "Todas as visitas"},
            "evidencia": {"texto": "Pergunta 1: perda (30 de 40, 75%)"},
            "observacao": "",
        }
    ],
    "dados_faltantes": [{"tipo": "versao_sem_visitas", "texto": "A versão B2 está ativa e não teve visitas."}],
    "por_dia": [
        {
            "nome": "2026-10-01",
            "sessoes": 40,
            "versoes": [{"version_key": "B1", "conclusoes": 8, "taxa_conclusao": {"denominador": 40, "inconclusiva": False}}],
            "gargalos": [],
        }
    ],
    "por_campanha": [],
    "comparacoes": {"aviso": "Campanhas são direcionadas, não aleatórias."},
    "funil": [
        {
            "version_key": "B1",
            "ativa": True,
            "visitas_elegiveis": 40,
            "conclusoes": 8,
            "saidas_reais": 1,
            "saidas_demonstracao": 3,
            "conclusoes_sem_saida": 4,
            "taxa_conclusao": {"denominador": 40, "inconclusiva": False},
            "taxa_saida_total": {"denominador": 8},
            "etapas": [
                {
                    "etapa": "7",
                    "rotulo": "Pergunta 1: Primeira",
                    "medida": True,
                    "viram": 40,
                    "clicaram": 35,
                    "abandonaram": 5,
                    "avancaram": 10,
                    "perda": 30,
                    "taxa_abandono": {"denominador": 40, "inconclusiva": False},
                    "taxa_perda": {"denominador": 40, "inconclusiva": False},
                },
                {
                    "etapa": "lead",
                    "rotulo": "Cadastro e envio",
                    "medida": False,
                    "viram": None,
                    "clicaram": None,
                    "abandonaram": 0,
                    "avancaram": None,
                    "perda": None,
                    "taxa_abandono": None,
                    "taxa_perda": None,
                },
            ],
        }
    ],
}
PROPOSTA = {
    "id": 5,
    "versao_base": "B1",
    "gargalo": "etapa:geral:B1:7",
    "hipotese": "Pergunta curta segura mais gente.",
    "prioridade": "alta",
    "mudanca": "Encurtar a pergunta 1.",
    "key_sugerida": "B3",
    "estado": "aceita",
    "criar_no_estudio": {"key": "B3", "mensagem": "Crie a versão B3 no estúdio. A versão B1 não foi alterada."},
}


@respx.mock
def test_tela_mostra_funil_gargalos_dados_faltantes_e_propostas():
    cliente = _cliente()
    leitura = respx.get(BASE + "/evolucao").mock(return_value=httpx.Response(200, json=LEITURA))
    respx.get(BASE + "/propostas").mock(
        return_value=httpx.Response(200, json={"propostas": [PROPOSTA]})
    )
    url = reverse("quiz_evolucao", kwargs={"slug": "campanha"})
    assert url == "/conteudos/quiz/campanha/evolucao" or url.endswith("/conteudos/quiz/campanha/evolucao")
    pagina = cliente.get(url, {"inicio": "2026-10-01", "fim": "2026-10-02"})
    assert pagina.status_code == 200
    texto = pagina.content.decode()
    assert "America/Sao_Paulo" in texto and "sessões distintas" in texto
    assert "30 de 40, 75%" in texto and "alta" in texto
    assert "Pergunta 1: Primeira" in texto
    assert "1 para o checkout real e 3 de demonstração" in texto
    assert "sem dados de compra" in texto
    assert "A versão B2 está ativa e não teve visitas." in texto
    assert "não aleatórias" in texto
    assert "Crie a versão B3 no estúdio" in texto
    assert "privado@" not in texto
    assert dict(leitura.calls.last.request.url.params) == {
        "site_id": "site-teste",
        "inicio": "2026-10-01",
        "fim": "2026-10-02",
    }


@respx.mock
def test_criar_proposta_envia_so_os_campos_e_redireciona():
    cliente = _cliente()
    criar = respx.post(BASE + "/propostas").mock(
        return_value=httpx.Response(201, json=PROPOSTA)
    )
    url = reverse("quiz_evolucao", kwargs={"slug": "campanha"})
    resposta = cliente.post(
        url,
        {
            "acao": "criar",
            "versao_base": "B1",
            "gargalo": "etapa:geral:B1:7",
            "hipotese": "Pergunta curta segura mais gente.",
            "prioridade": "alta",
            "mudanca": "Encurtar a pergunta 1.",
            "key_sugerida": "B3",
            "intruso": "x",
        },
    )
    assert resposta.status_code == 302 and "recado=criada" in resposta["Location"]
    corpo = json.loads(criar.calls.last.request.content)
    assert corpo["key_sugerida"] == "B3" and "intruso" not in corpo
    assert dict(criar.calls.last.request.url.params) == {"site_id": "site-teste"}


@respx.mock
def test_erro_da_api_volta_na_tela_sem_perder_o_que_foi_digitado():
    cliente = _cliente()
    respx.post(BASE + "/propostas").mock(
        return_value=httpx.Response(422, json={"detail": "Já existe a versão B2."})
    )
    respx.get(BASE + "/evolucao").mock(return_value=httpx.Response(200, json=LEITURA))
    respx.get(BASE + "/propostas").mock(
        return_value=httpx.Response(200, json={"propostas": []})
    )
    url = reverse("quiz_evolucao", kwargs={"slug": "campanha"})
    resposta = cliente.post(
        url,
        {"acao": "criar", "versao_base": "B1", "hipotese": "h", "mudanca": "m", "key_sugerida": "B2"},
    )
    assert resposta.status_code == 422
    texto = resposta.content.decode()
    assert "Já existe a versão B2." in texto
    assert 'value="B2"' in texto


@respx.mock
def test_atualizar_proposta_usa_patch_na_proposta_certa():
    cliente = _cliente()
    atualizar = respx.patch(BASE + "/propostas/5").mock(
        return_value=httpx.Response(200, json=PROPOSTA)
    )
    url = reverse("quiz_evolucao", kwargs={"slug": "campanha"})
    resposta = cliente.post(
        url,
        {"acao": "atualizar", "proposta_id": "5", "estado": "aceita", "resultado_texto": ""},
    )
    assert resposta.status_code == 302 and "recado=atualizada" in resposta["Location"]
    assert json.loads(atualizar.calls.last.request.content) == {"estado": "aceita"}


@respx.mock
def test_leitura_indisponivel_mostra_erro_em_vez_de_quebrar():
    cliente = _cliente()
    respx.get(BASE + "/evolucao").mock(return_value=httpx.Response(500, json={}))
    url = reverse("quiz_evolucao", kwargs={"slug": "campanha"})
    assert cliente.get(url).status_code == 503


@respx.mock
def test_evolucao_requer_sessao_admin():
    resposta = Client().get(reverse("quiz_evolucao", kwargs={"slug": "campanha"}))
    assert resposta.status_code in (302, 404)
