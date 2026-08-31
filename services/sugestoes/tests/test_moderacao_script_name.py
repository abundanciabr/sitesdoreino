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


# As três telas de `/moderacao` foram aposentadas em 30/08/2026 (TAR-023), e com
# elas saíram os quatro guardas que mediam os LINKS e os `action=` delas: não há
# mais página desta célula com formulário de moderação dentro, e um guarda que
# varresse uma resposta de 301 estaria varrendo o vazio. O que eles protegiam —
# "todo `action=` carrega o prefixo público" — mudou de casa junto com as telas,
# e do lado do Admin não existe: `/admin` não roda sob `FORCE_SCRIPT_NAME` de
# caminho aninhado do mesmo jeito, e a célula tem os próprios guardas
# (`services/admin/tests/test_healthz_script_name.py`).
#
# O que SOBRA aqui é o que continua sendo desta célula sob prefixo, e é o que os
# três guardas abaixo medem: a borda pública resolve os endereços aposentados, o
# destino do redirecionamento é ABSOLUTO (e por isso não leva o prefixo — ele é
# de outra superfície), e o urlconf continua sem conhecer o prefixo.


def test_o_destino_do_redirecionamento_e_absoluto_e_NAO_leva_o_prefixo(
    equipe_sob_prefixo, sugestao
):
    """A exceção que confirma a regra deste arquivo, e ela é deliberada.

    Todo endereço desta célula sai de `reverse()` justamente para carregar o
    prefixo público. O destino da mudança de casa, não: `/admin/caixa/` não
    pertence a esta célula, e nenhum `reverse()` daqui saberia montá-lo — as
    duas superfícies vivem sob o MESMO host, roteadas pelo mesmo Traefik, então
    o caminho absoluto basta (`apps/core/mudou_de_casa.py`).

    Sem este guarda, alguém "consertaria" o destino um dia pondo o prefixo nele
    por analogia com o resto do arquivo — e mandaria a equipe para
    `/forms/sugestoes/admin/caixa/`, que é um 404 do Traefik.
    """
    resposta = equipe_sob_prefixo.client.get(f"/moderacao/{sugestao.id}")

    assert resposta.status_code == 301, resposta.content
    assert resposta["Location"] == "/admin/caixa/"


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
