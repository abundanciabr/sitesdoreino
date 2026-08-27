"""Teste-guarda: o painel do dono, servido vivo e atrás da porta.

**O que este arquivo existe para impedir**, e por que os testes óbvios não
impediriam:

1. **Um painel que abre e não mostra nada.** É a falha mais provável aqui e a
   menos visível: o HTML chega inteiro (200), e o `<script>` embutido é
   bloqueado pelo CSP da porta, ou um `registros/*.js` dá 404. A tela fica em
   branco, sem erro nenhum de servidor — que é exatamente a forma de
   `armadilhas/083`. Um teste que só afirmasse `status_code == 200` na página
   ficaria VERDE com o painel quebrado. Por isso a prova aqui varre o HTML
   servido atrás de tudo que ele pede e busca **cada arquivo**, e confere o
   hash do CSP contra o script real.

2. **Um painel que vira um fork.** Se algum dia alguém "melhorar" a cópia
   servida, passam a existir dois painéis divergentes — a duplicação que o
   `CLAUDE.md` proíbe. `test_e_o_arquivo_do_repositorio_byte_a_byte` compara
   byte a byte.

3. **Um painel exposto.** Ele é a operação inteira do projeto numa tela. A
   porta o protege porque ele NÃO está em `CAMINHOS_ISENTOS`; isso é medido
   aqui de fora, e não por leitura do código.

A rede é dublada com `respx`, como em `test_inv_porta_fail_closed.py`.
"""

import base64
import hashlib
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.conf import settings
from django.test import Client

from apps.core.painel import diretorio_do_painel

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

# A pasta viva do repositório — a MESMA que o mantenedor abre no PC. Derivada
# deste arquivo, e não de `diretorio_do_painel()`: um teste que perguntasse ao
# código onde está a pasta passaria mesmo se o código respondesse a errada.
PAINEL_NO_REPO = Path(__file__).resolve().parents[3] / "painel"

# Um script embutido é `<script>` SEM `src=`. Escrito de novo aqui, de
# propósito: se o teste importasse o padrão do código, os dois errariam juntos.
ILHA = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


@pytest.fixture(autouse=True)
def env_da_porta(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    """Um cliente já reconhecido como o dono — a porta deixa passar."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Dono",
                "email": DONO,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def test_debug_esta_desligado():
    """Sanidade do cenário (lição de `armadilhas/083`).

    Com `DEBUG=True` o Django serve estático sozinho e o resto deste arquivo
    mediria um mundo que não existe em produção.
    """
    assert settings.DEBUG is False


def test_a_pasta_do_painel_foi_encontrada():
    assert (
        diretorio_do_painel() is not None
    ), "sem a pasta do painel os testes abaixo não provariam nada"


@respx.mock
def test_e_o_arquivo_do_repositorio_byte_a_byte():
    """A célula SERVE o painel; não reimplementa nem edita.

    Byte a byte de propósito: uma comparação de "contém o título" aceitaria uma
    cópia divergente, e cópia divergente é a duplicação que a lei proíbe.
    """
    resposta = _dentro().get("/painel/")
    assert resposta.status_code == 200, resposta.content[:400]
    assert resposta.content == (PAINEL_NO_REPO / "painel.html").read_bytes()


@respx.mock
def test_todo_arquivo_que_a_pagina_pede_responde_200():
    """A prova que pega o painel em branco.

    Varre o HTML servido atrás de `src=`/`href=` relativos e busca cada um pelo
    urlconf real. Assim, o dia em que o painel carregar um arquivo novo, ele
    entra nesta prova sem ninguém lembrar de atualizar o teste.
    """
    cliente = _dentro()
    html = cliente.get("/painel/").content.decode("utf-8")

    pedidos = {
        alvo
        for alvo in re.findall(r'(?:src|href)="([^"]+)"', html)
        if not alvo.startswith(("http://", "https://", "//", "#", "data:", "mailto:"))
    }
    assert pedidos, "o HTML não pede arquivo nenhum — a varredura está cega"

    for alvo in sorted(pedidos):
        resposta = cliente.get(f"/painel/{alvo}")
        assert resposta.status_code == 200, f"{alvo} respondeu {resposta.status_code}"


@respx.mock
def test_todo_registro_do_livro_e_alcancavel():
    """O manifesto lista N registros; os N precisam responder.

    A página se recusa a renderizar se `REGISTROS.length != MANIFESTO.length`
    (fail-closed do próprio painel). Um registro que não é servido derruba o
    painel inteiro — não some silenciosamente.
    """
    cliente = _dentro()
    registros = sorted(p.name for p in (PAINEL_NO_REPO / "registros").glob("*.js"))
    assert len(registros) > 10, "o livro está pequeno demais para esta prova valer"

    for nome in registros:
        resposta = cliente.get(f"/painel/registros/{nome}")
        assert resposta.status_code == 200, f"registro {nome} não é servido"


@respx.mock
def test_o_csp_libera_exatamente_o_script_embutido_do_painel():
    """O hash do CSP é calculado do arquivo REAL, e confere.

    Se alguém trocar o cálculo por um hash cravado em string, o painel quebra
    na primeira vez que o HTML mudar — e só em produção. Aqui o hash esperado é
    recalculado do arquivo, do lado do teste.
    """
    csp = _dentro().get("/painel/")["Content-Security-Policy"]

    ilhas = ILHA.findall((PAINEL_NO_REPO / "painel.html").read_bytes())
    assert ilhas, "o painel deixou de ter script embutido — reveja esta guarda"

    for corpo in ilhas:
        esperado = base64.b64encode(hashlib.sha256(corpo).digest()).decode()
        assert f"'sha256-{esperado}'" in csp, "o CSP não libera a ilha do painel"


@respx.mock
def test_csp_nao_afrouxa_para_unsafe_inline():
    """O conserto tentador — e proibido — para o problema acima."""
    csp = _dentro().get("/painel/")["Content-Security-Policy"]
    script_src = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src


@respx.mock
def test_o_painel_nunca_e_guardado_em_cache():
    """O atrito que originou este trabalho: o mantenedor vendo painel velho."""
    cliente = _dentro()
    assert cliente.get("/painel/")["Cache-Control"] == "no-store"
    assert cliente.get("/painel/manifesto.js")["Cache-Control"] == "no-store"


# ------------------------------------------------------------------- a porta


def test_sem_sessao_o_painel_nao_abre():
    """Ele não está em `CAMINHOS_ISENTOS`, e isso é medido de fora."""
    for caminho in ("/painel/", "/painel/manifesto.js", "/painel/registros/x.js"):
        resposta = Client().get(caminho)
        assert resposta.status_code == 302, caminho
        assert "/entrar/google" in resposta["Location"]


@respx.mock
def test_conta_fora_da_lista_nao_ve_o_painel():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-9",
                "nome_exibido": "Estranho",
                "email": "estranho@exemplo.com",
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    assert cliente.get("/painel/").status_code == 404


# -------------------------------------------------- o que a rota NÃO entrega


@respx.mock
def test_a_rota_so_entrega_html_js_e_css():
    """`LEIA-ME.md` não é para a web; `.js` da pasta é."""
    cliente = _dentro()
    assert cliente.get("/painel/LEIA-ME.md").status_code == 404
    assert cliente.get("/painel/logica.js").status_code == 200


@respx.mock
def test_travessia_de_diretorio_nao_sai_da_pasta():
    """O `safe_join` do Django devolve 400 (`SuspiciousFileOperation`)."""
    resposta = _dentro().get("/painel/../config/settings.py")
    assert resposta.status_code in (400, 404), resposta.status_code
