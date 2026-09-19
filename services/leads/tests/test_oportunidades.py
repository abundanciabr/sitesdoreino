# tests/test_oportunidades.py
"""O acompanhamento comercial humano, regra por regra do contrato congelado.

Cada teste aqui guarda uma frase do aceite: autorização por titular e por site,
histórico imutável, transferência que só troca o titular no aceite, recusa que
preserva o motivo, encerramento com evidência, reabertura e efeito que não
acontece duas vezes.
"""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import (
    Lead,
    Oportunidade,
    RegistroHistoricoOportunidade,
    TransferenciaResponsabilidade,
)

pytestmark = pytest.mark.django_db

ANA = "tok-da-ana"
BRUNO = "tok-do-bruno"
CARLA = "tok-da-carla"
MAQUINA = "tok-de-maquina"

DAQUI_A_POUCO = "2026-12-01T15:00:00-03:00"
JA_VENCEU = "2020-01-10T09:00:00-03:00"


@pytest.fixture
def comerciais(settings):
    contas = {
        ANA: {"titular_id": "com-ana", "site_id": "site-a"},
        BRUNO: {"titular_id": "com-bruno", "site_id": "site-a"},
        CARLA: {"titular_id": "com-carla", "site_id": "site-b"},
    }
    settings.COMERCIAIS_DO_CRM = contas
    settings.TOKENS_ACEITOS = set(contas) | {MAQUINA}
    return contas


@pytest.fixture
def lead_do_site_a():
    return Lead.objects.create(site_id="site-a", email="ana.cliente@example.com")


@pytest.fixture
def lead_do_site_b():
    return Lead.objects.create(site_id="site-b", email="beto.cliente@example.com")


def _chamar(client, metodo, caminho, token, corpo=None):
    argumentos = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    if corpo is not None:
        argumentos["data"] = json.dumps(corpo)
        argumentos["content_type"] = "application/json"
    return getattr(client, metodo)(f"/api/leads{caminho}", **argumentos)


def _passo(executar_ate=DAQUI_A_POUCO):
    return {
        "descricao": "Ligar para combinar a proposta",
        "executar_ate": executar_ate,
        "evidencia_esperada": "Resumo da ligação",
    }


def _criar(client, token, lead, titular_id="com-ana", **extra):
    corpo = {
        "lead_id": str(lead.id),
        "etapa": "nova",
        "titular_id": titular_id,
        "fonte": {"tipo": "captura", "referencia_id": "lp-certificacao"},
        "proximo_passo": _passo(),
    }
    corpo.update(extra)
    return _chamar(client, "post", "/opportunities", token, corpo)


def _oportunidade(client, lead, token=ANA, titular_id="com-ana", **extra):
    resposta = _criar(client, token, lead, titular_id=titular_id, **extra)
    assert resposta.status_code == 201, resposta.content
    return resposta.json()


# ---------------------------------------------------------------------------
# A superfície: o que o contrato promete devolver
# ---------------------------------------------------------------------------


def test_criar_devolve_a_oportunidade_aberta_com_historico(
    client, comerciais, lead_do_site_a
):
    corpo = _oportunidade(client, lead_do_site_a)

    assert corpo["situacao"] == "aberta"
    assert corpo["etapa"] == "nova"
    assert corpo["titular"] == {"id": "com-ana", "funcao": "comercial"}
    assert corpo["fonte"] == {"tipo": "captura", "referencia_id": "lp-certificacao"}
    assert corpo["proximo_passo"]["descricao"] == "Ligar para combinar a proposta"
    assert "desfecho" not in corpo
    assert len(corpo["historico"]) == 1


def test_consulta_traz_o_historico_da_oportunidade(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/history",
        ANA,
        {"tipo": "contato", "descricao": "Falei por telefone", "evidencia": "aud-1"},
    )

    resposta = _chamar(client, "get", f"/opportunities/{criada['id']}", ANA)

    assert resposta.status_code == 200
    historico = resposta.json()["historico"]
    assert [registro["tipo"] for registro in historico] == [
        "etapa_alterada",
        "contato",
    ]
    assert historico[-1]["evidencia"] == "aud-1"
    assert historico[-1]["autor_id"] == "com-ana"


