"""A oportunidade leva o site e as chaves opacas do contato, para o painel cruzar com o
grupo de comparação dos agentes (admin) sem receber e-mail nem telefone."""

import hashlib

import pytest

from test_compra_da_oportunidade import (  # noqa: F401  (admin é fixture)
    SITE, admin, quiz,
)

pytestmark = pytest.mark.django_db

URL = "/api/leads/resultados/comerciais"


def _chave(site, quem):
    return hashlib.sha256(f"chave-de-contato:{site}:{quem}".encode()).hexdigest()


def test_oportunidade_leva_o_site_e_a_chave_do_email_sem_expor_o_email(client, admin):
    quiz("crivo", email="Ana@Gmail.com")
    dados = client.get(URL, **admin).json()
    oportunidade = dados["oportunidades"][0]
    assert oportunidade["site_id"] == SITE
    assert _chave(SITE, "ana@gmail.com") in oportunidade["chaves_de_contato"]
    texto = str(dados).lower()
    assert "ana@gmail.com" not in texto


def test_a_chave_de_um_site_nao_vale_para_o_outro(client, admin):
    quiz("crivo", email="ana@gmail.com", site="site-a")
    quiz("crivo", email="ana@gmail.com", site="site-b")
    chaves = {o["site_id"]: o["chaves_de_contato"] for o in client.get(URL, **admin).json()["oportunidades"]}
    assert chaves["site-a"] != chaves["site-b"]
    assert _chave("site-a", "ana@gmail.com") in chaves["site-a"]
    assert _chave("site-a", "ana@gmail.com") not in chaves["site-b"]
