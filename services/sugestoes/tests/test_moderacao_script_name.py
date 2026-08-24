"""Guarda de armadilhas/029 e /081, quarta temporada: a moderação sob prefixo.

A armadilha é a mesma das três anteriores e não perdoa por repetição:
**`reverse()` não lê `settings.FORCE_SCRIPT_NAME`.** Ele lê um prefixo guardado
numa variável de THREAD, que o servidor de verdade preenche
(`ASGIHandler.__call__` chama `set_script_prefix`) e que os handlers de teste do
Django **não** preenchem. Um caminho escrito à mão sai "certo" no teste e
quebra só em produção.

Aqui o estrago tem uma cor própria. As páginas do aluno quebrando viram 404
visíveis, que alguém reclama no primeiro dia. As da equipe, não: a fila de
moderação é usada por duas ou três pessoas, e um `action="/moderacao/1/status"`
sem prefixo faz o clique de "Registrar mudança" cair num 404 do Traefik — a
equipe conclui que "a Caixa não salva status", e ninguém tem como saber que o
problema é uma barra de prefixo, porque a suíte inteira está verde.

As duas pontas travadas, como nos arquivos irmãos:

1. **a borda pública resolve** — a requisição chega ao uvicorn com o prefixo na
   request line (o Traefik NÃO o remove) e a rota existe;
2. **todo link, todo `action` e todo redirecionamento carregam o prefixo.**

O prefixo é de thread e o Django **não** o limpa entre testes: sem o
`clear_script_prefix()` na saída da fixture, ele vaza para quem rodar depois.
"""

import re

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, reverse, set_script_prefix

from apps.sugestoes.models import Sugestao

PREFIXO = "/forms/sugestoes"

# Escrito à mão: é o endereço que o Traefik serve (DECISAO-EVO-01 §2). Um teste
# que o montasse com o mesmo `reverse()` do código passaria com o prefixo errado.
LINK_INTERNO = re.compile(r'(?:href|action)="(/[^"]*)"')


@pytest.fixture
def sob_prefixo(settings):
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


@pytest.fixture
def equipe_sob_prefixo(equipe, sob_prefixo):
    """A ORDEM importa: entrar primeiro, ligar o prefixo depois.

    Com o prefixo já ligado, o `follow=True` do login pediria ao client
    síncrono um caminho que, para ele, é o `path_info` inteiro — e daria 404
    dentro da fixture, num teste que não é sobre login (`LICOES.md`).
    """
    return equipe


def _pela_borda_publica(caminho: str):
    """Uma requisição como o Traefik entrega: prefixo na request line."""
    return async_to_sync(AsyncClient().get)(
        caminho, headers={"x-forwarded-proto": "https"}
    )


def test_a_borda_publica_resolve_as_rotas_de_moderacao(sob_prefixo):
    for caminho in (f"{PREFIXO}/moderacao", f"{PREFIXO}/moderacao/1"):
        resposta = _pela_borda_publica(caminho)
        # 302 (e não 404) é a prova de que a rota existe: quem recusou foi o
        # porteiro de sessão, não o resolvedor de URL.
        assert resposta.status_code == 302, f"{caminho}: {resposta.status_code}"
        assert resposta["Location"] == f"{PREFIXO}/entrar"


def test_todo_link_da_fila_leva_o_prefixo(equipe_sob_prefixo, sugestao):
    corpo = equipe_sob_prefixo.client.get("/moderacao").content.decode()
    internos = LINK_INTERNO.findall(corpo)

    assert internos, "a fila não tem link interno — o guarda não mediu nada"
    sem_prefixo = [link for link in internos if not link.startswith(f"{PREFIXO}/")]
    assert sem_prefixo == [], (
        f"links sem o prefixo público na fila: {sem_prefixo}. "
        "Todo endereço interno sai de {% url %}, nunca escrito à mão."
    )


def test_todo_link_e_action_da_pagina_de_moderacao_levam_o_prefixo(
    equipe_sob_prefixo, sugestao
):
    """Os dois `action=` desta página são o que quebra em silêncio: o
    formulário de status e o da avaliação interna."""
    corpo = equipe_sob_prefixo.client.get(f"/moderacao/{sugestao.id}").content.decode()
    internos = LINK_INTERNO.findall(corpo)

    assert f"{PREFIXO}/moderacao/{sugestao.id}/status" in internos
    assert f"{PREFIXO}/moderacao/{sugestao.id}/avaliacao" in internos
    sem_prefixo = [link for link in internos if not link.startswith(f"{PREFIXO}/")]
    assert sem_prefixo == [], f"links sem o prefixo público: {sem_prefixo}"


def test_o_redirecionamento_depois_de_mudar_o_status_leva_o_prefixo(
    equipe_sob_prefixo, sugestao
):
    """O `Location` é onde o navegador vai bater em seguida — sem prefixo, 404."""
    resposta = equipe_sob_prefixo.client.post(
        f"/moderacao/{sugestao.id}/status",
        {"status": Sugestao.Status.PLANEJADO, "nota": "vai entrar"},
    )

    assert resposta.status_code == 302, resposta.content
    assert resposta["Location"] == f"{PREFIXO}/moderacao/{sugestao.id}"


def test_o_redirecionamento_depois_de_avaliar_leva_o_prefixo(
    equipe_sob_prefixo, sugestao
):
    resposta = equipe_sob_prefixo.client.post(
        f"/moderacao/{sugestao.id}/avaliacao", {"impacto_educacional": 3}
    )

    assert resposta.status_code == 302, resposta.content
    assert resposta["Location"] == f"{PREFIXO}/moderacao/{sugestao.id}"


def test_o_link_do_cracha_no_topo_leva_o_prefixo(equipe_sob_prefixo, sugestao):
    """O caminho da equipe até a fila passa pelo topo de toda página."""
    corpo = equipe_sob_prefixo.client.get("/").content.decode()

    assert f'href="{PREFIXO}/moderacao"' in corpo


def test_o_urlconf_continua_sem_conhecer_o_prefixo(client):
    """Sem `SCRIPT_NAME`, o caminho prefixado não existe: a Caixa é dona do
    próprio endereço por configuração, não por código."""
    for caminho in ("/moderacao", "/moderacao/1", "/moderacao/1/status"):
        assert client.get(f"{PREFIXO}{caminho}").status_code == 404, caminho

    assert reverse("fila") == "/moderacao"
    assert reverse("mudar_status", args=[1]) == "/moderacao/1/status"
