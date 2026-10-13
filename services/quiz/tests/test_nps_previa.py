import json

import pytest

from apps.quiz.models import NPSConfig, NPSTentativa, NPSAtendimento, Site
from apps.quiz.nps_revisado import default_document

pytestmark = pytest.mark.django_db
AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
OWNER = {"site_id": "escola", "admin_id": "admin-1", "curso": {"slug": "profissional"}}


@pytest.fixture
def config(settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    site = Site.objects.create(id="escola", host="escola.example", name="Escola")
    document = default_document()
    document["settings"]["nota_primeiro"] = False
    return NPSConfig.objects.create(site_id=site.id, versao=1, documento=document)


def post(client, state=None, **action):
    response = client.post("/interno/nps/simular", data=json.dumps({**OWNER,
        "estado_previa": (state or {}).get("estado_previa", ""), **action}), content_type="application/json", **AUTH)
    return response


def answer(client, state, key, value):
    assert state["proxima_pergunta"]["id"] == key
    response = post(client, state, acao="responder", pergunta_id=key, valor=value)
    assert response.status_code == 200, response.content
    return response.json()


@pytest.mark.parametrize("situacoes", [["nenhuma"], ["site_sem_acesso", "sem_resposta"]])
def test_percorre_ramos_reais_sem_gravar_alunos(client, config, situacoes):
    state = post(client, acao="iniciar").json()
    state = answer(client, state, "A1", "recente")
    state = answer(client, state, "R2", "satisfeito")
    assert any(o["valor"] == "site_sem_acesso" for o in state["proxima_pergunta"]["opcoes"])
    state = answer(client, state, "A3", situacoes)
    if len(situacoes) > 1:
        assert {o["valor"] for o in state["proxima_pergunta"]["opcoes"]} == set(situacoes)
        state = answer(client, state, "R4", "site_sem_acesso")
        assert "Não consegui entrar no site" in state["proxima_pergunta"]["texto"]
        state = answer(client, state, "R5", "continua")
        state = answer(client, state, "R6", "esperando")
    state = answer(client, state, "A8", "sim")
    state = answer(client, state, "R11", ["nao_falou"])
    state = answer(client, state, "R12", 8)
    state = answer(client, state, "R13", "")
    if len(situacoes) > 1:
        state = answer(client, state, "R14", "nao_precisa")
    assert state["conferencia"]["confirmacao_pendente"]
    refused = post(client, state, acao="concluir", confirmado=False)
    assert refused.status_code == 400
    response = post(client, refused.json(), acao="concluir", confirmado=True)
    assert response.status_code == 200 and response.json()["status"] == "concluida"
    assert NPSTentativa.objects.count() == 0 and NPSAtendimento.objects.count() == 0
    assert NPSConfig.objects.count() == 1


def test_voltar_nao_entendi_e_correcao(client, config):
    state = post(client, acao="iniciar").json()
    state = answer(client, state, "A1", "nenhuma")
    state = post(client, state, acao="nao_entendi", pergunta_id="R2").json()
    assert state["proxima_pergunta"]["id"] == "A3"
    assert not any(o["valor"] == "aula_chata" for o in state["proxima_pergunta"]["opcoes"])
    response = post(client, state, acao="voltar")
    assert response.status_code == 200 and response.json()["proxima_pergunta"]["id"] == "R2"
    assert NPSTentativa.objects.count() == 0


def test_estado_assinado_e_isolado_por_admin_curso_e_site(client, config):
    state = post(client, acao="iniciar").json()
    for extra in ({"admin_id": "outro"}, {"curso": {"slug": "outro"}}, {"estado_previa": "adulterado"}):
        response = post(client, state, acao="responder", pergunta_id="A1", valor="nenhuma", **extra)
        assert response.status_code in (400, 403)
    assert NPSTentativa.objects.count() == 0


def test_exige_token(client, config):
    response = client.post("/interno/nps/simular", data=json.dumps({**OWNER, "acao": "iniciar"}), content_type="application/json")
    assert response.status_code == 401


def test_nao_entendi_nota_tem_resumo_legivel_sem_alterar_resposta(client, config):
    state = post(client, acao="iniciar").json()
    state = answer(client, state, "A1", "nenhuma")
    state = answer(client, state, "R2", "sem_opiniao")
    state = answer(client, state, "A3", ["nenhuma"])
    state = answer(client, state, "A8", "sim")
    state = answer(client, state, "R11", ["nao_falou"])
    state = post(client, state, acao="nao_entendi", pergunta_id="R12").json()
    state = answer(client, state, "R13", "")
    nota = next(item for item in state["respostas_legiveis"] if item["pergunta_id"] == "R12")
    assert nota["resposta"] == "Não entendi a pergunta"
    assert any("Não entendi a pergunta" in frase for frase in state["conferencia"]["resumo"])
    assert all("__nao_entendi__" not in frase for frase in state["conferencia"]["resumo"])
    assert state["respostas"]["R12"] == "__nao_entendi__"
    response = post(client, state, acao="concluir", confirmado=True)
    assert response.status_code == 200 and response.json()["status"] == "concluida"
    assert response.json()["resultado"]["nps"] is None
    assert NPSTentativa.objects.count() == 0 and NPSAtendimento.objects.count() == 0