def test_listagem_pagina_e_devolve_cursor(client, comerciais, lead_do_site_a):
    from apps.core import oportunidades

    for _ in range(3):
        _oportunidade(client, lead_do_site_a)
    oportunidades.POR_PAGINA = 2
    try:
        primeira = _chamar(client, "get", "/opportunities", ANA).json()
        assert len(primeira["itens"]) == 2
        assert primeira["proximo_cursor"] is not None
        segunda = _chamar(
            client,
            "get",
            f"/opportunities?cursor={primeira['proximo_cursor']}",
            ANA,
        ).json()
    finally:
        oportunidades.POR_PAGINA = 50

    assert len(segunda["itens"]) == 1
    assert segunda["proximo_cursor"] is None
    assert "historico" not in segunda["itens"][0]


def test_listagem_atrasada_so_traz_passo_vencido_e_aberto(
    client, comerciais, lead_do_site_a
):
    _oportunidade(client, lead_do_site_a, proximo_passo=_passo(JA_VENCEU))
    em_dia = _oportunidade(client, lead_do_site_a)

    atrasadas = _chamar(client, "get", "/opportunities?atrasada=true", ANA).json()

    assert len(atrasadas["itens"]) == 1
    assert atrasadas["itens"][0]["id"] != em_dia["id"]


# ---------------------------------------------------------------------------
# Autorização: por titular e por site
# ---------------------------------------------------------------------------


def test_token_que_nao_e_conta_comercial_nao_entra(client, comerciais, lead_do_site_a):
    resposta = _criar(client, MAQUINA, lead_do_site_a)

    assert resposta.status_code == 403
    assert "COMERCIAIS_DO_CRM" in resposta.json()["detail"]


