import json
import uuid

import pytest
from django.utils.dateparse import parse_datetime

from apps.core.handlers import ao_quiz_completado
from apps.core.models import Oportunidade


pytestmark = pytest.mark.django_db


@pytest.fixture
def autorizado(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-acomp")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-acomp")
    return {"HTTP_AUTHORIZATION": "Bearer admin-acomp"}


@pytest.fixture
def oferta():
    ao_quiz_completado(str(uuid.uuid4()), {
        "site_id": "a", "quiz_slug": "crivo", "result_key": "iniciante",
        "lead": {"email": "maria@gmail.com", "name": "Maria"},
    })
    return Oportunidade.objects.get()


def patch(client, oferta, corpo, auth):
    return client.patch(f"/api/leads/crm/{oferta.pk}/acompanhamento", data=json.dumps(corpo),
                        content_type="application/json", **auth)


def test_agente_atualiza_acompanhamento_e_registra_nota(client, oferta, autorizado):
    resposta = patch(client, oferta, {
        "autor_id": "agente:atendimento",
        "atendido_por": {"tipo": "agente", "nome": "Assistente da equipe"},
        "ultimo_contato_em": "2026-10-03T09:30:00-03:00",
        "objecao_principal": "Pouco tempo",
        "proximo_passo": "Enviar o plano de estudo de 2 horas por semana",
        "prazo": "2026-10-05T12:00:00-03:00",
        "aguardando_resposta": True,
        "nota": {"descricao": "Disse que só tem as noites livres", "evidencia": "mensagem:m-7"},
    }, autorizado)
    assert resposta.status_code == 200, resposta.content
    item = resposta.json()
    assert item["atendido_por"] == {"tipo": "agente", "nome": "Assistente da equipe"}
    assert parse_datetime(item["ultimo_contato_em"]) == parse_datetime("2026-10-03T09:30:00-03:00")
    assert item["objecao_principal"] == "Pouco tempo"
    assert item["proximo_passo"]["descricao"] == "Enviar o plano de estudo de 2 horas por semana"
    assert parse_datetime(item["prazo"]) == parse_datetime("2026-10-05T12:00:00-03:00")
    assert item["aguardando_resposta"] is True
    assert item["etapa"] == "nova"  # etapa comercial não muda com o acompanhamento
    ultimos = item["historico"][-2:]
    assert ultimos[0]["tipo"] == "contato" and ultimos[0]["autor_id"] == "agente:atendimento"
    assert ultimos[1] == {**ultimos[1], "tipo": "nota",
                          "descricao": "Disse que só tem as noites livres",
                          "evidencia": "mensagem:m-7"}

    quadro = client.get("/api/leads/crm", {"aguardando_resposta": "sim"}, **autorizado).json()
    assert [i["id"] for i in quadro["itens"]] == [str(oferta.pk)]
    assert quadro["itens"][0]["objecao_principal"] == "Pouco tempo"
    assert client.get("/api/leads/crm", {"atendido_por": "pessoa"},
                      **autorizado).json()["itens"] == []
    assert client.get("/api/leads/crm", {"atendido_por": "agente"},
                      **autorizado).json()["total"] == 1


def test_pessoa_assume_e_campos_ausentes_ficam_como_estao(client, oferta, autorizado):
    patch(client, oferta, {"atendido_por": {"tipo": "agente", "nome": "Robô"},
                           "objecao_principal": "Preço", "aguardando_resposta": True}, autorizado)
    item = patch(client, oferta, {"atendido_por": {"tipo": "pessoa", "nome": "Ana"},
                                  "aguardando_resposta": False}, autorizado).json()
    assert item["atendido_por"] == {"tipo": "pessoa", "nome": "Ana"}
    assert item["objecao_principal"] == "Preço"
    assert item["aguardando_resposta"] is False
    item = patch(client, oferta, {"atendido_por": None, "ultimo_contato_em": None},
                 autorizado).json()
    assert item["atendido_por"] is None and item["ultimo_contato_em"] is None


def test_so_nota_registra_sem_mudar_campos(client, oferta, autorizado):
    antes = len(client.get(f"/api/leads/crm/{oferta.pk}", **autorizado).json()["historico"])
    item = patch(client, oferta, {"nota": "Ligar depois do almoço"}, autorizado).json()
    assert len(item["historico"]) == antes + 1
    assert item["historico"][-1]["descricao"] == "Ligar depois do almoço"


def test_proximo_passo_como_objeto_completo(client, oferta, autorizado):
    item = patch(client, oferta, {"proximo_passo": {
        "descricao": "Mandar link", "executar_ate": "2026-10-04T10:00:00-03:00",
        "evidencia_esperada": "Link enviado"}}, autorizado).json()
    assert item["proximo_passo"]["evidencia_esperada"] == "Link enviado"


@pytest.mark.parametrize("corpo", [
    {},
    {"etapa": "ganha"},
    {"atendido_por": {"tipo": "robo"}},
    {"atendido_por": "agente"},
    {"prazo": "2026-10-05T12:00:00"},
    {"aguardando_resposta": "sim"},
    {"proximo_passo": ""},
    {"nota": ""},
])
def test_acompanhamento_recusa_corpo_fora_do_formato(client, oferta, autorizado, corpo):
    assert patch(client, oferta, corpo, autorizado).status_code == 422


def test_oportunidade_encerrada_nao_recebe_proximo_passo_mas_recebe_nota(client, oferta, autorizado):
    client.post(f"/api/leads/crm/{oferta.pk}/close", data=json.dumps({
        "resultado": "perdida", "motivo": "Sem interesse", "evidencia": "mensagem:m-1"}),
        content_type="application/json", **autorizado)
    assert patch(client, oferta, {"proximo_passo": "Insistir"}, autorizado).status_code == 409
    assert patch(client, oferta, {"nota": "Pediu para não insistir"}, autorizado).status_code == 200


def test_acompanhamento_so_pelo_painel(client, oferta, settings):
    settings.TOKENS_ACEITOS.add("checkout")
    assert patch(client, oferta, {"nota": "x"},
                 {"HTTP_AUTHORIZATION": "Bearer checkout"}).status_code == 403
