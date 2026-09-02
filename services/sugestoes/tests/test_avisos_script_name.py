"""Guarda de armadilhas/081, quarta temporada: o sininho sob prefixo.

`reverse()` **não lê** `settings.FORCE_SCRIPT_NAME`. Ele lê um prefixo guardado
numa variável de THREAD que o servidor de verdade preenche
(`ASGIHandler.__call__` chama `set_script_prefix`) e que os handlers de teste do
Django **não** preenchem. O EVO-12a pagou isso na porta, o EVO-12b nas rotas de
participação, e as duas rotas novas do EVO-21 têm exatamente o mesmo problema:
um `action="/avisos/3/lido"` escrito à mão renderiza sem prefixo, o navegador
pede `meshcraft.top/avisos/3/lido`, o Traefik não conhece essa rota — e o botão
"marcar como lido" vira um 404 que passa em toda a suíte.

As duas pontas, como nos arquivos irmãos:

1. **a borda pública resolve** — a requisição chega ao uvicorn com o prefixo na
   request line (o Traefik NÃO o remove) e a rota existe;
2. **todo link e todo redirecionamento carregam o prefixo** — inclusive o
   `Location` da volta depois de marcar como lido, que é para onde o navegador
   bate em seguida.

O prefixo é de thread e o Django **não** o limpa entre testes: sem o
`clear_script_prefix()` na saída da fixture, ele vaza para quem rodar depois.
"""

import re

import pytest

from apps.core.rodape import enderecos_de_outras_celulas
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

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
    """A ORDEM importa: entrar primeiro, ligar o prefixo depois — o `follow=True`
    do login pediria ao client síncrono um caminho que, para ele, já é o
    `path_info` inteiro (`LICOES.md`)."""
    return dentro


def _pela_borda_publica(caminho: str):
    """Uma requisição como o Traefik entrega: prefixo na request line."""
    return async_to_sync(AsyncClient().get)(
        caminho, headers={"x-forwarded-proto": "https"}
    )


def test_a_borda_publica_resolve_as_rotas_do_sininho(sob_prefixo):
    for caminho in (f"{PREFIXO}/avisos", f"{PREFIXO}/avisos/1/lido"):
        resposta = _pela_borda_publica(caminho)
        # 302 (ou 405, no POST-only) e não 404: quem recusou foi o porteiro de
        # sessão, não o resolvedor de URL — é a prova de que a rota existe.
        assert resposta.status_code in (302, 405), f"{caminho}: {resposta.status_code}"


def test_todo_link_da_pagina_de_avisos_leva_o_prefixo(dentro_sob_prefixo, aviso):
    corpo = dentro_sob_prefixo.client.get("/avisos").content.decode()
    internos = LINK_INTERNO.findall(corpo)

    assert internos, "a página de avisos não tem link interno — nada foi medido"
    de_fora = enderecos_de_outras_celulas()
    sem_prefixo = [
        link
        for link in internos
        if not link.startswith(f"{PREFIXO}/") and link not in de_fora
    ]
    assert sem_prefixo == [], (
        f"links sem o prefixo público na página de avisos: {sem_prefixo}. "
        "Todo endereço interno sai de {% url %}, nunca escrito à mão."
    )


def test_o_link_do_sino_na_moldura_leva_o_prefixo(dentro_sob_prefixo, sugestao):
    """O sino aparece em TODA página (context processor): se ele saísse sem
    prefixo, quebraria em todas de uma vez."""
    corpo = dentro_sob_prefixo.client.get("/").content.decode()

    assert f'href="{PREFIXO}/avisos"' in corpo, corpo[:400]


def test_o_redirecionamento_depois_de_marcar_como_lido_leva_o_prefixo(
    dentro_sob_prefixo, aviso
):
    resposta = dentro_sob_prefixo.client.post(f"/avisos/{aviso.id}/lido")

    assert resposta.status_code == 302
    assert resposta["Location"] == f"{PREFIXO}/avisos"


def test_o_urlconf_continua_sem_conhecer_o_prefixo(client):
    """Sem `SCRIPT_NAME`, o caminho prefixado não existe: a Caixa é dona do
    próprio endereço por configuração, não por código."""
    for caminho in ("/avisos", "/avisos/1/lido"):
        assert client.get(f"{PREFIXO}{caminho}").status_code == 404, caminho

    assert reverse("avisos") == "/avisos"
    assert reverse("marcar_aviso_lido", args=[7]) == "/avisos/7/lido"
