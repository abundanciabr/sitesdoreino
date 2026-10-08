import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.quiz.models import NPSParticipacao, NPSTentativa, Site
from apps.quiz.participacao import aplicar

AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
BASE = "/interno/nps"


@pytest.fixture
def escola(settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    return Site.objects.create(id="escola", host="escola.test", name="Escola")


def post(client, path, data, **headers):
    return client.post(BASE + path, json.dumps(data), content_type="application/json", **headers)


def concluir(client, nota):
    dono = {"site_id": "escola", "aluno_id": "aluno"}
    criada = post(client, "/tentativas", dono, **AUTH).json()
    path = "/tentativas/" + criada["id"] + "/respostas"
    respostas = [("nota", nota)]
    if nota >= 9:
        respostas += [("repercussao", "3"), ("indicacao", "sim"), ("orcamento", "ultimo")]
    elif nota >= 7:
        respostas += [("gargalo", "tempo"), ("concorrente", "pesquisar")]
    else:
        respostas += [("escopo", "isolado"), ("continuar", "sim"), ("vinculo_anterior", "sim")]
    respostas += [("comentario", "")]
    for chave, valor in respostas:
        resposta = post(client, path, {**dono, "pergunta_id": chave, "valor": valor}, **AUTH)
        assert resposta.status_code == 200, resposta.content
    resposta = post(client, path, {**dono, "acao": "concluir"}, **AUTH)
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


@pytest.mark.django_db
def test_conclusao_aplica_rebaixamento_e_recuperacao_sem_apagar_conquistas(client, escola):
    positiva = concluir(client, 10)
    estado = NPSParticipacao.objects.get(aluno_id="aluno")
    assert estado.segmento == "promotor" and estado.embaixador_desde
    detratora = concluir(client, 5)
    # Mesmo que o questionário descreva um promotor em crise, a nota manda.
    assert detratora["resultado"]["classificacao"] == "Promotor em Crise"
    estado.refresh_from_db()
    corte = estado.conquistas_privadas_ate
    assert estado.segmento == "detrator" and corte and estado.embaixador_desde
    concluir(client, 8)
    estado.refresh_from_db()
    assert estado.segmento == "neutro" and estado.conquistas_privadas_ate == corte
    concluir(client, 9)
    estado.refresh_from_db()
    assert estado.segmento == "promotor" and estado.conquistas_privadas_ate == corte
    assert NPSTentativa.objects.get(pk=positiva["id"]).resultado["nps"] == 10


@pytest.mark.django_db
def test_incompleta_e_acoes_administrativas_nao_liberam_restricao(client, escola):
    anterior = concluir(client, 3)
    dono = {"site_id": "escola", "aluno_id": "aluno"}
    criada = post(client, "/tentativas", dono, **AUTH).json()
    path = "/tentativas/" + criada["id"] + "/respostas"
    assert post(client, path, {**dono, "pergunta_id": "nota", "valor": 10}, **AUTH).status_code == 200
    assert post(client, path, {**dono, "acao": "concluir"}, **AUTH).status_code == 400
    assert NPSParticipacao.objects.get(aluno_id="aluno").segmento == "detrator"
    acao = {**dono, "tentativa_id": anterior["id"], "acao": "arquivar"}
    assert post(client, "/acoes", acao, **AUTH).status_code == 200
    assert post(client, "/acoes", {**acao, "acao": "excluir", "confirmacao": "excluir"}, **AUTH).status_code == 200
    assert NPSParticipacao.objects.get(aluno_id="aluno").segmento == "detrator"


@pytest.mark.django_db
def test_consulta_privada_sem_acesso_para_alterar_estado(client, escola, monkeypatch):
    concluir(client, 10)
    monkeypatch.setenv("TOKEN_PARTICIPACAO_NPS", "par-teste")
    pedido = {"site_id": "escola", "ids": ["aluno", "novo"]}
    assert post(client, "/participacao", pedido).status_code == 401
    resposta = post(client, "/participacao", pedido, HTTP_AUTHORIZATION="Bearer par-teste")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta.json()["aluno"]["segmento"] == "promotor"
    assert resposta.json()["novo"]["segmento"] == "sem_avaliacao"
    pedido["site_id"] = "outra"
    assert post(client, "/participacao", pedido, HTTP_AUTHORIZATION="Bearer par-teste").json()["aluno"]["segmento"] == "sem_avaliacao"


@pytest.mark.django_db
def test_avaliacao_antiga_ou_do_responsavel_nao_substitui_a_do_aluno(client, escola):
    concluir(client, 3)
    estado = NPSParticipacao.objects.get(aluno_id="aluno")
    antiga = NPSTentativa.objects.create(site_id="escola", aluno_id="aluno", config_versao=1, config_documento={}, status="concluida", concluida_em=timezone.now() - timedelta(days=1), resultado={"nps": 10})
    aplicar(antiga)
    responsavel = NPSTentativa.objects.create(site_id="escola", aluno_id="aluno", config_versao=1, config_documento={}, status="concluida", concluida_em=timezone.now(), resultado={"nps": 10, "pessoa_respondente": "responsavel"})
    aplicar(responsavel)
    estado.refresh_from_db()
    assert estado.segmento == "detrator" and not estado.embaixador_desde


@pytest.mark.django_db
def test_falha_na_participacao_desfaz_conclusao(client, escola, monkeypatch):
    from apps.quiz import nps
    def falhar(avaliacao):
        raise RuntimeError("falha simulada")
    monkeypatch.setattr(nps, "aplicar_participacao", falhar)
    with pytest.raises(RuntimeError):
        concluir(client, 10)
    assert not NPSTentativa.objects.filter(status="concluida").exists()
    assert not NPSParticipacao.objects.exists()