def test_outro_titular_do_mesmo_site_nao_le_a_oportunidade(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _chamar(client, "get", f"/opportunities/{criada['id']}", BRUNO)

    assert resposta.status_code == 403


def test_comercial_nao_abre_oportunidade_em_lead_de_outro_site(
    client, comerciais, lead_do_site_b
):
    resposta = _criar(client, ANA, lead_do_site_b)

    assert resposta.status_code == 403
    assert Oportunidade.objects.count() == 0


def test_comercial_nao_abre_oportunidade_no_nome_de_outro_titular(
    client, comerciais, lead_do_site_a
):
    resposta = _criar(client, ANA, lead_do_site_a, titular_id="com-bruno")

    assert resposta.status_code == 403
    assert Oportunidade.objects.count() == 0


def test_listagem_so_mostra_o_que_e_do_titular_e_do_site(
    client, comerciais, lead_do_site_a, lead_do_site_b
):
    _oportunidade(client, lead_do_site_a)
    _oportunidade(client, lead_do_site_b, token=CARLA, titular_id="com-carla")

    da_ana = _chamar(client, "get", "/opportunities", ANA).json()
    do_bruno = _chamar(client, "get", "/opportunities", BRUNO).json()

    assert len(da_ana["itens"]) == 1
    assert da_ana["itens"][0]["titular"]["id"] == "com-ana"
    assert do_bruno["itens"] == []


def test_listar_oportunidade_de_outro_titular_e_recusado(
    client, comerciais, lead_do_site_a
):
    resposta = _chamar(client, "get", "/opportunities?titular_id=com-bruno", ANA)

    assert resposta.status_code == 403


def test_oportunidade_inexistente_e_404(client, comerciais):
    resposta = _chamar(
        client,
        "get",
        "/opportunities/6f1b8f9e-0000-4000-8000-000000000000",
        ANA,
    )

    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# O histórico não se altera
# ---------------------------------------------------------------------------


def test_registro_de_historico_recusa_alteracao_e_remocao(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    registro = RegistroHistoricoOportunidade.objects.get(oportunidade_id=criada["id"])

    registro.descricao = "outra coisa"
    with pytest.raises(ValueError):
        registro.save()
    with pytest.raises(ValueError):
        registro.delete()

    registro.refresh_from_db()
    assert registro.descricao == "Oportunidade aberta na etapa nova."


def test_atualizar_etapa_acrescenta_registro_sem_tocar_nos_anteriores(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    primeiro = criada["historico"][0]

    resposta = _chamar(
        client, "patch", f"/opportunities/{criada['id']}", ANA, {"etapa": "proposta"}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["oportunidade"]["etapa"] == "proposta"
    assert corpo["evento"]["tipo"] == "etapa_alterada"
    assert corpo["oportunidade"]["historico"][0] == primeiro
    assert len(corpo["oportunidade"]["historico"]) == 2


def test_historico_so_aceita_os_tipos_humanos(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/history",
        ANA,
        {"tipo": "encerramento", "descricao": "tentando forjar"},
    )

    assert resposta.status_code == 422


# ---------------------------------------------------------------------------
# Transferência: pendente não troca o responsável
# ---------------------------------------------------------------------------


def _transferir(client, oportunidade_id, token=ANA, para="com-bruno"):
    return _chamar(
        client,
        "post",
        f"/opportunities/{oportunidade_id}/transfers",
        token,
        {"novo_titular_id": para, "motivo": "Ana entra de férias"},
    )


def test_transferencia_pendente_nao_troca_o_titular(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _transferir(client, criada["id"])

    assert resposta.status_code == 201
    assert resposta.json()["transferencia"]["estado"] == "pendente"
    assert resposta.json()["evento"]["tipo"] == "transferencia_solicitada"
    assert Oportunidade.objects.get(id=criada["id"]).titular_id == "com-ana"


def test_segunda_transferencia_pendente_e_recusada(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    _transferir(client, criada["id"])

    repetida = _transferir(client, criada["id"])

    assert repetida.status_code == 409
    assert TransferenciaResponsabilidade.objects.count() == 1


def test_so_o_novo_titular_aceita_a_transferencia(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    transferencia = _transferir(client, criada["id"]).json()["transferencia"]

    resposta = _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/transfers/{transferencia['id']}/accept",
        ANA,
    )

    assert resposta.status_code == 403
    assert Oportunidade.objects.get(id=criada["id"]).titular_id == "com-ana"


def test_aceite_troca_o_titular_e_registra_o_evento(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    transferencia = _transferir(client, criada["id"]).json()["transferencia"]

    resposta = _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/transfers/{transferencia['id']}/accept",
        BRUNO,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["oportunidade"]["titular"]["id"] == "com-bruno"
    assert corpo["evento"]["tipo"] == "transferencia_aceita"
    assert Oportunidade.objects.get(id=criada["id"]).titular_id == "com-bruno"


def test_aceite_repetido_nao_duplica_efeito(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    transferencia = _transferir(client, criada["id"]).json()["transferencia"]
    caminho = f"/opportunities/{criada['id']}/transfers/{transferencia['id']}/accept"
    _chamar(client, "post", caminho, BRUNO)

    repetido = _chamar(client, "post", caminho, BRUNO)

    assert repetido.status_code == 409
    assert (
        RegistroHistoricoOportunidade.objects.filter(
            oportunidade_id=criada["id"], tipo="transferencia_aceita"
        ).count()
        == 1
    )


def test_recusa_preserva_o_motivo_e_mantem_o_titular(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    transferencia = _transferir(client, criada["id"]).json()["transferencia"]

    resposta = _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/transfers/{transferencia['id']}/refuse",
        BRUNO,
        {"motivo": "Já acompanho esta pessoa por outro caminho"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["transferencia"]["estado"] == "recusada"
    assert corpo["transferencia"]["motivo_recusa"] == (
        "Já acompanho esta pessoa por outro caminho"
    )
    assert corpo["evento"]["tipo"] == "transferencia_recusada"
    assert Oportunidade.objects.get(id=criada["id"]).titular_id == "com-ana"


def test_recusa_sem_motivo_e_recusada(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)
    transferencia = _transferir(client, criada["id"]).json()["transferencia"]

    resposta = _chamar(
        client,
        "post",
        f"/opportunities/{criada['id']}/transfers/{transferencia['id']}/refuse",
        BRUNO,
        {"motivo": "   "},
    )

    assert resposta.status_code == 422
    assert (
        TransferenciaResponsabilidade.objects.get(id=transferencia["id"]).estado
        == "pendente"
    )


def test_transferencia_para_quem_nao_e_conta_do_site_e_recusada(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _transferir(client, criada["id"], para="com-carla")

    assert resposta.status_code == 422
    assert TransferenciaResponsabilidade.objects.count() == 0


# ---------------------------------------------------------------------------
# Encerramento e reabertura
# ---------------------------------------------------------------------------


def _encerrar(client, oportunidade_id, token=ANA, **extra):
    corpo = {
        "resultado": "ganha",
        "motivo": "Assinou o contrato",
        "evidencia": "proposta-2026-11.pdf",
    }
    corpo.update(extra)
    return _chamar(
        client, "post", f"/opportunities/{oportunidade_id}/close", token, corpo
    )


def test_encerramento_guarda_o_desfecho_com_evidencia(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _encerrar(client, criada["id"])

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["oportunidade"]["situacao"] == "encerrada"
    assert corpo["oportunidade"]["etapa"] == "ganha"
    assert corpo["oportunidade"]["desfecho"]["evidencia"] == "proposta-2026-11.pdf"
    assert corpo["oportunidade"]["desfecho"]["encerrada_em"]
    assert corpo["evento"]["tipo"] == "encerramento"


def test_encerramento_sem_evidencia_e_recusado(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)

    resposta = _encerrar(client, criada["id"], evidencia="")

    assert resposta.status_code == 422
    assert Oportunidade.objects.get(id=criada["id"]).desfecho_encerrada_em is None


def test_encerrar_duas_vezes_nao_reescreve_o_desfecho(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    primeira = _encerrar(client, criada["id"]).json()

    repetida = _encerrar(client, criada["id"], motivo="outro motivo")

    assert repetida.status_code == 409
    oportunidade = Oportunidade.objects.get(id=criada["id"])
    assert oportunidade.desfecho_motivo == "Assinou o contrato"
    assert oportunidade.desfecho_encerrada_em.isoformat() == (
        primeira["oportunidade"]["desfecho"]["encerrada_em"]
    )


def test_oportunidade_encerrada_nao_aceita_atualizacao(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    _encerrar(client, criada["id"])

    resposta = _chamar(
        client, "patch", f"/opportunities/{criada['id']}", ANA, {"etapa": "proposta"}
    )

    assert resposta.status_code == 409


def test_reabertura_exige_encerramento_e_devolve_a_oportunidade_aberta(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    corpo = {
        "motivo": "O cliente voltou a responder",
        "etapa": "negociacao",
        "proximo_passo": _passo(),
    }

    ainda_aberta = _chamar(
        client, "post", f"/opportunities/{criada['id']}/reopen", ANA, corpo
    )
    assert ainda_aberta.status_code == 409

    _encerrar(client, criada["id"], resultado="perdida", motivo="Sumiu")
    reaberta = _chamar(
        client, "post", f"/opportunities/{criada['id']}/reopen", ANA, corpo
    )

    assert reaberta.status_code == 200
    devolvida = reaberta.json()["oportunidade"]
    assert devolvida["situacao"] == "aberta"
    assert devolvida["etapa"] == "negociacao"
    assert "desfecho" not in devolvida
    assert reaberta.json()["evento"]["tipo"] == "reabertura"
    assert [registro["tipo"] for registro in devolvida["historico"]] == [
        "etapa_alterada",
        "encerramento",
        "reabertura",
    ]


# ---------------------------------------------------------------------------
# Efeito e registro vivem na mesma transação
# ---------------------------------------------------------------------------


def test_falha_ao_registrar_desfaz_a_mudanca_da_etapa(
    client, comerciais, lead_do_site_a, monkeypatch
):
    from apps.core import oportunidades

    criada = _oportunidade(client, lead_do_site_a)

    def explodir(*args, **kwargs):
        raise RuntimeError("banco caiu no meio")

    monkeypatch.setattr(oportunidades, "_registrar", explodir)

    with pytest.raises(RuntimeError):
        _chamar(
            client,
            "patch",
            f"/opportunities/{criada['id']}",
            ANA,
            {"etapa": "proposta"},
        )

    assert Oportunidade.objects.get(id=criada["id"]).etapa == "nova"


def test_payload_fora_do_contrato_e_recusado(client, comerciais, lead_do_site_a):
    criada = _oportunidade(client, lead_do_site_a)

    vazio = _chamar(client, "patch", f"/opportunities/{criada['id']}", ANA, {})
    estranho = _chamar(
        client,
        "patch",
        f"/opportunities/{criada['id']}",
        ANA,
        {"titular_id": "com-bruno"},
    )
    sem_fuso = _chamar(
        client,
        "patch",
        f"/opportunities/{criada['id']}",
        ANA,
        {"proximo_passo": _passo("2026-12-01T15:00:00")},
    )

    assert vazio.status_code == 422
    assert estranho.status_code == 422
    assert sem_fuso.status_code == 422
    assert Oportunidade.objects.get(id=criada["id"]).titular_id == "com-ana"


def test_passo_vencido_aparece_como_atrasado_na_hora_certa(
    client, comerciais, lead_do_site_a
):
    criada = _oportunidade(client, lead_do_site_a)
    assert (
        _chamar(client, "get", "/opportunities?atrasada=true", ANA).json()["itens"]
        == []
    )

    Oportunidade.objects.filter(id=criada["id"]).update(
        passo_executar_ate=timezone.now() - timedelta(minutes=1)
    )

    atrasadas = _chamar(client, "get", "/opportunities?atrasada=true", ANA).json()
    assert [item["id"] for item in atrasadas["itens"]] == [criada["id"]]
