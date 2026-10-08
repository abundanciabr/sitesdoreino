"""Telas reais: catálogo restrito e pergunta privada sem contexto alheio."""

from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from django.test import RequestFactory

from apps.core import ia_fila_real, telas_fila_real


def test_catalogo_real_reaproveita_categorias_sem_exibir_orcamento(monkeypatch):
    pedido = SimpleNamespace(
        pk=uuid4(), titulo="Pet do cliente", categoria="pets", valor_cents=12500,
        briefing={"observacoes": "Um pet", "entregaveis": ["FBX"], "referencias": []},
    )
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "aluno-a"))
    monkeypatch.setattr(telas_fila_real, "_papel", lambda site, pessoa: "aluno")
    monkeypatch.setattr(telas_fila_real.fila_real, "catalogo", lambda **kwargs: {
        "pedidos": [pedido], "trabalhos": [], "trabalho_ativo": None,
    })
    resposta = telas_fila_real.catalogo(RequestFactory().get("/cliente/?categoria=pets"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Pet do cliente" in html
    assert "R$ 125,00" in html
    assert "48 horas" in html
    assert "R$ 5.000" not in html


def test_cliente_vinculado_abre_sua_pagina_admin_sem_fase_legacy(monkeypatch):
    cliente = SimpleNamespace(slug="paula")
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "paula-id"))
    monkeypatch.setattr(telas_fila_real.plantao, "e_do_plantao", lambda pessoa: False)
    monkeypatch.setattr(telas_fila_real.fila_real, "cliente_da_pessoa", lambda **kwargs: cliente)
    monkeypatch.setattr(telas_fila_real.marketplace, "acesso_aluno", lambda **kwargs: False)
    resposta = telas_fila_real.catalogo(RequestFactory().get("/cliente/"))
    assert resposta.status_code == 302
    assert resposta["Location"] == "/admin/clientes/paula/"


def test_orientacao_externa_contem_somente_pergunta_escolhida(monkeypatch):
    chamadas = []
    modelo = SimpleNamespace(
        autorizacao_ativa=lambda: SimpleNamespace(pk=1),
        conexao=lambda: SimpleNamespace(modelo_rapido="modelo-teste"),
        responder=lambda **kwargs: chamadas.append(kwargs) or SimpleNamespace(
            completa=True, chamadas=[], texto="Peça confirmação no chat humano."
        ),
    )
    real_import = ia_fila_real.importlib.import_module

    def importar(nome):
        if nome == "config.runtime":
            return SimpleNamespace(serving=lambda tipo: nullcontext())
        if nome == "modules.admin.apps.agentes.modelo":
            return modelo
        return real_import(nome)

    monkeypatch.setattr(ia_fila_real.importlib, "import_module", importar)
    texto = ia_fila_real._consultar_modelo("Como fazer uma prévia?")
    assert texto == "Peça confirmação no chat humano."
    assert chamadas[0]["itens"] == [{"role": "user", "content": "Como fazer uma prévia?"}]
    assert chamadas[0]["ferramentas"] is None
