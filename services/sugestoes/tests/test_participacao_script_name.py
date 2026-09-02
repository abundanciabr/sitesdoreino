"""Guarda de armadilhas/029 e /081, terceira temporada: a participação sob prefixo.

O EVO-12a pagou esta armadilha na porta de entrada e a deixou escrita:
**`reverse()` não lê `settings.FORCE_SCRIPT_NAME`.** Ele lê um prefixo guardado
numa variável de THREAD, que o servidor de verdade preenche
(`ASGIHandler.__call__` chama `set_script_prefix`) e que os handlers de teste do
Django **não** preenchem. O resultado é uma mentira simétrica: em teste o
`reverse()` sai sem prefixo com a produção certa; e um caminho cravado à mão
sai "certo" no teste e quebra só em produção.

As rotas novas do EVO-12b têm exatamente o mesmo problema, com um agravante
diferente do OAuth: aqui não há Google para recusar nada. Um `href="/sugestoes/nova"`
escrito à mão renderiza sem prefixo, o navegador pede `meshcraft.top/sugestoes/nova`,
o Traefik não conhece essa rota — e a Caixa vira uma pilha de 404 que passa em
toda a suíte. Daí este arquivo travar as DUAS pontas:

1. **a borda pública resolve** — a requisição chega ao uvicorn com o prefixo na
   request line (o Traefik NÃO o remove) e a rota existe;
2. **todo link e todo redirecionamento carregam o prefixo** — nada de caminho
   escrito à mão em template nem em `HttpResponseRedirect`.

O prefixo é de thread e o Django **não** o limpa entre testes: sem o
`clear_script_prefix()` na saída da fixture, ele vaza para quem rodar depois.
"""

import re

import pytest

from apps.core.rodape import enderecos_de_outras_celulas
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

# Sem `django_db` no módulo, de propósito: os guardas da borda pública usam
# `AsyncClient` e não tocam o banco (o anônimo é recusado antes de qualquer
# consulta). Quem precisa de banco recebe a marca pelas fixtures, que já
# dependem de `db` — é o mesmo desenho do `test_entrada_script_name.py`.
PREFIXO = "/forms/sugestoes"

# Escrito à mão: é o endereço que o Traefik serve (DECISAO-EVO-01 §2). Um teste
# que o montasse com o mesmo `reverse()` do código passaria com o prefixo errado.
LINK_INTERNO = re.compile(r'(?:href|action)="(/[^"]*)"')


