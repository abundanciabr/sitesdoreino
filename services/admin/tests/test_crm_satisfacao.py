"""Satisfação no CRM: acesso, leitura honesta e escritas protegidas."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse


IDENTIDADE = "http://identidade:8000/interno"
QUIZ = "http://quiz:8000"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-identidade")
    monkeypatch.setenv("QUIZ_API_URL", QUIZ)
    monkeypatch.setenv("QUIZ_API_TOKEN", "token-quiz")
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"


def entrar(email="dono@exemplo.com", *, csrf=False):
    respx.get(IDENTIDADE + "/sessao/completa").mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "id-dono", "nome_exibido": "Dono", "papel": None, "email": email,
    }))
    cliente = Client(enforce_csrf_checks=csrf)
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=assinada"
    return cliente


@respx.mock
def test_consulta_mostra_nps_respostas_e_atendimento_sem_uuid_no_titulo():
    cliente = entrar()
    respx.get(QUIZ + "/interno/nps/config").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "versao": 2, "documento": {"perguntas": {}, "caminhos": {}},
    }))
    respx.get(QUIZ + "/interno/nps/historico").mock(return_value=httpx.Response(200, json={
        "site_id": "principal", "aluno_id": "aluno-1",
        "avaliacoes": [{
            "id": "avaliacao-uuid", "aluno_id": "aluno-1", "curso": {"nome": "Curso de desenho"},
            "resultado": {"nps": 9, "classificacao": "promotor", "motivos": ["Indicou três pessoas"],
                          "repercussao_pontos": 2, "participacao_externa": "não disponível"},
            "respostas_legiveis": [{"pergunta": "O que gostou?", "resposta": "Aulas práticas"}],
            "qualidade": {"estado": "conclusiva", "evidencias": {
                "observacao": "Registros somente deste site.",
                "registros_locais": {"aulas_concluidas": 3, "entregas": 1, "comentarios": 0, "ultima_entrega": None},
            }},
            "config_versao": 2, "calculo_versao": 1,
        }],
        "atendimentos": [{"id": "atendimento-uuid", "status": "aberto", "responsavel": "Ana",
                          "proximo_passo": "Ligar amanhã", "historico": []}],
    }))
    resposta = cliente.get(reverse("crm_satisfacao"), {"site_id": "principal", "email": "aluna@exemplo.com"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    for trecho in ("Curso de desenho", "NPS original:", "Indicou três pessoas", "O que gostou?", "Aulas práticas", "Ligar amanhã", "Aulas concluídas neste site", "Registros somente deste site."):
        assert trecho in texto
    assert "Avaliação avaliacao-uuid" not in texto
    assert "{'aulas_concluidas':" not in texto


@respx.mock
def test_servico_fora_do_ar_nao_vira_historico_vazio():
    cliente = entrar()
    respx.get(QUIZ + "/interno/nps/config").mock(side_effect=httpx.ConnectError("offline"))
    respx.get(QUIZ + "/interno/nps/historico").mock(side_effect=httpx.ConnectError("offline"))
    resposta = cliente.get(reverse("crm_satisfacao"), {"site_id": "principal", "email": "aluna@exemplo.com"})
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "não significa que não houve avaliações" in texto
    assert "Nenhuma avaliação registrada" not in texto


@respx.mock
def test_somente_admin_e_post_exige_csrf():
    cliente = entrar("estranho@exemplo.com")
    assert cliente.get(reverse("crm_satisfacao"), {"site_id": "principal"}).status_code == 404
    cliente = entrar(csrf=True)
    resposta = cliente.post(reverse("crm_satisfacao_config_salvar"), {"site_id": "principal", "documento": "{}"})
    assert resposta.status_code == 403


@respx.mock
def test_atendimento_envia_prazo_com_fuso():
    cliente = entrar()
    chamada = respx.post(QUIZ + "/interno/nps/atendimentos").mock(return_value=httpx.Response(201, json={
        "atendimento": {"id": "1"},
    }))
    resposta = cliente.post(reverse("crm_satisfacao_atendimento_salvar"), {
        "site_id": "principal", "aluno_id": "aluno-1", "responsavel": "Ana",
        "proximo_passo": "Ligar", "prazo": "2026-10-07T15:30", "status": "aberto",
    })
    assert resposta.status_code == 302
    assert chamada.called
    assert chamada.calls[0].request.read().decode().find('2026-10-07T15:30:00-03:00') >= 0
