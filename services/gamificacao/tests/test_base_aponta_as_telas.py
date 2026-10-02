"""A Base de `/conquistas` leva o aluno às telas que já existem.

O DEFEITO QUE ESTE ARQUIVO FECHA (27/09/2026)
---------------------------------------------
Marcos, Forja, Medalhas e Contribuições já estavam no ar, e a Base não
apontava para nenhuma delas: quem não digitasse o endereço não as achava. Pior,
ela dizia que "as medalhas e a trilha de marcos chegam nos próximos passos",
prometendo como futuro o que já estava pronto.

O QUE ESTE ARQUIVO PROTEGE
--------------------------
1. **Quem entrou vê os quatro caminhos**, cada um saído de `{% url %}`, que é
   quem carrega o prefixo público `/conquistas`.
2. **A promessa velha não volta.** O corpo é comparado com os espaços
   normalizados, porque a frase do template ocupa várias linhas e um `in` cru
   deixaria passar a frase de volta sem erro.
3. **Nenhum link leva a 403 ou 404.** Cada endereço da faixa é seguido por quem
   o vê, e a resposta tem de ser a tela.
4. **Visitante continua com o convite para entrar**, sem a faixa de quem entrou.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

SITE = "site-de-teste"
ALGUEM = "pes-base-aponta"

TELAS = ("marcos", "forja", "medalhas", "contribuicoes")


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
def test_quem_entrou_ve_os_quatro_caminhos(client, com_site, logado):
    corpo = _corpo(client.get(reverse("base")))
    faixa = _faixa_das_telas(corpo)

    for nome in TELAS:
        assert f'href="{reverse(nome)}"' in faixa, f"falta o link para {nome}"
    for rotulo in ("Marcos reais", "Forja", "Medalhas", "Contribuições"):
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
