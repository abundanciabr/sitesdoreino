import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import clientes_fila


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "id-token")
    monkeypatch.setenv("ENCOMENDAS_API_URL", "http://encomendas:8000/api/encomendas")
    monkeypatch.setenv("ENCOMENDAS_API_TOKEN", "leitura")
    monkeypatch.setenv("ENCOMENDAS_API_TOKEN_ESCRITA", "escrita")
    settings.ADMIN_EMAILS = "admin@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"


def _entrar(email, pessoa="pessoa-1"):
    respx.get("http://identidade:8000/interno/sessao/completa").mock(
        return_value=httpx.Response(200, json={
            "autenticado": True, "id": pessoa, "email": email,
            "nome_exibido": email, "papel": None,
        })
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=sessao"
    return cliente


@respx.mock
def test_cliente_ve_somente_propria_pagina_sem_menu_admin():
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/acesso/pessoa-1").mock(
        return_value=httpx.Response(200, json={"slug": "paula", "pessoa_id": "pessoa-1"})
    )
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/paula?pessoa_id=pessoa-1").mock(
        return_value=httpx.Response(200, json={"nome": "Paula", "slug": "paula", "pedidos": []})
    )
    cliente = _entrar("paula@exemplo.com")
    resposta = cliente.get(reverse("cliente_fila", args=["paula"]))
    assert resposta.status_code == 200
    assert b"Paula" in resposta.content
    assert b'aria-label="Se' not in resposta.content
    assert cliente.get(reverse("cliente_fila", args=["anne"])).status_code == 404
    assert cliente.get(reverse("clientes_fila")).status_code == 404
    assert cliente.get(reverse("visao_geral")).status_code == 404


@respx.mock
def test_admin_ve_lista_e_cliente_nao_pode_vincular():
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila").mock(
        return_value=httpx.Response(200, json={"clientes": [
            {"nome": "Tilon", "slug": "tilon", "disponivel_cents": 500000},
            {"nome": "Paula", "slug": "paula", "disponivel_cents": 500000},
            {"nome": "Anne", "slug": "anne", "disponivel_cents": 500000},
        ]})
    )
    resposta = _entrar("admin@exemplo.com").get(reverse("clientes_fila"))
    assert resposta.status_code == 200
    assert b"Tilon" in resposta.content and b"Paula" in resposta.content and b"Anne" in resposta.content
    assert b"5.000,00" in resposta.content


@respx.mock
def test_formulario_fixa_um_item_e_48_horas(monkeypatch):
    class Dublê:
        def __init__(self):
            self.dados = None

        def pedido(self, slug, dados, pedido_id=None):
            self.dados = dados
            return {}

    duble = Dublê()
    monkeypatch.setattr(clientes_fila, "ClientesFilaClient", lambda: duble)
    resposta = _entrar("admin@exemplo.com").post(reverse("criar_pedido_cliente_fila", args=["paula"]), {
        "titulo": "Pet", "categoria": "pets", "briefing": "Mascote azul",
        "entregaveis": "Arquivo .blend", "valor_reais": "80,00",
        "quantidade": "9", "prazo_horas": "999",
    })
    assert resposta.status_code == 302
    assert duble.dados["quantidade"] == 1
    assert duble.dados["prazo_horas"] == 48
    assert duble.dados["valor_cents"] == 8000
    assert duble.dados["administrativo"] is True


@respx.mock
def test_vinculo_usa_credencial_de_escrita_e_marca_admin_no_servidor():
    chamada = respx.post("http://encomendas:8000/api/encomendas/clientes-fila/paula/vincular").mock(
        return_value=httpx.Response(200, json={"slug": "paula"})
    )
    resposta = _entrar("admin@exemplo.com").post(reverse("vincular_cliente_fila", args=["paula"]), {
        "email": "paula@exemplo.com",
    })
    assert resposta.status_code == 302
    assert chamada.called
    assert chamada.calls[0].request.headers["Authorization"] == "Bearer escrita"
    assert b'"administrativo":true' in chamada.calls[0].request.content


@respx.mock
def test_edicao_em_producao_nao_envia_valor_nem_prazo():
    class Dublê:
        def __init__(self):
            self.dados = None

        def pedido(self, slug, dados, pedido_id=None):
            self.dados = dados
            return {}

    duble = Dublê()
    from uuid import uuid4
    monkey = pytest.MonkeyPatch()
    monkey.setattr(clientes_fila, "ClientesFilaClient", lambda: duble)
    try:
        resposta = _entrar("admin@exemplo.com").post(reverse("orientar_pedido_cliente_fila", args=["paula", uuid4()]), {
            "observacoes_cliente": "Faça a textura azul.", "valor_reais": "9999,99", "prazo_horas": "1",
        })
    finally:
        monkey.undo()
    assert resposta.status_code == 302
    assert duble.dados == {"observacoes_cliente": "Faça a textura azul.", "pessoa_id": "", "administrativo": True}


