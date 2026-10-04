import json
import uuid

import pytest
from django.utils.dateparse import parse_datetime

from apps.core.handlers import ao_quiz_completado
from apps.core.models import Lead, PerfilDoLead, TimelineEvent


pytestmark = pytest.mark.django_db


@pytest.fixture
def autorizado(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-perfil")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-perfil")
    return {"HTTP_AUTHORIZATION": "Bearer admin-perfil"}


@pytest.fixture
def lead():
    ao_quiz_completado(str(uuid.uuid4()), {
        "site_id": "a", "quiz_slug": "crivo", "result_key": "iniciante",
        "lead": {"email": "maria@gmail.com", "name": "Maria"},
    })
    return Lead.objects.get()


PERFIL = {
    "resumo": "Quer trabalhar com o tema e tem pouco tempo por semana.",
    "objetivo_declarado": {
        "texto": "Trabalhar com isso",
        "evidencias": [{"tipo": "resposta", "id": "q2", "trecho": "Trabalhar com isso"}],
    },
    "experiencia": {"texto": "Iniciante", "evidencias": [
        {"tipo": "resposta", "id": "resultado", "trecho": "iniciante"}]},
    "disponibilidade": {"texto": "Menos de 2 horas por semana", "evidencias": [
        {"tipo": "resposta", "id": "q1", "trecho": "Menos de 2 horas"}]},
    "duvidas": [{"texto": "Se dá para estudar no celular"}],
    "objecoes": [{"texto": "Tempo", "evidencias": [
        {"tipo": "mensagem", "id": "m-1", "trecho": "não tenho tempo"}]}],
    "informacoes_ausentes": ["orçamento disponível"],
    "hipoteses": [{"texto": "Pode preferir aulas curtas", "evidencias": [
        {"tipo": "resposta", "id": "q1", "trecho": "Menos de 2 horas"}]}],
    "perguntas_uteis": ["Qual horário fica melhor para estudar?"],
    "prioridade": {"nivel": "alta", "explicacao": "Declarou objetivo profissional."},
    "oferta_indicada": {"oferta_ref": "curso-crivo", "nome": "Curso Crivo",
                        "motivo": "Indicada pelo resultado do quiz"},
    "analisado_em": "2026-10-03T10:00:00-03:00",
    "analisado_por": "agente:analista",
    "versao_estrategia": "analista-v1",
}


def put(client, lead, corpo, auth):
    return client.put(f"/api/leads/leads/{lead.pk}/perfil", data=json.dumps(corpo),
                      content_type="application/json", **auth)


def test_perfil_ainda_nao_analisado_e_404(client, lead, autorizado):
    assert client.get(f"/api/leads/leads/{lead.pk}/perfil", **autorizado).status_code == 404


def test_analista_grava_perfil_com_evidencias_e_hipoteses(client, lead, autorizado):
    resposta = put(client, lead, PERFIL, autorizado)
    assert resposta.status_code == 200, resposta.content
    perfil = resposta.json()
    assert perfil["versao"] == 1
    assert perfil["objetivo_declarado"]["hipotese"] is False
    assert perfil["objetivo_declarado"]["evidencias"][0] == {
        "tipo": "resposta", "id": "q2", "trecho": "Trabalhar com isso"}
    # Sem evidência a afirmação fica marcada como hipótese.
    assert perfil["duvidas"][0]["hipotese"] is True
    assert perfil["objecoes"][0]["hipotese"] is False
    # Hipótese é sempre hipótese, mesmo com evidência.
    assert perfil["hipoteses"][0]["hipotese"] is True
    assert perfil["prioridade"] == {"nivel": "alta", "explicacao": "Declarou objetivo profissional."}
    assert perfil["oferta_indicada"]["oferta_ref"] == "curso-crivo"
    assert perfil["analisado_por"] == "agente:analista"
    assert perfil["versao_estrategia"] == "analista-v1"
    assert parse_datetime(perfil["analisado_em"]) == parse_datetime(PERFIL["analisado_em"])

    lido = client.get(f"/api/leads/leads/{lead.pk}/perfil", **autorizado).json()
    assert lido["resumo"] == PERFIL["resumo"]
    assert lido["versoes"] == 1
    assert lido["informacoes_ausentes"] == ["orçamento disponível"]
    assert lido["perguntas_uteis"] == ["Qual horário fica melhor para estudar?"]

    ficha = client.get(f"/api/leads/leads/{lead.pk}", **autorizado).json()
    assert ficha["perfil"]["versao"] == 1


