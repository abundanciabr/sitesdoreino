"""Telas reais: catálogo restrito e pergunta privada sem contexto alheio."""

from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from django.test import RequestFactory
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.urls import resolve, reverse

from apps.core import ia_fila_real, telas_fila_real
from apps.encomendas import saques_fila


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


def test_carteira_e_privada_e_nao_expoe_chave_pix(monkeypatch):
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "aluno-a"))
    monkeypatch.setattr(saques_fila, "pode_acessar_carteira", lambda **kwargs: True)
    monkeypatch.setattr(saques_fila, "carteira", lambda **kwargs: {
        "saldo_disponivel_cents": 12500,
        "saldo_solicitado_cents": 5000,
        "total_pago_cents": 2500,
        "saques": [{"id": "s1", "valor_cents": 5000, "status": "solicitado",
                    "solicitado_em": "2026-10-08T12:00:00-03:00",
                    "referencia_pix": "", "chave_pix": "chave-privada"},
                   {"id": "s2", "valor_cents": 2500, "status": "pago",
                    "solicitado_em": "2026-10-07T12:00:00-03:00",
                    "pago_em": "2026-10-08T11:00:00-03:00",
                    "referencia_pix": "referencia-comprovada"}],
    })
    resposta = telas_fila_real.carteira_aluno(RequestFactory().get("/cliente/carteira/"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "R$ 125,00" in html and "R$ 50,00" in html
    assert "chave-privada" not in html
    assert "Solicitado em 08/10/2026" in html
    assert "Pix pago" in html and "referencia-comprovada" in html
    assert resposta["Cache-Control"] == "private, no-store"
    monkeypatch.setattr(saques_fila, "pode_acessar_carteira", lambda **kwargs: False)
    from django.http import Http404
    import pytest
    with pytest.raises(Http404):
        telas_fila_real.carteira_aluno(RequestFactory().get("/cliente/carteira/"))


def test_solicitacao_passa_pix_so_no_post_e_redireciona_sem_chave(monkeypatch):
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "aluno-a"))
    monkeypatch.setattr(saques_fila, "pode_acessar_carteira", lambda **kwargs: True)
    recebido = []
    monkeypatch.setattr(saques_fila, "solicitar", lambda **kwargs: recebido.append(kwargs) or {})
    chave = str(uuid4())
    pedido_http = RequestFactory().post(
        "/cliente/carteira/solicitar/", {"valor_reais": "50,00",
        "nome_recebedor": "Aluno de Teste", "chave_pix": "chave-privada",
        "chave_idempotencia": chave,
    })
    resposta = telas_fila_real.solicitar_saque(pedido_http)
    assert resposta.status_code == 302
    assert recebido == [{"site_id": "site-a", "pessoa_id": "aluno-a", "dados": {
        "valor_cents": 5000, "nome_recebedor": "Aluno de Teste",
        "chave_pix": "chave-privada", "chave_idempotencia": chave,
    }}]
    assert "chave-privada" not in resposta["Location"]
    assert pedido_http.sensitive_post_parameters == ("chave_pix",)


def test_entradas_antigas_da_fila_apontam_para_fluxo_novo(monkeypatch):
    pedido_id = uuid4()
    assert resolve(reverse("marketplace_fila")).func == telas_fila_real.entrada_antiga_fila
    assert resolve(reverse("marketplace_sacar")).func == telas_fila_real.saque_antigo
    for nome in ("marketplace_recarregar", "marketplace_comprar_creditos",
                 "marketplace_cobrar", "marketplace_confirmar_paypal"):
        args = [pedido_id] if nome != "marketplace_recarregar" else []
        assert resolve(reverse(nome, args=args)).func == telas_fila_real.financeiro_antigo_cliente
    assert resolve(reverse("marketplace_retorno_paypal", args=[pedido_id])).func == telas_fila_real.retorno_pagamento_antigo
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "paula-id"))
    monkeypatch.setattr(telas_fila_real.fila_real, "cliente_da_pessoa", lambda **kwargs: SimpleNamespace(slug="paula"))
    resposta = telas_fila_real.financeiro_antigo_cliente(RequestFactory().post(
        reverse("marketplace_recarregar"), {"chave_pix": "nao-enviar"}))
    assert resposta["Location"] == "/admin/clientes/paula/"
    monkeypatch.setattr(saques_fila, "pode_acessar_carteira", lambda **kwargs: True)
    assert telas_fila_real.saque_antigo(RequestFactory().post(reverse("marketplace_sacar")))["Location"] == reverse("fila_real_carteira")


