import json

import httpx
import pytest

from test_sessao_no_site import COOKIE, logado
from tests.conftest import HOST_MESH, NOTIFICACOES, caminho_mesh


@pytest.fixture
def notificacoes_configurada(monkeypatch):
    monkeypatch.setenv("NOTIFICACOES_API_URL", NOTIFICACOES)
    monkeypatch.setenv("NOTIFICACOES_API_TOKEN", "token-do-par-funil-notificacoes")


def _resumo(rede, quantidade=1):
    rede.get(f"{NOTIFICACOES}/resumo").mock(
        return_value=httpx.Response(200, json={"nao_lidas": quantidade})
    )


def _aviso():
    return {
        "id": "aviso-1",
        "assunto": "sugestao.status-alterado",
        "parametros": {
            "status_anterior": "em_analise",
            "status_novo": "planejado",
            "vinculo": "autor",
            "nota": "Vamos colocar esta ideia no roadmap.",
        },
        "ator_id": None,
        "lido_em": None,
        "criado_em": "2026-09-08T10:00:00+00:00",
    }


def test_a_home_tem_uma_lista_unica_de_notificacoes(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    lista = rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(
            200, json={"itens": [_aviso()], "proximo_cursor": None}
        )
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Notificações" in corpo
    assert "Sua sugestão teve uma novidade" in corpo
    assert "O status mudou de" in corpo
    assert "em análise" in corpo
    assert "para" in corpo
    assert "planejado" in corpo
    assert "Vamos colocar esta ideia no roadmap." in corpo
    assert "Marcar como lido" in corpo
    assert lista.calls[0].request.url.params["destinatario_id"] == "idt-de-teste"
    assert lista.calls[0].request.url.params["site_id"] == "site-mesh"


def test_sugestao_implementada_avisa_e_leva_para_a_pagina_da_sugestao(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    aviso = _aviso()
    aviso["parametros"] = {
        "nota": "Feito! Criamos duas super aulas completas de chapéu.",
        "vinculo": "voto",
        "status_novo": "implementado",
        "suggestion_id": "20",
        "status_anterior": "implementado",
    }
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [aviso], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Sugestão implementada" in corpo
    assert 'href="/forms/sugestoes/sugestoes/20"' in corpo
    assert "Ver a sugestão" in corpo
    assert "O status atual é" in corpo
    assert "O status mudou de" not in corpo
    assert "Feito! Criamos duas super aulas completas de chapéu." in corpo
    assert "ainda não sabe mostrar" not in corpo


def test_subir_de_nivel_tem_cartao_proprio(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    aviso = _aviso()
    aviso["assunto"] = "gamificacao.nivel-alcancado"
    aviso["parametros"] = {"nivel": 2, "titulo_slug": "aprendiz-de-atelie"}
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [aviso], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    corpo = resposta.content.decode()
    assert "Você subiu de nível" in corpo
    assert "Agora você está no nível 2." in corpo
    assert 'href="/conquistas/"' in corpo
    assert "ainda não sabe mostrar" not in corpo


def test_assunto_desconhecido_continua_no_cartao_generico(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    aviso = _aviso()
    aviso["assunto"] = "jornada.passo"
    aviso["parametros"] = {"jornada_slug": "boas-vindas", "passo_id": "x", "ordem": 1}
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [aviso], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert "Você tem um aviso novo" in resposta.content.decode()


def test_lista_vazia_e_diferente_de_falha(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede, 0)
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert resposta.status_code == 200
    assert "Você ainda não tem avisos." in resposta.content.decode()
    assert "temporariamente indisponíveis" not in resposta.content.decode()


def test_falha_da_caixa_aparece_na_lista(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    rede.get(f"{NOTIFICACOES}/avisos").mock(return_value=httpx.Response(503))

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert resposta.status_code == 503
    assert "Tente novamente em alguns instantes" in resposta.content.decode()


def test_marcar_um_aviso_volta_para_a_lista(
    client, logado, rede, notificacoes_configurada
):
    rota = rede.post(f"{NOTIFICACOES}/marcar-lida").mock(
        return_value=httpx.Response(200, json={"ja_estava_lido": False})
    )

    resposta = client.post(
        caminho_mesh("pt-br", "/notificacoes/aviso-1/lida"),
        HTTP_HOST=HOST_MESH,
        HTTP_COOKIE=COOKIE,
    )

    assert resposta.status_code == 302
    assert resposta["Location"] == "/pt-br/notificacoes"
    assert rota.calls[0].request.content == (
        b'{"destinatario_id":"idt-de-teste","site_id":"site-mesh","id":"aviso-1"}'
    )


def test_marcar_todos_os_avisos_volta_para_a_lista(
    client, logado, rede, notificacoes_configurada
):
    rota = rede.post(f"{NOTIFICACOES}/marcar-lidas").mock(
        return_value=httpx.Response(200, json={"marcados": 2})
    )

    resposta = client.post(
        caminho_mesh("pt-br", "/notificacoes/marcar-todas"),
        HTTP_HOST=HOST_MESH,
        HTTP_COOKIE=COOKIE,
    )

    assert resposta.status_code == 302
    assert resposta["Location"] == "/pt-br/notificacoes"
    assert json.loads(rota.calls[0].request.content)["site_id"] == "site-mesh"


def test_visitante_e_levado_para_entrar_antes_de_ver_notificacoes(client, rede):
    resposta = client.get(caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH)

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/pt-br/login?next=%2Fpt-br%2Fnotificacoes")
