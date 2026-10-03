"""Q30/Q31/Q33: o funil leva ao checkout os 7 parâmetros internos do quiz, a
tentativa (qa) e o quiz (qz), pelo mesmo caminho das UTMs (link do checkout)."""

from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_pagina_de_oferta import (  # noqa: F401
    CAMINHO,
    HOST_A,
    SECOES_CHEIAS,
    SLUG,
    pagina,
    publicar,
)

QA = "7b0c2f9e-3f0a-4c1e-9d52-0a1b2c3d4e5f"
QUIZ = {
    "v": "B2",
    "fmt": "text",
    "seg": "empreendedor",
    "src": "tiktok",
    "med": "video",
    "cpg": "maio",
    "ctv": "anuncio3",
}
UTMS = {
    "utm_source": "tiktok",
    "utm_medium": "video",
    "utm_campaign": "maio",
    "utm_content": "anuncio3",
    "utm_term": "roblox",
}


def _href(resp):
    html = resp.content.decode()
    inicio = html.index(f'href="/checkout/{SLUG}/?') + len('href="')
    return html[inicio : html.index('"', inicio)].replace("&amp;", "&")


def test_link_do_checkout_leva_os_doze_parametros_mais_qa_e_qz(client, rede):
    publicar(rede, pagina(SECOES_CHEIAS))
    entrada = {**UTMS, **QUIZ, "qa": QA, "qz": "low-ticket"}
    resp = client.get(CAMINHO, entrada, HTTP_HOST=HOST_A)
    assert resp.status_code == 200
    url = urlsplit(_href(resp))
    assert url.path == f"/checkout/{SLUG}/"
    assert {k: v[0] for k, v in parse_qs(url.query).items()} == entrada


def test_valor_fora_do_padrao_nao_vai_ao_checkout(client, rede):
    publicar(rede, pagina(SECOES_CHEIAS))
    resp = client.get(
        CAMINHO,
        {"v": "B2", "qa": "<script>", "cpg": "a" * 101, "outro": "x"},
        HTTP_HOST=HOST_A,
    )
    query = parse_qs(urlsplit(_href(resp)).query)
    assert query == {"v": ["B2"]}


def test_sem_parametros_do_quiz_o_link_nao_muda(client, rede):
    publicar(rede, pagina(SECOES_CHEIAS))
    resp = client.get(CAMINHO, {"utm_source": "ig"}, HTTP_HOST=HOST_A)
    assert f'href="/checkout/{SLUG}/?utm_source=ig"'.encode() in resp.content