@respx.mock
def test_pedido_iniciado_mostra_conversa_e_orientacao_sem_editor_de_preco():
    from uuid import uuid4

    pedido_id = uuid4()
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/paula?administrativo=1").mock(
        return_value=httpx.Response(200, json={
            "nome": "Paula", "slug": "paula", "abertos": 0, "em_andamento": 1,
            "finalizados": 0, "pedidos": [{
                "id": str(pedido_id), "titulo": "Mascote", "categoria": "pets",
                "status": "em_producao", "valor_cents": 8000,
                "descricao": "Mascote azul", "referencias": ["Primeira", "Segunda"],
                "entregaveis": ["Arquivo .blend"], "termos_editaveis": False,
                "orientavel": True, "depositado_real": False,
            }],
        })
    )
    resposta = _entrar("admin@exemplo.com").get(reverse("cliente_fila", args=["paula"]))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "https://meshcraft.top/encomendas/cliente/trabalhos/" + str(pedido_id) + "/" in html
    assert "Enviar orientação" in html
    assert "Editar pedido" not in html
    assert "Pix ainda não confirmado" in html
    assert "Abertos (0)" in html and "Em andamento (1)" in html


@respx.mock
def test_saques_exclusivos_admin_e_sem_formulario_para_pagos():
    from uuid import uuid4

    saque_id = uuid4()
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais").mock(
        return_value=httpx.Response(200, json={"saques": [{
            "id": str(saque_id), "nome_recebedor": "Aluno Exemplo", "chave_pix": "chave-teste",
            "valor_cents": 5000, "status": "pago", "referencia_pix": "ref-teste",
        }]})
    )
    admin = _entrar("admin@exemplo.com")
    resposta = admin.get(reverse("saques_fila"))
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    assert "Cookie" in resposta["Vary"]
    assert b"Aluno Exemplo" in resposta.content and b"chave-teste" in resposta.content
    assert b"Registrar Pix" not in resposta.content

    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/acesso/pessoa-1").mock(
        return_value=httpx.Response(200, json={"slug": "paula", "pessoa_id": "pessoa-1"})
    )
    cliente = _entrar("paula@exemplo.com")
    assert cliente.get(reverse("saques_fila")).status_code == 404
    assert cliente.post(reverse("saque_fila_pago", args=[saque_id]), {}).status_code == 404


@respx.mock
def test_registro_pix_manual_envia_identificacao_completa_sem_reexibir_cpf():
    from uuid import uuid4
    import json

    saque_id = uuid4()
    chamada = respx.post(
        f"http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais/{saque_id}/pago"
    ).mock(return_value=httpx.Response(200, json={"status": "pago"}))
    resposta = _entrar("admin@exemplo.com", pessoa="admin-opaco").post(
        reverse("saque_fila_pago", args=[saque_id]), {
            "referencia_pix": "pix-banco-123", "pagador_nome": "Pessoa Pagadora",
            "pagador_cpf": "123.456.789-09", "pagador_email": "pagador@exemplo.com",
        }
    )
    assert resposta.status_code == 302
    assert b"123" not in resposta.content
    assert chamada.calls[0].request.headers["Authorization"] == "Bearer escrita"
    corpo = json.loads(chamada.calls[0].request.content)
    assert corpo == {
        "administrativo": True, "ator_id": "admin-opaco", "referencia_pix": "pix-banco-123",
        "pagador_nome": "Pessoa Pagadora", "pagador_cpf": "12345678909",
        "pagador_email": "pagador@exemplo.com",
    }


@respx.mock
def test_dados_incompletos_nao_registram_pix_nem_reexibem_cpf():
    from uuid import uuid4

    saque_id = uuid4()
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais").mock(
        return_value=httpx.Response(200, json={"saques": []})
    )
    chamada = respx.post(
        f"http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais/{saque_id}/pago"
    ).mock(return_value=httpx.Response(200, json={"status": "pago"}))
    resposta = _entrar("admin@exemplo.com").post(reverse("saque_fila_pago", args=[saque_id]), {
        "referencia_pix": "ref", "pagador_nome": "Pessoa Pagadora",
        "pagador_cpf": "123.456.789-09", "pagador_email": "",
    })
    assert resposta.status_code == 400
    assert not chamada.called
    assert b"12345678909" not in resposta.content


@respx.mock
def test_cpf_invalido_nao_registra_pix():
    from uuid import uuid4

    saque_id = uuid4()
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais").mock(
        return_value=httpx.Response(200, json={"saques": []})
    )
    chamada = respx.post(
        f"http://encomendas:8000/api/encomendas/clientes-fila/saques-manuais/{saque_id}/pago"
    ).mock(return_value=httpx.Response(200, json={"status": "pago"}))
    resposta = _entrar("admin@exemplo.com").post(reverse("saque_fila_pago", args=[saque_id]), {
        "referencia_pix": "ref", "pagador_nome": "Pessoa Pagadora",
        "pagador_cpf": "111.111.111-11", "pagador_email": "pagador@exemplo.com",
    })
    assert resposta.status_code == 400
    assert not chamada.called
