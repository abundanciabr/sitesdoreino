import json
from itertools import product

import pytest

from apps.quiz.models import NPSTentativa, Site
from apps.quiz.nps_revisado import default_document, portrait_from_readings


BASE = "/interno/nps"
AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
OWNER = {"site_id": "escola", "aluno_id": "aluno-1"}


def post(client, path, data):
    return client.post(BASE + path, data=json.dumps(data), content_type="application/json", **AUTH)


@pytest.fixture
def site(db, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    return Site.objects.create(id="escola", host="escola.example", name="Escola")


@pytest.fixture
def revised(client, site):
    response = post(client, "/config", {"site_id": site.id, "documento": default_document()})
    assert response.status_code == 200, response.content
    return response.json()


def start(client):
    response = post(client, "/tentativas", {**OWNER, "aluno": {"email": "adulto@example.com"}, "matricula": {"id": "m-1"}})
    assert response.status_code == 201, response.content
    return response.json()


def answer(client, attempt, key, value, **extra):
    response = post(client, f"/tentativas/{attempt['id']}/respostas", {**OWNER, "pergunta_id": key, "valor": value, **extra})
    assert response.status_code == 200, response.content
    return response.json()


@pytest.mark.django_db
def test_adulto_pagante_sem_aula_conferencia_e_nota_separada(client, revised):
    attempt = start(client)
    assert attempt["roteiro"] == "revisado"
    assert attempt["proxima_pergunta"]["id"] == "A1"
    assert attempt["respostas"]["P1"] == "aluno_pagante"
    assert attempt["qualidade"]["identidade_respondente"]["fonte"] == "publico_adulto_confirmado_pelo_mantenedor"
    attempt = answer(client, attempt, "A1", "nenhuma")
    assert attempt["proxima_pergunta"]["id"] == "R2"
    attempt = answer(client, attempt, "R2", "satisfeito")
    options = {item["valor"] for item in attempt["proxima_pergunta"]["opcoes"]}
    assert "aula_chata" not in options and "esperando_ajuda" in options and "sem_vontade" in options
    attempt = answer(client, attempt, "A3", ["nenhuma"])
    assert attempt["proxima_pergunta"]["id"] == "A8"
    attempt = answer(client, attempt, "A8", "nao")
    assert attempt["proxima_pergunta"]["id"] == "R10"  # Sem aulas também pode não querer começar.
    attempt = answer(client, attempt, "R10", "preco")
    attempt = answer(client, attempt, "R11", ["nao_falou"])
    attempt = answer(client, attempt, "R12", "9")
    attempt = answer(client, attempt, "R13", "")
    assert attempt["proxima_pergunta"] is None
    assert attempt["conferencia"]["confirmacao_pendente"] is True
    assert all("P1" not in line for line in attempt["conferencia"]["resumo"])
    path = f"/tentativas/{attempt['id']}/respostas"
    assert post(client, path, {**OWNER, "acao": "concluir"}).status_code == 400
    done = post(client, path, {**OWNER, "acao": "concluir", "confirmado": True}).json()
    assert done["status"] == "concluida"
    assert done["resultado"]["nps"] == 9
    assert done["resultado"]["leituras"]["satisfacao"]["valor"] == "Satisfeito"
    assert done["resultado"]["classificacao"] == "Em risco"
    assert done["qualidade"]["audit_failed"] is False
    assert done["qualidade"]["tempos_perguntas"]
    assert post(client, path, {**OWNER, "acao": "corrigir", "pergunta_id": "A8"}).status_code == 409


@pytest.mark.django_db
def test_voltar_de_r2_reabre_a1_sem_apagar_identidade(client, revised):
    attempt = start(client)
    attempt = answer(client, attempt, "A1", "recente")
    assert attempt["proxima_pergunta"]["id"] == "R2"
    returned = post(client, f"/tentativas/{attempt['id']}/respostas", {**OWNER, "acao": "voltar"})
    assert returned.status_code == 200, returned.content
    data = returned.json()
    assert data["proxima_pergunta"]["id"] == "A1"
    assert data["respostas"]["P1"] == "aluno_pagante"
    assert "A1" not in data["respostas"]
    assert data["qualidade"].get("confirmacao_recusada") is not True


@pytest.mark.django_db
def test_multiplas_reclamacoes_resolucao_retrato_e_revisao(client, revised):
    attempt = start(client)
    attempt = answer(client, attempt, "A1", "recente")
    attempt = answer(client, attempt, "R2", "morno")
    path = f"/tentativas/{attempt['id']}/respostas"
    assert post(client, path, {**OWNER, "pergunta_id": "A3", "valor": ["nenhuma", "video_trava"]}).status_code == 400
    attempt = answer(client, attempt, "A3", ["video_trava", "outra"], complemento="O fórum não carrega")
    assert attempt["proxima_pergunta"]["id"] == "R4"
    attempt = answer(client, attempt, "R4", "video_trava")
    attempt = answer(client, attempt, "R5", "continua")
    assert attempt["proxima_pergunta"]["id"] == "R6"
    attempt = answer(client, attempt, "R6", "nao")
    attempt = answer(client, attempt, "R7", "satisfeito")
    attempt = answer(client, attempt, "A8", "sim")
    attempt = answer(client, attempt, "R11", ["recomendou_nao_sei"])
    attempt = answer(client, attempt, "R12", 6)
    attempt = answer(client, attempt, "R13", "Preciso de ajuda.")
    attempt = answer(client, attempt, "R14", "email")
    done = post(client, path, {**OWNER, "acao": "concluir", "confirmado": True}).json()
    assert done["resultado"]["classificacao"] == "Promotor em crise"
    assert done["resultado"]["provisorio"] is True
    assert done["resultado"]["nps"] == 6  # Nota não altera o retrato.
    review = post(client, "/revisao", {**OWNER, "tentativa_id": attempt["id"], "situacao_id": "outra", "tipo": "pessoal", "prova": {"fonte": "leitura da equipe", "referencia": "atendimento interno"}})
    assert review.status_code == 201, review.content
    assert review.json()["avaliacao"]["resultado"]["provisorio"] is True
    assert review.json()["avaliacao"]["resultado_atual"]["provisorio"] is False
    original = NPSTentativa.objects.get(pk=attempt["id"])
    assert original.resultado["provisorio"] is True


@pytest.mark.django_db
def test_nao_entendi_fato_e_esclarecimento_sem_mudar_snapshot(client, revised):
    attempt = start(client)
    path = f"/tentativas/{attempt['id']}/respostas"
    attempt = post(client, path, {**OWNER, "acao": "nao_entendi", "pergunta_id": "A1"}).json()
    assert attempt["proxima_pergunta"]["id"] == "R2"
    attempt = answer(client, attempt, "R2", "sem_opiniao")
    attempt = answer(client, attempt, "A3", ["nenhuma"])
    assert "quer fazer" in attempt["proxima_pergunta"]["texto"].lower()
    attempt = answer(client, attempt, "A8", "sim")
    attempt = answer(client, attempt, "R11", ["nao_falou"])
    attempt = answer(client, attempt, "R12", 4)
    attempt = answer(client, attempt, "R13", "")
    done = post(client, path, {**OWNER, "acao": "concluir", "confirmado": True}).json()
    assert done["resultado"]["suspenso"] is True
    assert done["resultado"]["classificacao"] == "A conferir"
    assert done["resultado"]["leituras"]["satisfacao"]["estado"] == "declarada"
    assert done["resultado"]["leituras"]["ponto_curso"]["estado"] == "sem_valor"
    invalid = post(client, "/revisao", {**OWNER, "tentativa_id": attempt["id"], "situacao_id": "satisfacao", "tipo": "fato", "prova": {"fonte": "x", "referencia": "y", "valor": "Satisfeito"}})
    assert invalid.status_code == 400
    fact = post(client, "/revisao", {**OWNER, "tentativa_id": attempt["id"], "situacao_id": "ponto_curso", "tipo": "fato", "prova": {"fonte": "plataforma", "referencia": "relatorio-1", "valor": "recente"}})
    assert fact.status_code == 201, fact.content
    assert fact.json()["avaliacao"]["resultado_atual"]["leituras"]["ponto_curso"]["estado"] == "em_conflito"
    clarification = post(client, "/revisao", {**OWNER, "tentativa_id": attempt["id"], "situacao_id": "A1", "tipo": "esclarecimento", "prova": {"fonte": "entrevista", "referencia": "atendimento-1", "valor": "recente"}})
    assert clarification.status_code == 201, clarification.content
    assert clarification.json()["avaliacao"]["respostas"]["A1"] == "__nao_entendi__"
    assert clarification.json()["avaliacao"]["resultado_atual"]["suspenso"] is False
    assert clarification.json()["avaliacao"]["resultado_atual"]["leituras"]["ponto_curso"]["estado"] == "confirmada"
    assert clarification.json()["avaliacao"]["resultado_atual"]["fatos_confirmados"] == ["ponto_curso"]


def test_nove_retratos_cobrem_512_combinacoes_com_precedencia():
    labels = set()
    spaces = (
        ("Satisfeito", "Morno", "Insatisfeito", "Sem opinião ainda"),
        ("Em aberto", "Resolvida", "Só opinião ou barreira pessoal", "Nenhuma"),
        ("Fica", "Em dúvida", "Sai", "Concluiu"),
        ("A favor", "Contra", "Dos dois jeitos", "Nenhum"),
        (False, True),
    )
    combinations = list(product(*spaces))
    assert len(combinations) == 512
    for values in combinations:
        portrait, reason = portrait_from_readings(*values)
        assert portrait and reason
        assert portrait == portrait_from_readings(*values)[0]
        labels.add(portrait)
    assert labels == {"Detrator", "Promotor em crise", "Insatisfeito de saída", "Em risco por problema", "Em risco", "Cedo para avaliar", "Promotor", "Promotor em potencial", "Neutro"}
    assert portrait_from_readings("Morno", "Em aberto", "Sai", "Contra", True)[0] == "Detrator"
    assert portrait_from_readings("Satisfeito", "Em aberto", "Sai", "A favor", False)[0] == "Promotor em crise"


@pytest.mark.django_db
def test_entrevista_abre_ramo_e_permita_completar_perguntas_pendentes(client, revised):
    attempt = start(client)
    attempt = answer(client, attempt, "A1", "recente")
    attempt = answer(client, attempt, "R2", "morno")
    path = f"/tentativas/{attempt['id']}/respostas"
    attempt = post(client, path, {**OWNER, "acao": "nao_entendi", "pergunta_id": "A3"}).json()
    attempt = answer(client, attempt, "A8", "sim")
    attempt = answer(client, attempt, "R11", ["nao_falou"])
    attempt = answer(client, attempt, "R12", 5)
    attempt = answer(client, attempt, "R13", "")
    post(client, path, {**OWNER, "acao": "concluir", "confirmado": True})

    def clarify(key, value):
        response = post(client, "/revisao", {**OWNER, "tentativa_id": attempt["id"], "situacao_id": key, "tipo": "esclarecimento", "prova": {"fonte": "entrevista", "referencia": "atendimento-2", "valor": value}})
        assert response.status_code == 201, response.content
        return response.json()["avaliacao"]

    evaluation = clarify("A3", ["video_trava", "site_sem_acesso"])
    assert [item["id"] for item in evaluation["perguntas_pendentes_revisao"]] == ["R4", "R5"]
    evaluation = clarify("R4", "video_trava")
    assert [item["id"] for item in evaluation["perguntas_pendentes_revisao"]] == ["R5"]
    evaluation = clarify("R5", "continua")
    assert [item["id"] for item in evaluation["perguntas_pendentes_revisao"]] == ["R6", "R7", "R14"]
    evaluation = clarify("R6", "nao")
    evaluation = clarify("R7", "insatisfeito")
    evaluation = clarify("R14", "email")
    assert evaluation["perguntas_pendentes_revisao"] == []
    assert evaluation["resultado_atual"]["suspenso"] is False
    assert evaluation["respostas"]["A3"] == "__nao_entendi__"
