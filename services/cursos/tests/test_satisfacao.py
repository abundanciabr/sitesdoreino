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
