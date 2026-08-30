"""O estilo da área administrativa CHEGA ao navegador (30/08/2026).

O buraco que estes guardas fecham foi medido em produção, não imaginado: a
porta mandava `style-src 'self'` em toda resposta, e o estilo desta área mora
EMBUTIDO no `<head>` (`admin/base.html` explica por quê). `style-src 'self'`
proíbe estilo embutido — então toda tela desta área chegava **sem estilo
nenhum** ao navegador do dono. Só `/admin/painel/` e a aba "Os robôs"
escapavam, porque mandam política própria.

**Por que ninguém viu:** o test client do Django não aplica CSP, e o `curl`
baixa o HTML com o `<style>` lá dentro sem nunca renderizá-lo. Os dois davam
verde. A prova veio de um Chrome de verdade batendo em
`https://meshcraft.top/docs/`, que recusou em voz alta e ainda disse qual hash
faltava — o MESMO que o teste abaixo calcula.

O que estes testes protegem, agora que o conserto existe:

1. **A política carrega o hash do estilo daquela resposta** — e o hash é
   calculado do jeito que o navegador calcula (os bytes ENTRE as tags).
2. **`'unsafe-inline'` nunca entra** para consertar isso pelo caminho fácil:
   ele liberaria qualquer estilo injetado, o oposto do que o hash faz.
3. **Resposta sem corpo continua com a política de antes** — um 302 não tem
   estilo para liberar, e não deve ganhar hash nenhum.
4. **Quem manda a própria política continua mandando** (`setdefault`).
"""

import base64
import hashlib
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

ESTILO = re.compile(rb"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _hashes_do_navegador(corpo: bytes) -> set[str]:
    """Os hashes que o NAVEGADOR exigiria desta resposta.

    Calculado aqui de forma independente da porta — se a porta mudar o jeito de
    hashear, este teste discorda dela, que é o ponto. A fórmula é a do padrão:
    sha256 dos bytes entre `<style ...>` e `</style>`, em base64.
    """
    return {
        "'sha256-" + base64.b64encode(hashlib.sha256(m).digest()).decode() + "'"
        for m in ESTILO.findall(corpo)
    }


def _style_src(csp: str) -> str:
    for diretiva in csp.split(";"):
        if diretiva.strip().startswith("style-src"):
            return diretiva.strip()
    raise AssertionError(f"a política não tem `style-src`: {csp}")


@respx.mock
def test_a_politica_libera_exatamente_o_estilo_daquela_pagina():
    resposta = _dentro().get(reverse("visao_geral"))
    assert resposta.status_code == 200
    exigidos = _hashes_do_navegador(resposta.content)
    assert exigidos, "a página deveria ter estilo embutido — sem ele o teste é vazio"
    style_src = _style_src(resposta["Content-Security-Policy"])
    faltando = [h for h in exigidos if h not in style_src]
    assert not faltando, (
        f"o navegador BLOQUEARIA o estilo desta página: falta {faltando} em "
        f"{style_src!r}. É o defeito de 30/08/2026 de volta."
    )


@respx.mock
@pytest.mark.parametrize(
    "rota", ["visao_geral", "escola", "caixa", "documentos_admin", "mapa_do_site"]
)
def test_toda_tela_da_area_chega_com_o_estilo_liberado(rota):
    """Uma tela por família — o defeito era da porta, então valia para todas."""
    resposta = _dentro().get(reverse(rota))
    assert resposta.status_code == 200
    style_src = _style_src(resposta["Content-Security-Policy"])
    for h in _hashes_do_navegador(resposta.content):
        assert h in style_src, f"{rota}: o navegador bloquearia o estilo"


@respx.mock
def test_a_politica_nunca_afrouxa_para_unsafe_inline():
    """O conserto fácil que não se usa: liberaria QUALQUER estilo injetado."""
    resposta = _dentro().get(reverse("visao_geral"))
    assert "'unsafe-inline'" not in _style_src(resposta["Content-Security-Policy"])


@respx.mock
def test_resposta_sem_corpo_mantem_a_politica_de_sempre():
    """Um 302 não tem estilo para liberar — e não ganha hash nenhum."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    resposta = Client().get(reverse("visao_geral"))
    assert resposta.status_code == 302
    assert _style_src(resposta["Content-Security-Policy"]) == "style-src 'self'"


@respx.mock
def test_quem_manda_a_propria_politica_continua_mandando():
    """O painel declara CSP própria (com o hash do script dele). A porta não
    pode sobrescrevê-la — `setdefault`, nunca atribuição."""
    resposta = _dentro().get(reverse("painel"))
    csp = resposta["Content-Security-Policy"]
    assert "sha256-" in _style_src(csp) or "'unsafe-inline'" in _style_src(csp)
    assert "fonts.googleapis.com" in csp, "esta é a política do painel, não a da porta"
