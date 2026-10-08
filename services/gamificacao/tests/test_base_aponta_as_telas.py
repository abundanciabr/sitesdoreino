"""A Base de `/conquistas` leva o aluno às medalhas que seguem ativas."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

SITE = "site-de-teste"
ALGUEM = "pes-base-aponta"

TELAS = ("medalhas",)


@pytest.fixture
def com_site(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)


@pytest.fixture
def logado(monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ALGUEM)


@pytest.fixture
def visitante(monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)


def _corpo(resposta) -> str:
    return re.sub(r"\s+", " ", resposta.content.decode())


def _faixa_das_telas(corpo: str) -> str:
    achado = re.search(
        r'<nav class="aviso" aria-labelledby="telas-das-conquistas">.*?</nav>', corpo
    )
    assert achado, "a Base não tem a faixa que aponta para as telas"
    return achado.group(0)


@pytest.mark.django_db
def test_quem_entrou_ve_o_caminho_das_medalhas(client, com_site, logado):
    corpo = _corpo(client.get(reverse("base")))
    faixa = _faixa_das_telas(corpo)

    for nome in TELAS:
        assert f'href="{reverse(nome)}"' in faixa, f"falta o link para {nome}"
    for rotulo in ("Medalhas",):
        assert rotulo in faixa, f"falta o nome da tela {rotulo}"


@pytest.mark.django_db
def test_a_promessa_velha_saiu(client, com_site, logado):
    corpo = _corpo(client.get(reverse("base")))

    assert "Por enquanto ela mostra só o seu degrau" not in corpo
    assert "chegam nos próximos passos" not in corpo
    assert "Esta página está começando" not in corpo


@pytest.mark.django_db
def test_nenhum_link_da_faixa_leva_a_403_ou_404(client, com_site, logado):
    faixa = _faixa_das_telas(_corpo(client.get(reverse("base"))))
    enderecos = re.findall(r'href="([^"]+)"', faixa)

    assert len(enderecos) == len(TELAS)
    for endereco in enderecos:
        resposta = client.get(endereco)
        assert resposta.status_code == 200, f"{endereco} deu {resposta.status_code}"


@pytest.mark.django_db
def test_visitante_segue_com_o_convite_e_sem_a_faixa(client, com_site, visitante):
    resposta = client.get(reverse("base"))

    assert resposta.status_code == 200
    corpo = _corpo(resposta)
    assert "Entrar na escola" in corpo
    assert 'aria-labelledby="telas-das-conquistas"' not in corpo
