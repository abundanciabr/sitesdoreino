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
    assert "Mercado Pago".encode() in resposta.content
    assert b"Devolver" in resposta.content


def test_pagina_fala_portugues_com_recusa_troca_e_devolucao():
    desviada = {
        "pedido": "pedido-desviado", "valor_centavos": 990, "empresa": "mercadopago",
        "primeira_empresa": "appmax", "estado": "approved", "metodo": "card",
        "data": "2026-10-03T23:28:00+00:00", "segunda_empresa": True,
        "motivo": "recusado_por_risco", "estorno": "contestacao",
        "pode_devolver": False, "tentativa_id": "7", "presa": False,
    }
    recusada = {
        "pedido": "pedido-recusado", "valor_centavos": 990, "empresa": "appmax",
        "primeira_empresa": "appmax", "estado": "rejected", "metodo": "pix",
        "data": "2026-10-03T12:00:00+00:00", "segunda_empresa": False,
        "motivo": "codigo_novo_da_empresa", "estorno": "", "pode_devolver": False,
        "tentativa_id": "8", "presa": False,
    }
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina",
        return_value={"compras": [desviada, recusada], "pagina": 1, "total": 2,
                      "paginas": 1, "mais": False},
    ):
        html = pagamentos(_pedido("get")).content.decode()
    assert "03/10/2026 20:28" in html
    assert "Appmax → Mercado Pago" in html
    assert "Antifraude da Appmax" in html
    assert "Contestada pelo comprador" in html
    assert "Aprovada" in html and "Recusada" in html and "Cartão" in html
    assert "codigo novo da empresa" in html
    assert "approved" not in html and "recusado_por_risco" not in html
    assert "Devolver</button>" not in html


def _devolver_com(resposta_do_servico):
    pedido = RequestFactory().post(
        "/pagamentos/devolver", {"tentativa_id": "5", "pagina": "1"},
        HTTP_HOST="meshcraft.top",
    )
    pedido.admin = {"email": "admin@example.test"}
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.devolver", return_value=resposta_do_servico,
    ):
        return pagamentos_devolver(pedido)["Location"]


def test_resultado_da_devolucao_diz_o_que_aconteceu():
    assert _devolver_com((200, {"estorno": "solicitado"})).endswith("resultado=solicitado")
    assert _devolver_com((200, {"estorno": "ambiguo"})).endswith("resultado=aguardando")
    assert _devolver_com((200, {"estorno": "confirmado"})).endswith("resultado=devolvida")
    assert _devolver_com((409, {"detail": "x"})).endswith("resultado=conferir")
    assert _devolver_com(None).endswith("resultado=incerto")
    with patch("apps.core.pagamentos.site_de", return_value="site-um"), patch(
        "apps.core.pagamentos.PagamentosClient.compras_pagina", return_value=None,
    ):
        html = pagamentos(_pedido("get", "/pagamentos/?resultado=aguardando")).content.decode()
    assert "Não precisa clicar de novo" in html


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