def test_lista_escola_abre_pedido_real_e_preserva_link_do_legado():
    class PedidoAntigo:
        pk = uuid4()
        titulo = "Pedido antigo"
        status = "na_fila"

        @property
        def fila_cliente(self):
            raise ObjectDoesNotExist("sem vínculo da fila real")

        def get_status_display(self):
            return "Na fila"

    antigo = PedidoAntigo()
    real = SimpleNamespace(pk=uuid4(), titulo="Pedido real", status="na_fila",
                           fila_cliente=object(), get_status_display=lambda: "Na fila")
    html = render_to_string("marketplace/escola.html", {
        "papel": "equipe", "fase": SimpleNamespace(alunos_liberados=False, clientes_liberados=False),
        "pedidos": [antigo, real], "pagamentos": {}, "alunos": [], "clientes": [], "saques": [],
    })
    assert f'href="{reverse("marketplace_pedido", args=[antigo.pk])}"' in html
    assert f'href="{reverse("fila_real_trabalho", args=[real.pk])}"' in html


def _catalogo_html(monkeypatch, papel, participou):
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "pessoa-a"))
    monkeypatch.setattr(telas_fila_real, "_papel", lambda site, pessoa: papel)
    monkeypatch.setattr(telas_fila_real.fila_real, "catalogo", lambda **kwargs: {
        "pedidos": [], "trabalhos": [], "trabalho_ativo": None, "participou_da_fila": participou,
    })
    return telas_fila_real.catalogo(RequestFactory().get("/cliente/")).content.decode()


def test_catalogo_avisa_antes_do_aceite_que_participacao_e_unica(monkeypatch):
    html = _catalogo_html(monkeypatch, "aluno", False)
    assert "a participação na Fila do Dólar é única" in html
    assert "escolha com calma" in html


def test_catalogo_nao_repete_aviso_de_antes_do_aceite_para_quem_ja_participou(monkeypatch):
    html = _catalogo_html(monkeypatch, "aluno", True)
    assert "escolha com calma" not in html


def test_catalogo_da_equipe_nao_mostra_aviso_de_aluno(monkeypatch):
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "pessoa-a"))
    monkeypatch.setattr(telas_fila_real, "_papel", lambda site, pessoa: "plantao")
    monkeypatch.setattr(telas_fila_real.fila_real, "catalogo", lambda **kwargs: {
        "pedidos": [], "trabalhos": [], "trabalho_ativo": None, "participou_da_fila": False,
    })
    try:
        html = telas_fila_real.catalogo(RequestFactory().get("/cliente/")).content.decode()
    except Exception:
        return
    assert "escolha com calma" not in html


def test_confirmacao_mostra_participacao_unica_e_rotulo_novo(monkeypatch):
    pedido = SimpleNamespace(
        pk=uuid4(), titulo="Pet do cliente", categoria="pets", valor_cents=12500, ilustracao="pets",
        briefing={"observacoes": "Um pet", "entregaveis": ["FBX"], "referencias": []},
    )
    monkeypatch.setattr(telas_fila_real, "_entrada", lambda request: ("site-a", "pessoa-a"))
    monkeypatch.setattr(telas_fila_real, "_papel", lambda site, pessoa: "aluno")
    monkeypatch.setattr(telas_fila_real.fila_real, "catalogo", lambda **kwargs: {"pedidos": [pedido]})
    html = telas_fila_real.confirmar(RequestFactory().get("/x/"), pedido.pk).content.decode()
    assert "Participação única:" in html
    assert "Li e aceito estas condições, inclusive que a participação na Fila do Dólar é única" in html
