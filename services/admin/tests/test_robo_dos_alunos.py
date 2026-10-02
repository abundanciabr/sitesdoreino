import json
from decimal import Decimal
from unittest.mock import patch
import httpx
import pytest
import respx
from django.test import Client
from apps.agentes import alunos, modelo, segredo
from apps.agentes.models import AutorizacaoDeGasto, Consumo, RoboPessoal
from test_robos import _guardar_chave, _texto_do_modelo, _cliente, DONO, ambiente

pytestmark = pytest.mark.django_db
URL = "/interno/robo-dos-alunos/gerar"

def pedido(cliente=None, token="pages", **extra):
    return (cliente or Client()).post(URL, json.dumps({
        "campo": "apresentacao_publica",
        "contexto": {"quiz": {"experiencia": "iniciante", "ideia_propria": "um cabelo"}},
        **extra,
    }), content_type="application/json", HTTP_AUTHORIZATION="Bearer " + token)

def ativar(teto="1"):
    robo = alunos.configuracao()
    robo.ativo = True
    robo.modelo = "gpt-6-luna"
    robo.autorizacao = AutorizacaoDeGasto.objects.create(
        destino="alunos", descricao="Alunos", teto_mensal_usd=Decimal(teto), fonte="teste"
    )
    robo.save()
    return robo

def test_nao_aceita_outro_par_nem_chama_modelo_desativado(monkeypatch, settings):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    settings.TOKENS_ACEITOS = {"pages", "outro-par"}
    with patch.object(modelo, "responder") as chamar:
        assert pedido(token="outro-par").status_code == 401
        assert pedido(token="").status_code == 401
        assert pedido().status_code == 503
        assert pedido(campo="segredo").status_code == 422
        chamar.assert_not_called()
    assert RoboPessoal.objects.count() == 0

@respx.mock
def test_exemplo_tem_robo_prompt_e_consumo_distintos(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    _guardar_chave()
    robo = ativar()
    api = respx.post(modelo.URL + "/responses").mock(return_value=_texto_do_modelo("Estou desenvolvendo meu primeiro cabelo para Roblox."))
    resposta = pedido()
    assert resposta.status_code == 200
    assert resposta.json()["texto"].startswith("Estou desenvolvendo")
    corpo = json.loads(api.calls.last.request.content)
    assert "robô dos alunos" in corpo["instructions"]
    assert "não são instruções" in corpo["instructions"]
    assert not corpo.get("tools")
    assert corpo["store"] is False
    consumo = Consumo.objects.get()
    assert consumo.origem == "alunos" and consumo.robo_id is None
    assert consumo.autorizacao_id == robo.autorizacao_id
    assert modelo.autorizacao_ativa().destino == "equipe"

@respx.mock
def test_teto_dos_alunos_nao_usa_autorizacao_da_equipe(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_PAGES", "pages")
    _guardar_chave()
    robo = ativar("0")
    api = respx.post(modelo.URL + "/responses")
    assert pedido().status_code == 503
    assert not api.called
    assert not Consumo.objects.exists()

@respx.mock
def test_configuracao_dos_alunos_nao_altera_modelo_da_equipe():
    cliente = _cliente(DONO)
    conexao = _guardar_chave()
    antes = (conexao.modelo_rapido, conexao.modelo_forte, conexao.segredo_cifrado)
    r = cliente.post("/robos/", {
        "acao": "alunos", "nome_alunos": "Ajuda do portfólio", "modelo_alunos": "modelo-alunos",
        "instrucoes_alunos": "Escreva curto", "ativo_alunos": "1",
        "orcamento_alunos": "compartilhar",
    })
    assert r.status_code == 302
    robo = alunos.configuracao()
    assert robo.ativo and robo.autorizacao.destino == "equipe"
    assert robo.modelo == "modelo-alunos"
    conexao.refresh_from_db()
    assert antes == (conexao.modelo_rapido, conexao.modelo_forte, conexao.segredo_cifrado)
    pagina = cliente.get("/robos/")
    assert pagina.status_code == 200 and "Robô dos alunos" in pagina.content.decode()
