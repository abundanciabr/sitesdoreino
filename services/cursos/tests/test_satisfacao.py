import json
import httpx
import pytest
from django.urls import reverse
from apps.cursos.models import Progresso
from tests.conftest import COOKIE, ANA, dublar_sessao, dublar_matricula

pytestmark = pytest.mark.django_db


def test_visitante_nao_inicia_tentativa(client):
    resposta = client.post(reverse("satisfacao"), {"acao": "iniciar"})
    assert resposta.status_code == 200
    assert "Entrar com meu cadastro" in resposta.content.decode()


def test_lead_sem_matricula_nao_responde(client, env_dos_pares, rede, esqueleto):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = client.post(reverse("satisfacao-curso", args=["profissional"]), {"acao": "iniciar"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403


def test_aluno_externo_sem_aulas_inicia_com_identidade_do_servidor(client, aluna, rede, monkeypatch):
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "par-nps")
    rota = rede.post("http://quiz:8000/interno/nps/tentativas").mock(return_value=httpx.Response(201, json={"id": "bc7d35fc-c822-409c-a308-a2a9458e60f0"}))
    resposta = client.post(reverse("satisfacao-curso", args=["profissional"]), {"acao": "iniciar", "aluno_id": "outra-pessoa"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 302
    corpo = json.loads(rota.calls[0].request.content)
    assert corpo["aluno_id"] == ANA["id"]
    assert corpo["aluno"]["email"] == ANA["email"]
    assert corpo["matricula"]["status"] == "ativa"
    assert corpo["evidencias"]["participacao"] == "participação não disponível"
    assert Progresso.objects.count() == 0


def test_tentativa_de_outro_curso_nao_aceita_post(client, aluna, rede, monkeypatch):
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "par-nps")
    rede.get("http://quiz:8000/interno/nps/tentativas/bc7d35fc-c822-409c-a308-a2a9458e60f0").mock(return_value=httpx.Response(200, json={"curso": {"slug": "outro"}}))
    resposta = client.post(reverse("satisfacao-curso", args=["profissional"]), {"tentativa_id": "bc7d35fc-c822-409c-a308-a2a9458e60f0", "acao": "concluir"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 404


def test_curso_nao_matriculado_fechado(client, aluna):
    assert client.get(reverse("satisfacao-curso", args=["outro"]), HTTP_COOKIE=COOKIE).status_code == 404


def montar_revisada(rede, monkeypatch, pergunta=None, conferencia=None):
    monkeypatch.setenv("QUIZ_API_URL", "http://quiz:8000")
    monkeypatch.setenv("QUIZ_API_TOKEN", "par-nps")
    tid = "bc7d35fc-c822-409c-a308-a2a9458e60f0"
    dados = {"id": tid, "status": "em_andamento", "curso": {"slug": "profissional"},
        "config_documento": {"roteiro": "revisado"}, "respostas": {},
        "proxima_pergunta": pergunta, "conferencia": conferencia, "respostas_legiveis": []}
    rede.get(f"http://quiz:8000/interno/nps/tentativas/{tid}").mock(return_value=httpx.Response(200, json=dados))
    post = rede.post(f"http://quiz:8000/interno/nps/tentativas/{tid}/respostas").mock(return_value=httpx.Response(200, json=dados))
    return tid, post


def test_lista_envia_todas_as_situacoes_e_complemento(client, aluna, rede, monkeypatch):
    tid, post = montar_revisada(rede, monkeypatch, {"id": "A3", "tipo": "multipla"})
    response = client.post(reverse("satisfacao-curso", args=["profissional"]),
        {"tentativa_id": tid, "acao": "responder", "pergunta_id": "A3", "valor": ["video", "outra"], "complemento": "Problema de acesso"}, HTTP_COOKIE=COOKIE)
    assert response.status_code == 302
    body = json.loads(post.calls[0].request.content)
    assert body["valor"] == ["video", "outra"] and body["complemento"] == "Problema de acesso"


def test_nao_entendi_nao_exige_resposta_de_chute(client, aluna, rede, monkeypatch):
    tid, post = montar_revisada(rede, monkeypatch, {"id": "A1", "tipo": "escolha"})
    response = client.post(reverse("satisfacao-curso", args=["profissional"]),
        {"tentativa_id": tid, "acao": "nao_entendi", "pergunta_id": "A1"}, HTTP_COOKIE=COOKIE)
    assert response.status_code == 302
    body = json.loads(post.calls[0].request.content)
    assert body["acao"] == "nao_entendi" and "valor" not in body


def test_conferencia_tem_confirmacao_explicita_e_correcao(client, aluna, rede, monkeypatch):
    tid, post = montar_revisada(rede, monkeypatch, conferencia={"resumo": ["Você está satisfeito com o curso."], "confirmacao_pendente": True})
    response = client.get(reverse("satisfacao-curso", args=["profissional"]) + "?tentativa=" + tid, HTTP_COOKIE=COOKIE)
    texto = response.content.decode()
    assert "Você está satisfeito com o curso." in texto
    assert "Sim, é isso" in texto and "Não, quero corrigir" in texto
    response = client.post(reverse("satisfacao-curso", args=["profissional"]),
        {"tentativa_id": tid, "acao": "concluir", "confirmado": "sim"}, HTTP_COOKIE=COOKIE)
    assert json.loads(post.calls[0].request.content)["confirmado"] is True
