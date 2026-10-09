import json

import httpx
import respx
from django.urls import reverse

from tests.test_clientes_fila import ambiente, _entrar  # noqa: F401


@respx.mock
def test_cliente_escolhe_projeto_do_catalogo_recebido_pela_api():
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/acesso/pessoa-1").mock(
        return_value=httpx.Response(200, json={"slug": "paula", "pessoa_id": "pessoa-1"}))
    catalogo = {"categorias": [{"chave": "carros", "titulo": "Carros"}],
                "projetos": [{"slug": "curso-carro", "titulo": "Carro", "categoria": "carros",
                              "briefing": "Construir carro conforme referência.",
                              "referencias": [], "entregaveis": ["Arquivo Blender editável"]}]}
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/paula?pessoa_id=pessoa-1").mock(
        return_value=httpx.Response(200, json={"nome": "Paula", "slug": "paula", "pedidos": [],
                                             "catalogo_curso": catalogo}))
    resposta = _entrar("paula@exemplo.com").get(reverse("cliente_fila", args=["paula"]))
    assert resposta.status_code == 200
    assert b'value="curso-carro"' in resposta.content and b'value="carros"' in resposta.content
    assert b'name="projeto_curso"' in resposta.content and b'name="valor_reais"' in resposta.content


@respx.mock
def test_projeto_chega_com_descricao_do_cliente_e_valor_original():
    respx.get("http://encomendas:8000/api/encomendas/clientes-fila/acesso/pessoa-1").mock(
        return_value=httpx.Response(200, json={"slug": "paula", "pessoa_id": "pessoa-1"}))
    chamada = respx.post("http://encomendas:8000/api/encomendas/clientes-fila/paula/pedidos").mock(
        return_value=httpx.Response(201, json={"id": "pedido-sintetico"}))
    resposta = _entrar("paula@exemplo.com").post(reverse("criar_pedido_cliente_fila", args=["paula"]), {
        "projeto_curso": "curso-carro", "titulo": "Carro vermelho", "categoria": "carros",
        "briefing": "Carro vermelho para meu jogo.", "entregaveis": "Arquivo .blend",
        "valor_reais": "137,50", "prazo_horas": "1", "quantidade": "100",
    })
    assert resposta.status_code == 302 and chamada.called
    dados = json.loads(chamada.calls[0].request.content)
    assert dados["projeto_curso"] == "curso-carro" and dados["briefing"] == "Carro vermelho para meu jogo."
    assert dados["valor_cents"] == 13750 and dados["prazo_horas"] == 48 and dados["quantidade"] == 1
    assert dados["pessoa_id"] == "pessoa-1" and dados["administrativo"] is False
