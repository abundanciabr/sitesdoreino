from unittest.mock import patch

from django.test import RequestFactory

from apps.core.pagamentos import pagamentos, pagamentos_devolver
from apps.core.clients import PagamentosClient


def _pedido(method, path="/pagamentos/"):
    pedido = getattr(RequestFactory(), method)(path, HTTP_HOST="meshcraft.top")
    pedido.admin = {"email": "admin@example.test"}
    return pedido


def test_pagina_mostra_empresa_valor_e_confirmacao():
    compra = {
        "pedido": "pedido-1", "valor_centavos": 990, "empresa": "mercadopago",
        "estado": "approved", "metodo": "card", "data": "2026-10-03",
        "segunda_empresa": True, "estorno": "", "pode_devolver": True,
        "tentativa_id": "123", "presa": False,
    }
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina",
        return_value={"compras": [compra], "pagina": 1, "total": 1,
                      "paginas": 1, "mais": False},
    ):
        resposta = pagamentos(_pedido("get"))
    assert resposta.status_code == 200
    assert b"R$ 9,90" in resposta.content
    assert b"mercadopago" in resposta.content
    assert b"Devolver" in resposta.content


def test_pagina_antiga_mostra_devolver_e_volta_a_mesma_pagina():
    compra = {
        "pedido": "pedido-antigo", "valor_centavos": 990, "empresa": "mercadopago",
        "estado": "approved", "metodo": "card", "data": "2026-10-03",
        "segunda_empresa": False, "estorno": "", "pode_devolver": True,
        "tentativa_id": "321", "presa": False,
    }
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina",
        return_value={"compras": [compra], "pagina": 2, "total": 101,
                      "paginas": 2, "mais": False},
    ) as listar:
        resposta = pagamentos(_pedido("get", "/pagamentos/?pagina=2"))
    listar.assert_called_once_with("site-um", 2)
    assert b"pedido-antigo" in resposta.content
    assert b'"pagina" value="2"' in resposta.content
    assert b"Compras mais recentes" in resposta.content
    assert b"Devolver" in resposta.content

    pedido = RequestFactory().post(
        "/pagamentos/devolver", {"tentativa_id": "321", "pagina": "2"},
        HTTP_HOST="meshcraft.top",
    )
    pedido.admin = {"email": "admin@example.test"}
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.devolver",
        return_value=(200, {"estorno": "solicitado"}),
    ) as devolver:
        redirecionamento = pagamentos_devolver(pedido)
    devolver.assert_called_once_with("site-um", "321")
    assert redirecionamento["Location"].endswith("?pagina=2&resultado=solicitado")


def test_cliente_envia_numero_da_pagina_ao_servico():
    dados = {"compras": [{"id": "1"}], "pagina": 2, "total": 101,
             "paginas": 2, "mais": False}
    with patch.object(PagamentosClient, "_pedir", return_value=(200, dados)) as pedir:
        assert PagamentosClient().compras_pagina("site/um", 2) == dados
    pedir.assert_called_once_with("GET", "/interno/admin/compras/site%2Fum?pagina=2")


def test_post_usa_site_do_host_e_id_da_tentativa():
    tentativa = "123"
    pedido = RequestFactory().post(
        "/pagamentos/devolver", {"tentativa_id": tentativa}, HTTP_HOST="meshcraft.top"
    )
    pedido.admin = {"email": "admin@example.test"}
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.devolver", return_value=(200, {"estorno": "solicitado"})
    ) as devolver:
        resposta = pagamentos_devolver(pedido)
    assert resposta.status_code == 302
    devolver.assert_called_once_with("site-um", tentativa)


def test_pagina_mostra_o_que_as_empresas_responderam():
    compra = {
        "pedido": "pedido-1", "valor_centavos": 990, "empresa": "appmax",
        "estado": "rejected", "metodo": "card", "data": "2026-10-03",
        "segunda_empresa": False, "estorno": "", "pode_devolver": False,
        "tentativa_id": "123", "presa": False,
    }
    observacao = [
        {"empresa": "appmax", "origem": "aviso_order_refused_by_risk",
         "status": "cancelado", "detalhe": "", "total": 3, "ultima": ""},
        {"empresa": "mercadopago", "origem": "criacao", "status": "rejected",
         "detalhe": "rejected_by_regulations", "total": 1, "ultima": ""},
        {"empresa": "mercadopago", "origem": "aviso", "status": "rejected",
         "detalhe": "x", "total": "2"},
    ]
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina",
        return_value={"compras": [compra], "pagina": 1, "total": 1,
                      "paginas": 1, "mais": False, "observacao": observacao},
    ):
        resposta = pagamentos(_pedido("get"))
    html = resposta.content.decode()
    assert "O que as empresas responderam" in html
    assert "GET depois do aviso de risco" in html
    assert "cancelado" in html and "rejected_by_regulations" in html
    assert "Ao criar o Pix" in html
    # Linha sem total inteiro não aparece.
    assert "Aviso do Mercado Pago" not in html


def test_pagina_sem_observacao_nao_mostra_a_tabela():
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina",
        return_value={"compras": [], "pagina": 1, "total": 0,
                      "paginas": 1, "mais": False},
    ):
        resposta = pagamentos(_pedido("get"))
    assert "O que as empresas responderam" not in resposta.content.decode()