def test_cada_analise_vira_versao_e_historico_fica(client, lead, autorizado):
    put(client, lead, PERFIL, autorizado)
    segunda = put(client, lead, {**PERFIL, "resumo": "Agora quer começar já.",
                                 "versao_base": 1}, autorizado)
    assert segunda.status_code == 200 and segunda.json()["versao"] == 2
    conflito = put(client, lead, {**PERFIL, "versao_base": 1}, autorizado)
    assert conflito.status_code == 409
    versoes = client.get(f"/api/leads/leads/{lead.pk}/perfil/versoes", **autorizado).json()
    assert [v["versao"] for v in versoes["versoes"]] == [2, 1]
    assert versoes["versoes"][1]["resumo"] == PERFIL["resumo"]
    assert client.get(f"/api/leads/leads/{lead.pk}/perfil",
                      **autorizado).json()["resumo"] == "Agora quer começar já."
    with pytest.raises(ValueError):
        antiga = PerfilDoLead.objects.get(versao=1)
        antiga.resumo = "mudado"
        antiga.save()


def test_perfil_avisa_fatos_novos_depois_da_analise(client, lead, autorizado):
    put(client, lead, {**PERFIL, "analisado_em": None}, autorizado)
    assert client.get(f"/api/leads/leads/{lead.pk}/perfil",
                      **autorizado).json()["fatos_novos_desde_a_analise"] == 0
    TimelineEvent.objects.create(lead=lead, event="pedido.criado", payload={})
    assert client.get(f"/api/leads/leads/{lead.pk}/perfil",
                      **autorizado).json()["fatos_novos_desde_a_analise"] == 1


def test_perfil_minimo_e_texto_simples(client, lead, autorizado):
    resposta = put(client, lead, {"resumo": "Pouca informação.",
                                  "objetivo_declarado": "Aprender", "prioridade": "baixa",
                                  "oferta_indicada": "curso-crivo"}, autorizado)
    assert resposta.status_code == 200
    perfil = resposta.json()
    assert perfil["objetivo_declarado"] == {"texto": "Aprender", "evidencias": [], "hipotese": True}
    assert perfil["experiencia"] is None and perfil["duvidas"] == []
    assert perfil["prioridade"]["nivel"] == "baixa"
    assert perfil["oferta_indicada"]["oferta_ref"] == "curso-crivo"


@pytest.mark.parametrize("corpo", [
    {"renda": "alta"},
    {"prioridade": {"nivel": "urgente"}},
    {"objecoes": "tempo"},
    {"objetivo_declarado": {"texto": "x", "evidencias": [{"tipo": "resposta"}]}},
    {"analisado_em": "ontem"},
    {"versao_base": "1"},
])
def test_perfil_recusa_corpo_fora_do_formato(client, lead, autorizado, corpo):
    assert put(client, lead, corpo, autorizado).status_code == 422


def test_perfil_so_pelo_painel_e_por_lead(client, lead, autorizado, settings):
    settings.TOKENS_ACEITOS.add("checkout")
    assert put(client, lead, PERFIL, {"HTTP_AUTHORIZATION": "Bearer checkout"}).status_code == 403
    assert client.get(f"/api/leads/leads/{lead.pk}/perfil",
                      HTTP_AUTHORIZATION="Bearer checkout").status_code == 403
    outro = Lead.objects.create(site_id="b", email="maria@gmail.com", source="quiz:crivo")
    put(client, lead, PERFIL, autorizado)
    assert client.get(f"/api/leads/leads/{outro.pk}/perfil", **autorizado).status_code == 404
    assert client.put(f"/api/leads/leads/{uuid.uuid4()}/perfil", data="{}",
                      content_type="application/json", **autorizado).status_code == 404
