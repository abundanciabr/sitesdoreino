import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.quiz.models import NPSTentativa, Site
from apps.quiz.nps import _classify, _default, _valid_document


AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
BASE = "/interno/nps"


def post(client, path, body, **headers):
    return client.post(BASE + path, data=json.dumps(body), content_type="application/json", **headers)


@pytest.fixture
def site(db):
    return Site.objects.create(id="escola", host="escola.example", name="Escola")


@pytest.mark.django_db
def test_acesso_config_versao_e_identidade(client, site, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    assert client.get(BASE + "/config?site_id=escola").status_code == 401
    assert post(client, "/tentativas", {"site_id": site.id, "aluno_id": "p1"}).status_code == 401
    original = client.get(BASE + "/config?site_id=escola", **AUTH).json()
    original["documento"]["perguntas"]["nota"]["texto"] = "Nova pergunta?"
    updated = post(client, "/config", {"site_id": site.id, "documento": original["documento"]}, **AUTH).json()
    assert updated["versao"] == 2
    created = post(client, "/tentativas", {"site_id": site.id, "aluno_id": "p1", "aluno": {"email": "A@EXAMPLE.COM"}}, **AUTH).json()
    assert created["config_versao"] == 2
    assert created["proxima_pergunta"]["texto"] == "Nova pergunta?"
    attempt_id = created["id"]
    assert client.get(BASE + f"/tentativas/{attempt_id}?site_id=escola&aluno_id=outro", **AUTH).status_code == 404
    assert post(client, f"/tentativas/{attempt_id}/respostas", {"site_id": site.id, "aluno_id": "outro", "pergunta_id": "nota", "valor": 9}, **AUTH).status_code == 404


@pytest.mark.django_db
def test_ramo_editado_tempo_historico_e_imutabilidade(client, site, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    created = post(client, "/tentativas", {"site_id": site.id, "aluno_id": "p1", "aluno": {"email": "A@EXAMPLE.COM"}, "matricula": {"id": "m1"}}, **AUTH).json()
    path = f"/tentativas/{created['id']}/respostas"
    owner = {"site_id": site.id, "aluno_id": "p1"}

    def answer(key, value):
        response = post(client, path, {**owner, "pergunta_id": key, "valor": value}, **AUTH)
        assert response.status_code == 200, response.content
        return response.json()

    assert answer("nota", 5)["proxima_pergunta"]["id"] == "escopo"
    answer("escopo", "recorrente")
    edited = answer("nota", 9)
    assert "escopo" not in edited["respostas"]
    assert edited["proxima_pergunta"]["id"] == "repercussao"
    assert answer("repercussao", "mais_3")["proxima_pergunta"]["id"] == "nome_indicado"
    answer("nome_indicado", "")
    answer("indicacao", "nao")
    answer("orcamento", "ultimo")
    assert answer("comentario", "Gostei, mas tive uma dificuldade.")["proxima_pergunta"] is None
    completed = post(client, path, {**owner, "acao": "concluir"}, **AUTH).json()
    assert completed["resultado"]["classificacao"] == "Promotor confirmado"
    assert completed["resultado"]["repercussao_pontos"] == 2
    assert completed["resultado"]["indicacao_declarada"] is False
    assert completed["qualidade"]["audit_failed"] is True
    assert completed["qualidade"]["perguntas_exibidas_unicas"] == 8
    assert any(event["acao"] == "ramo_abandonado" and event["pergunta_id"] == "escopo" for event in completed["qualidade"]["eventos"])
    assert any(item["pergunta_id"] == "escopo" for item in completed["respostas_registro"])
    assert any(item["pergunta_id"] == "comentario" and item["resposta"] == "Gostei, mas tive uma dificuldade." for item in completed["respostas_legiveis"])
    assert post(client, path, {**owner, "pergunta_id": "nota", "valor": 0}, **AUTH).status_code == 409
    history = client.get(BASE + "/historico?site_id=escola&email=a@example.com", **AUTH).json()
    assert history["avaliacoes"][0]["aluno_id"] == "p1"
    assert history["avaliacoes"][0]["respostas"]["comentario"] == "Gostei, mas tive uma dificuldade."
    case = post(client, "/atendimentos", {**owner, "tentativa_id": created["id"], "responsavel": "Equipe", "proximo_passo": "Ligar", "status": "aberto"}, **AUTH)
    assert case.status_code == 201
    assert case.json()["atendimento"]["proximo_passo"] == "Ligar"
    edited_case = post(client, "/atendimentos", {**owner, "id": case.json()["atendimento"]["id"], "responsavel": "Equipe", "proximo_passo": "Resolver", "status": "em_andamento"}, **AUTH).json()["atendimento"]
    assert [item["proximo_passo"] for item in edited_case["historico"]] == ["Ligar", "Resolver"]
    assert len(client.get(BASE + "/historico?site_id=escola&aluno_id=p1", **AUTH).json()["atendimentos"]) == 1


@pytest.mark.django_db
def test_tempo_suficiente_e_nova_tentativa(client, site, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    owner = {"site_id": site.id, "aluno_id": "p1"}
    first = post(client, "/tentativas", owner, **AUTH).json()
    path = f"/tentativas/{first['id']}/respostas"
    for key, value in [("nota", 7), ("gargalo", "tempo"), ("concorrente", "pesquisar"), ("comentario", "")]:
        assert post(client, path, {**owner, "pergunta_id": key, "valor": value}, **AUTH).status_code == 200
    NPSTentativa.objects.filter(pk=first["id"]).update(criada_em=timezone.now() - timedelta(minutes=2))
    result = post(client, path, {**owner, "acao": "concluir"}, **AUTH).json()
    assert result["qualidade"]["audit_failed"] is False
    assert result["resultado"]["classificacao"] == "Neutro"
    second = post(client, "/tentativas", owner, **AUTH)
    assert second.status_code == 201 and second.json()["id"] != first["id"]


@pytest.mark.parametrize("answers,expected", [
    ({"nota": 5, "escopo": "recorrente", "continuar": "indiferente", "vinculo_anterior": "nao"}, "Detrator real"),
    ({"nota": 5, "escopo": "isolado", "continuar": "sim", "vinculo_anterior": "sim"}, "Promotor em Crise"),
    ({"nota": 5, "escopo": "isolado", "continuar": "sim", "vinculo_anterior": "nao"}, "Neutro sob Risco"),
    ({"nota": 7, "concorrente": "migrar"}, "Alto risco de saída"),
    ({"nota": 7, "concorrente": "permanecer"}, "Promotor potencial"),
    ({"nota": 7, "gargalo": "pedagogico", "concorrente": "permanecer"}, "Classificação ainda não confirmada"),
    ({"nota": 10, "repercussao": "nenhuma", "orcamento": "pausar"}, "Neutro"),
])
def test_regras_explicitas(answers, expected):
    assert _classify(answers)["classificacao"] == expected


def test_tres_pessoas_sem_peso_e_config_anterior_valida():
    document = _default()
    assert {option["valor"] for option in document["perguntas"]["repercussao"]["opcoes"]} == {"mais_3", "3", "1_2", "nenhuma"}
    assert _valid_document(document)
    old_document = _default()
    old_document["perguntas"]["repercussao"]["opcoes"] = [option for option in old_document["perguntas"]["repercussao"]["opcoes"] if option["valor"] != "3"]
    assert _valid_document(old_document)
    result = _classify({"nota": 10, "repercussao": "3", "orcamento": "ultimo", "indicacao": "sim"})
    assert result["repercussao_pontos"] is None
    assert result["evangelismo"] is None
    assert result["classificacao"] == "Classificação ainda não confirmada"
    assert "peso definido" in result["motivos"][0]
