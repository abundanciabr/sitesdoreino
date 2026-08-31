"""A Base em `/conquistas`: a primeira tela que um aluno desta célula abre.

O QUE ESTE ARQUIVO PROTEGE, e por que cada coisa
-------------------------------------------------
1. **Visitante nunca leva erro.** A tela é pública e convida a entrar. Um 403
   diria "isto não é para você" a quem ainda vai se matricular, e um 500 seria
   pior: a página existiria e pareceria quebrada.
2. **O perfil nasce ao ser olhado, e nasce UMA vez.** Duas visitas não criam
   dois perfis, e quem garante isso é o `Unique(pessoa, site_id)` do banco.
3. **Sem `SITE_ID` a tela não quebra.** É a falha ABERTA que o contrato exige da
   porta de máquina, e vale igual aqui: página sem selo, nunca página quebrada.
   Este é o caso que mais se esconde, então ele tem teste próprio.
4. **O CSS responde sob o prefixo.** `armadilhas/083` e `/102`: com DEBUG=0 o
   Django não serve estático, e `{% static %}` apontaria para o `funil`. Este
   teste é o que faz a diferença entre "funciona em dev" e "funciona".
5. **A escada não mente.** Nível, título e a fração da barra saem de
   `NivelDefinicao` ATIVA, e a economia inteira nasce desligada.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.gamificacao.models import NivelDefinicao, PerfilJogador, Pessoa

SITE = "site-de-teste"
ALGUEM = "pes-abc"


@pytest.fixture
def com_site(monkeypatch):
    """`SITE_ID` presente, que é o estado normal em produção."""
    monkeypatch.setenv("SITE_ID", SITE)


@pytest.fixture
def logado(monkeypatch):
    """Alguém entrou. O reconhecimento é da `identidade`, e aqui ele é dublê."""
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ALGUEM)


@pytest.fixture
def visitante(monkeypatch):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)


def _degraus(*pares: tuple[int, int, str]) -> None:
    for nivel, xp, titulo in pares:
        NivelDefinicao.objects.create(
            nivel=nivel, site_id=SITE, xp_necessario=xp, titulo=titulo, ativa=True
        )


# ------------------------------------------------------------------- visitante


@pytest.mark.django_db
def test_visitante_ve_o_convite_e_nunca_um_erro(client, com_site, visitante):
    resposta = client.get(reverse("base"))

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Suas conquistas ficam aqui" in corpo
    assert "Entrar na escola" in corpo


@pytest.mark.django_db
def test_visitante_nao_cria_perfil_nenhum(client, com_site, visitante):
    client.get(reverse("base"))

    assert PerfilJogador.objects.count() == 0
    assert Pessoa.objects.count() == 0


# ------------------------------------------------------------ quem está logado


@pytest.mark.django_db
def test_o_primeiro_acesso_cria_o_perfil(client, com_site, logado):
    resposta = client.get(reverse("base"))

    assert resposta.status_code == 200
    perfil = PerfilJogador.objects.get()
    assert perfil.pessoa_id == ALGUEM
    assert perfil.site_id == SITE
    assert perfil.xp_total == 0
    assert perfil.nivel == 1


@pytest.mark.django_db
def test_o_segundo_acesso_nao_duplica_o_perfil(client, com_site, logado):
    """`Unique(pessoa, site_id)`, e a tela respeitando o que o banco impõe."""
    client.get(reverse("base"))
    client.get(reverse("base"))

    assert PerfilJogador.objects.count() == 1
    assert Pessoa.objects.count() == 1


@pytest.mark.django_db
def test_a_tela_mostra_o_degrau_e_o_que_falta(client, com_site, logado):
    _degraus((1, 0, "Aprendiz"), (2, 50, "Aprendiz de Ateliê"))
    Pessoa.objects.create(id_da_plataforma=ALGUEM, email="a@b.invalid")
    PerfilJogador.objects.create(pessoa_id=ALGUEM, site_id=SITE, xp_total=20, nivel=1)

    corpo = client.get(reverse("base")).content.decode()

    assert "Aprendiz" in corpo
    assert "30" in corpo, "não disse quanto falta para o próximo degrau"
    assert "40%" in corpo, "a barra não refletiu 20 de 50"


@pytest.mark.django_db
def test_no_ultimo_degrau_a_tela_nao_promete_um_proximo(client, com_site, logado):
    _degraus((1, 0, "Aprendiz"))
    Pessoa.objects.create(id_da_plataforma=ALGUEM, email="a@b.invalid")
    PerfilJogador.objects.create(pessoa_id=ALGUEM, site_id=SITE, xp_total=999, nivel=1)

    corpo = client.get(reverse("base")).content.decode()

    assert "último degrau" in corpo
    assert "Faltam" not in corpo


@pytest.mark.django_db
def test_sem_nivel_ativo_a_tela_abre_igual(client, com_site, logado):
    """A economia nasce DESLIGADA. Nenhum degrau ativo não é motivo de erro."""
    NivelDefinicao.objects.create(
        nivel=1, site_id=SITE, xp_necessario=0, titulo="Aprendiz", ativa=False
    )

    resposta = client.get(reverse("base"))

    assert resposta.status_code == 200
    assert (
        "Aprendiz" not in resposta.content.decode()
    ), "mostrou um degrau que o mantenedor ainda não ligou"


# ------------------------------------------- a falha que melhor se esconde


@pytest.mark.django_db
def test_sem_site_id_a_tela_abre_como_visitante_e_nao_quebra(
    client, monkeypatch, logado
):
    """`SITE_ID` ausente apaga a etiqueta de todo mundo, e NÃO derruba a página.

    É a falha ABERTA que o contrato exige, e é justamente por ela ser silenciosa
    que `infra/provisionar-gamificacao.sh` se recusa a terminar sem esse campo.
    Aqui o teste fixa o comportamento: 200, e o convite no lugar dos números.
    """
    monkeypatch.delenv("SITE_ID", raising=False)

    resposta = client.get(reverse("base"))

    assert resposta.status_code == 200
    assert "Suas conquistas ficam aqui" in resposta.content.decode()
    assert PerfilJogador.objects.count() == 0


# ------------------------------------------------------------------ o estático


@pytest.mark.django_db
def test_o_css_responde_e_com_o_tipo_certo(client):
    resposta = client.get(reverse("estatico", args=["gamificacao.css"]))

    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/css")


@pytest.mark.django_db
def test_o_estatico_recusa_sair_da_pasta(client):
    """Trava de travessia: `../` não alcança o resto do container."""
    resposta = client.get("/static/../config/settings.py")

    assert resposta.status_code in (301, 404)


@pytest.mark.django_db
def test_o_template_pede_o_css_por_url_e_nao_por_static(client, com_site, visitante):
    """`armadilhas/102`: `{% static %}` apontaria para o `funil`, não para cá.

    A régua é o HTML de verdade: o `<link>` tem de sair com o caminho desta
    célula. Em teste não há `SCRIPT_NAME`, então o esperado é `/static/…` desta
    urlconf — o que muda em produção é o prefixo que o `{% url %}` acrescenta, e
    é exatamente esse acréscimo que `{% static %}` não faria.
    """
    corpo = client.get(reverse("base")).content.decode()

    assert reverse("estatico", args=["gamificacao.css"]) in corpo