@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS mais o que o servidor faz e o client de teste não faz."""
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


@pytest.fixture
def dentro_sob_prefixo(dentro, sob_prefixo):
    """A ORDEM importa: entrar primeiro, ligar o prefixo depois.

    Com o prefixo já ligado, o `follow=True` do login pediria ao client
    síncrono um caminho que, para ele, é o `path_info` inteiro — e daria 404
    dentro da fixture, num teste que não é sobre login (`LICOES.md`: a
    aritmética de `path`/`path_info` do client síncrono é a inversa da do
    `ASGIRequest`).
    """
    return dentro


def _pela_borda_publica(caminho: str):
    """Uma requisição como o Traefik entrega: prefixo na request line."""
    return async_to_sync(AsyncClient().get)(
        caminho, headers={"x-forwarded-proto": "https"}
    )


def test_a_borda_publica_resolve_o_quadro_e_devolve_o_anonimo_a_porta(sob_prefixo):
    """Uma asserção, duas provas: a rota existe sob o prefixo E o `reverse()`
    do porteiro devolve um endereço que o Traefik sabe servir."""
    resposta = _pela_borda_publica(f"{PREFIXO}/")

    assert resposta.asgi_request.path == f"{PREFIXO}/"
    assert resposta.asgi_request.path_info == "/"
    assert resposta.status_code == 302, resposta.status_code
    assert resposta["Location"] == f"{PREFIXO}/entrar"


def test_a_borda_publica_resolve_as_rotas_de_sugestao(sob_prefixo):
    for caminho in (f"{PREFIXO}/sugestoes/nova", f"{PREFIXO}/sugestoes/1"):
        resposta = _pela_borda_publica(caminho)
        # 302 (e não 404) é a prova de que a rota existe: quem recusou foi o
        # porteiro de sessão, não o resolvedor de URL.
        assert resposta.status_code == 302, f"{caminho}: {resposta.status_code}"


def test_todo_link_do_quadro_leva_o_prefixo(dentro_sob_prefixo, sugestao):
    corpo = dentro_sob_prefixo.client.get("/").content.decode()
    internos = LINK_INTERNO.findall(corpo)

    assert internos, "o quadro não tem nenhum link interno — o guarda não mediu nada"
    de_fora = enderecos_de_outras_celulas()
    sem_prefixo = [
        link
        for link in internos
        if not link.startswith(f"{PREFIXO}/") and link not in de_fora
    ]
    assert sem_prefixo == [], (
        f"links sem o prefixo público no quadro: {sem_prefixo}. "
        "Todo endereço interno sai de {% url %}, nunca escrito à mão."
    )


def test_todo_link_da_pagina_da_sugestao_leva_o_prefixo(dentro_sob_prefixo, sugestao):
    corpo = dentro_sob_prefixo.client.get(f"/sugestoes/{sugestao.id}").content.decode()

    de_fora = enderecos_de_outras_celulas()
    sem_prefixo = [
        link
        for link in LINK_INTERNO.findall(corpo)
        if not link.startswith(f"{PREFIXO}/") and link not in de_fora
    ]
    assert sem_prefixo == [], f"links sem o prefixo público: {sem_prefixo}"


def test_todo_link_do_formulario_de_sugerir_leva_o_prefixo(
    dentro_sob_prefixo, categoria
):
    corpo = dentro_sob_prefixo.client.get("/sugestoes/nova").content.decode()

    de_fora = enderecos_de_outras_celulas()
    sem_prefixo = [
        link
        for link in LINK_INTERNO.findall(corpo)
        if not link.startswith(f"{PREFIXO}/") and link not in de_fora
    ]
    assert sem_prefixo == [], f"links sem o prefixo público: {sem_prefixo}"


def test_o_redirecionamento_depois_de_votar_leva_o_prefixo(
    dentro_sob_prefixo, sugestao
):
    """O `Location` é onde o navegador vai bater em seguida — sem prefixo, 404."""
    cliente = dentro_sob_prefixo.client

    para_a_pagina = cliente.post(f"/sugestoes/{sugestao.id}/votar")
    para_o_quadro = cliente.post(f"/sugestoes/{sugestao.id}/desvotar", {"de": "quadro"})

    assert para_a_pagina["Location"] == f"{PREFIXO}/sugestoes/{sugestao.id}"
    assert para_o_quadro["Location"] == f"{PREFIXO}/"


def test_o_redirecionamento_depois_de_publicar_leva_o_prefixo(
    dentro_sob_prefixo, categoria
):
    resposta = dentro_sob_prefixo.client.post(
        "/sugestoes/nova",
        {
            "titulo": "Publicada sob prefixo",
            "problema": "Doi assim.",
            "categoria": "curso",
            "publicar": "1",
        },
    )

    assert resposta.status_code == 302, resposta.content
    assert resposta["Location"].startswith(f"{PREFIXO}/sugestoes/")


def test_o_urlconf_continua_sem_conhecer_o_prefixo(client):
    """Sem `SCRIPT_NAME`, o caminho prefixado não existe: a Caixa é dona do
    próprio endereço por configuração, não por código."""
    for caminho in ("/", "/sugestoes/nova", "/sugestoes/1", "/sugestoes/1/votar"):
        assert client.get(f"{PREFIXO}{caminho}").status_code == 404, caminho

    # E o `reverse()` sem prefixo continua devolvendo o caminho nu.
    assert reverse("quadro") == "/"
    assert reverse("nova_sugestao") == "/sugestoes/nova"
