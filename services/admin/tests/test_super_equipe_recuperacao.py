import copy
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.agentes.models import Consumo, Execucao, RoboPessoal
from apps.agentes.views_super_equipe import super_equipe_acao, super_equipe
from tests.test_super_equipe_automatica import rotina, melhoria


def consultar(item, dados=None, admin=None):
    r = (RequestFactory().get("/") if dados is None else
         RequestFactory().post("/", data=json.dumps(dados), content_type="application/json"))
    r.admin = {"robo": True} if admin is None else admin
    return super_equipe_acao(r, item.pk)


@pytest.fixture
def interrompida(melhoria):
    trabalho = Execucao.objects.create(robo=RoboPessoal.objects.first(), tipo="super_equipe")
    melhoria.trabalho = trabalho
    melhoria.situacao = "mantenedor"
    melhoria.resultado = "Interrupção original"
    melhoria.posse = "executor-vps-anterior"
    c = Consumo.objects.create(execucao=trabalho, modelo="gpt-6-sol", origem="super_equipe_codigo",
        resposta_id="resp-salva", tokens_entrada=100, tokens_saida=10, custo_estimado_usd="0.01")
    Consumo.objects.create(execucao=trabalho, modelo="gpt-6-sol", origem="super_equipe_codigo",
        tokens_entrada=500, tokens_saida=7000, custo_estimado_usd="0.228772", desconhecido=True)
    Consumo.objects.create(execucao=trabalho, modelo="gpt-6-sol", origem="super_equipe",
        custo_estimado_usd="0.5")  # os pareceres não são custo do desenvolvimento
    Consumo.objects.create(modelo="gpt-6-sol", origem="super_equipe_codigo",
        custo_estimado_usd="0.9")  # não atribuir chamadas de outro trabalho
    melhoria.desenvolvimento = {"rodadas": {
        "primeira": {"resposta": {"acao": "ler", "motivo": "conteúdo interno"},
            "consumo_id": c.pk, "custo_usd": "0.010000"}, "interrompida": {"base": "a"*40}},
        "historico": [{"resultado": "Episódio preservado"}]}
    melhoria.save()
    return melhoria


def test_conferencia_separa_reserva_e_uso_sem_reenviar_ou_reabrir(interrompida):
    item = interrompida
    original = copy.deepcopy(item.desenvolvimento)
    consumos = list(Consumo.objects.values())
    with patch("apps.agentes.modelo.responder") as chamada:
        leitura = consultar(item)
        assert leitura.status_code == 200
        assert leitura["Cache-Control"] == "no-store"
        dados = json.loads(leitura.content)
        assert dados["custo_calculado_do_uso_usd"] == "0.010000"
        assert dados["reserva_sem_confirmacao_usd"] == "0.228772"
        assert len(dados["consumos_do_trabalho"]) == 2
        assert not dados["consumos_do_trabalho"][1]["vinculado_a_rodada"]
        assert dados["rodadas"][1]["consumo_id"] is None
        assert "motivo" not in leitura.content.decode()
        item.refresh_from_db()
        assert item.desenvolvimento == original  # GET não altera nada
        pedido = {"acao": "conferir_recuperacao", "assinatura": dados["assinatura"]}
        assert consultar(item, pedido).status_code == 200
        assert consultar(item, pedido).status_code == 200
        chamada.assert_not_called()
    item.refresh_from_db()
    assert item.situacao == "mantenedor" and item.posse == "executor-vps-anterior"
    assert item.desenvolvimento["rodadas"] == original["rodadas"]
    assert item.desenvolvimento["historico"] == original["historico"]
    assert len(item.desenvolvimento["conferencias"]) == 1
    assert item.desenvolvimento["conferencias"][0]["resultado_anterior"] == "Interrupção original"
    assert item.eventos.filter(texto__startswith="Recuperação conferida").count() == 1
    assert list(Consumo.objects.values()) == consumos
    assert "Reserva não é cobrança confirmada" in item.resultado


def test_consulta_e_registro_exigem_admin(interrompida):
    for admin in ({}, {"equipe_apenas": True}):
        assert consultar(interrompida, admin=admin).status_code == 403
        assert consultar(interrompida, {"acao": "conferir_recuperacao"}, admin=admin).status_code == 403


def test_painel_exibe_conferencia_e_custos_separados(interrompida):
    dados = json.loads(consultar(interrompida).content)
    consultar(interrompida, {"acao": "conferir_recuperacao", "assinatura": dados["assinatura"]})
    r = RequestFactory().get("/admin/super-equipe/")
    r.admin = {"robo": True}
    resposta = super_equipe(r)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "US$ 0.010000" in html and "US$ 0.228772 reservados sem confirmação" in html
    assert "Retomada não liberada" in html


def test_conferencia_obsoleta_nao_sobrescreve_evidencia(interrompida):
    dados = json.loads(consultar(interrompida).content)
    Consumo.objects.filter(execucao=interrompida.trabalho, desconhecido=True).update(
        desconhecido=False, resposta_id="resp-recebida", custo_estimado_usd="0.02")
    assert consultar(interrompida, {"acao": "conferir_recuperacao", "assinatura": dados["assinatura"]}).status_code == 409
    interrompida.refresh_from_db()
    assert "conferencias" not in interrompida.desenvolvimento


@pytest.mark.parametrize("situacao,posse_ativa", [("executando", False), ("publicando", False),
    ("resolvida", False), ("mantenedor", True)])
def test_conferencia_nao_interfere_em_execucao_ou_publicacao(interrompida, situacao, posse_ativa):
    interrompida.situacao = situacao
    if posse_ativa:
        interrompida.ocupada_ate = timezone.now() + timedelta(minutes=5)
    interrompida.save()
    dados = json.loads(consultar(interrompida).content)
    assert consultar(interrompida, {"acao": "conferir_recuperacao", "assinatura": dados["assinatura"]}).status_code == 409
    interrompida.refresh_from_db()
    assert "conferencias" not in interrompida.desenvolvimento
