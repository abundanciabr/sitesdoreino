import json

import httpx
import pytest

from apps.core import notificacoes
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
    aviso["assunto"] = "assunto.inventado"
    aviso["parametros"] = {}
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [aviso], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    assert "Você tem um aviso novo" in resposta.content.decode()


PASSO = "c1fe58bf-0a82-42ce-9ad6-8dd32c343b06"


def _boas_vindas():
    aviso = _aviso()
    aviso["assunto"] = "jornada.passo"
    aviso["parametros"] = {"jornada_slug": "boas-vindas", "passo_id": PASSO, "ordem": 1}
    return aviso


def _lista(rede, *avisos):
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(
            200, json={"itens": list(avisos), "proximo_cursor": None}
        )
    )


def test_boas_vindas_mostra_o_texto_do_passo_no_idioma_de_quem_le(
    client, logado, rede, notificacoes_configurada, monkeypatch
):
    pedidos = []

    def textos(ids, idioma):
        ids = list(ids)
        pedidos.append((ids, idioma))
        return {PASSO: {"titulo": "Bem-vindo à Meshcraft Academy", "corpo": "Que bom ter você aqui."}}

    monkeypatch.setattr(notificacoes, "textos_dos_passos", textos)
    _resumo(rede)
    _lista(rede, _boas_vindas())

    corpo = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert "Bem-vindo à Meshcraft Academy" in corpo
    assert "Que bom ter você aqui." in corpo
    assert "ainda não sabe mostrar" not in corpo
    assert pedidos == [([PASSO], "pt-br")]


def test_boas_vindas_sem_texto_guardado_mostra_a_frase_padrao(
    client, logado, rede, notificacoes_configurada
):
    _resumo(rede)
    _lista(rede, _boas_vindas())

    corpo = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert "Boas-vindas" in corpo
    assert "Que bom ter você na escola." in corpo
    assert "ainda não sabe mostrar" not in corpo


def test_sugestao_mostra_o_titulo_da_ideia_com_link(
    client, logado, rede, notificacoes_configurada, monkeypatch
):
    monkeypatch.setattr(
        notificacoes,
        "ideias",
        lambda ids: {"20": {"titulo": "tutorial de chapéu / acessórios", "apagada": False}},
    )
    _resumo(rede)
    aviso = _aviso()
    aviso["parametros"]["suggestion_id"] = "20"
    _lista(rede, aviso)

    corpo = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert '<a href="/forms/sugestoes/sugestoes/20">tutorial de chapéu / acessórios</a>' in corpo


def test_aviso_de_ideia_apagada_some_e_sai_do_sino(
    client, logado, rede, notificacoes_configurada, monkeypatch
):
    monkeypatch.setattr(
        notificacoes, "ideias", lambda ids: {"20": {"titulo": "x", "apagada": True}}
    )
    _resumo(rede)
    apagada = _aviso()
    apagada["id"] = "aviso-apagado"
    apagada["parametros"]["suggestion_id"] = "20"
    _lista(rede, apagada, _boas_vindas())
    marcar = rede.post(f"{NOTIFICACOES}/marcar-lida").mock(
        return_value=httpx.Response(200, json={"ja_estava_lido": False})
    )

    corpo = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert "Sua sugestão teve uma novidade" not in corpo
    assert "Você tem 1 aviso não lido." in corpo
    assert json.loads(marcar.calls[0].request.content)["id"] == "aviso-apagado"


class _Linhas:
    def __init__(self, linhas):
        self.linhas = linhas
        self.filtro = None

    def filter(self, **filtro):
        self.filtro = filtro
        return self

    def values_list(self, *campos):
        return self.linhas


class _Modelo:
    def __init__(self, linhas):
        self.objects = _Linhas(linhas)


def test_textos_dos_passos_escolhe_o_idioma_e_cai_no_ingles(monkeypatch):
    modelo = _Modelo(
        [
            (PASSO, "pt-br", "Bem-vindo", "Oi"),
            (PASSO, "en", "Welcome", "Hi"),
            ("outro", "es", "Bienvenido", "Hola"),
        ]
    )
    monkeypatch.setattr(notificacoes, "_modelo", lambda rotulo, nome: modelo)

    assert notificacoes.textos_dos_passos([PASSO, "outro"], "pt-br") == {
        PASSO: {"titulo": "Bem-vindo", "corpo": "Oi"},
        "outro": {"titulo": "Bienvenido", "corpo": "Hola"},
    }
    assert notificacoes.textos_dos_passos([PASSO], "es")[PASSO]["titulo"] == "Welcome"


def test_ideias_le_titulo_e_apagamento(monkeypatch):
    modelo = _Modelo([(20, "tutorial de chapéu", None), (21, "sumiu", "2026-10-01")])
    monkeypatch.setattr(notificacoes, "_modelo", lambda rotulo, nome: modelo)

    assert notificacoes.ideias(["20", "21"]) == {
        "20": {"titulo": "tutorial de chapéu", "apagada": False},
        "21": {"titulo": "sumiu", "apagada": True},
    }
    assert modelo.objects.filtro == {"pk__in": ["20", "21"]}


def test_sem_a_sugestoes_e_a_mensageria_no_processo_nada_quebra():
    assert notificacoes.ideias(["20"]) == {}
    assert notificacoes.textos_dos_passos([PASSO], "pt-br") == {}


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


@pytest.mark.parametrize(
    "situacao, frase",
    [("ativa", "notificacoes.matricula_ativa"), ("inventada", "notificacoes.matricula_outra")],
)
def test_matricula_usa_a_frase_da_situacao(
    client, logado, rede, notificacoes_configurada, situacao, frase
):
    from apps.i18n.catalogo import t

    _resumo(rede)
    aviso = _aviso()
    aviso["assunto"] = "matricula.situacao-alterada"
    aviso["parametros"] = {"situacao_nova": situacao}
    _lista(rede, aviso)

    corpo = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    ).content.decode()

    assert t(frase, "pt-br") in corpo


def test_chave_por_variavel_e_chave_que_falta_nao_derrubam_a_pagina():
    from django.template import Context, Template

    modelo = Template('{% load t %}[{% t chave %}][{% t "notificacoes."|add:nome %}][{% t vazia %}]')
    texto = modelo.render(Context({"chave": "notificacoes.titulo", "nome": "nao_existe", "vazia": ""}))

    assert texto == "[Notifications][notificacoes.nao_existe][]"


def test_aviso_de_faixa_diz_a_faixa(client, logado, rede, notificacoes_configurada):
    _resumo(rede)
    aviso = _aviso()
    aviso["assunto"] = "gamificacao.conquista-concedida"
    aviso["parametros"] = {"conquista_slug": "faixa-amarela", "familia": "carreira"}
    rede.get(f"{NOTIFICACOES}/avisos").mock(
        return_value=httpx.Response(200, json={"itens": [aviso], "proximo_cursor": None})
    )

    resposta = client.get(
        caminho_mesh("pt-br", "/notificacoes"), HTTP_HOST=HOST_MESH, HTTP_COOKIE=COOKIE
    )

    corpo = resposta.content.decode()
    assert "Você chegou a uma nova faixa" in corpo
    assert "Você chegou à faixa Amarela." in corpo
    assert "medalha" not in corpo
