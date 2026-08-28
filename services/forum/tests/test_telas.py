"""Guardas das telas — o que a pessoa vê, e o que ela NÃO vê.

A rede está dublada com `respx` (`conftest.py`): nenhum teste depende de a
`identidade` ou a `alunos` estarem no ar, porque suíte que depende de outra
célula fica vermelha por motivo alheio.
"""

import pytest
from django.urls import reverse

from apps.forum.models import Area, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db


@pytest.fixture
def area_publica():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        descricao="Pergunte sem medo.",
        visibilidade=Area.Visibilidade.PUBLICA,
    )


@pytest.fixture
def area_de_alunos():
    return Area.objects.create(
        slug="turma-secreta",
        nome="Só para alunos",
        visibilidade=Area.Visibilidade.ALUNOS,
    )


@pytest.fixture
def autor():
    return Pessoa.objects.create(
        id_da_plataforma="p1", email="a@b.com", nome_exibido="Ana"
    )


def test_visitante_ve_a_area_publica_e_nao_ve_a_de_alunos(
    client, area_publica, area_de_alunos
):
    resposta = client.get(reverse("home"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Dúvidas gerais" in corpo
    assert "Só para alunos" not in corpo


def test_o_forum_vazio_diz_que_esta_vazio_em_vez_de_fingir(client):
    """O "salão vazio" é problema declarado da lei §6.1 — a tela é honesta."""
    resposta = client.get(reverse("home"))
    assert resposta.status_code == 200
    assert "Ainda não há nenhuma área aberta" in resposta.content.decode()


def test_area_fechada_responde_404_e_nao_403(client, area_de_alunos):
    """404 e não 403 é decisão de segurança.

    Um 403 confirmaria que a área existe — e numa escola isso vaza a estrutura
    de turmas para quem não deveria conhecê-la.
    """
    resposta = client.get(reverse("area", args=[area_de_alunos.slug]))
    assert resposta.status_code == 404


def test_topico_de_area_fechada_tambem_responde_404(client, area_de_alunos, autor):
    """A permissão é a da ÁREA; o endereço do tópico não é atalho."""
    topico = Topico.objects.create(area=area_de_alunos, autor=autor, titulo="segredo")
    resposta = client.get(reverse("topico", args=[topico.pk]))
    assert resposta.status_code == 404


def test_a_conversa_publica_aparece_inteira(client, area_publica, autor):
    topico = Topico.objects.create(
        area=area_publica, autor=autor, titulo="Como texturizar?"
    )
    Mensagem.objects.create(topico=topico, autor=autor, texto="Primeira fala")
    Mensagem.objects.create(topico=topico, autor=autor, texto="Segunda fala")

    resposta = client.get(reverse("topico", args=[topico.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Primeira fala" in corpo
    assert "Segunda fala" in corpo
    assert "Ana" in corpo


def test_mensagem_removida_some_da_tela_mas_continua_no_banco(
    client, area_publica, autor
):
    """Remoção suave: some para quem lê, fica para quem precisa auditar."""
    from django.utils import timezone

    topico = Topico.objects.create(area=area_publica, autor=autor, titulo="t")
    Mensagem.objects.create(topico=topico, autor=autor, texto="fica")
    ruim = Mensagem.objects.create(
        topico=topico,
        autor=autor,
        texto="ISTO FOI REMOVIDO",
        removida_em=timezone.now(),
    )

    corpo = client.get(reverse("topico", args=[topico.pk])).content.decode()
    assert "fica" in corpo
    assert "ISTO FOI REMOVIDO" not in corpo
    assert Mensagem.objects.filter(pk=ruim.pk).exists()


def test_topico_esperando_moderacao_nao_aparece(client, area_publica, autor):
    """A fila de aprovação existe desde o começo (lei §4.6)."""
    topico = Topico.objects.create(
        area=area_publica,
        autor=autor,
        titulo="ainda não aprovado",
        estado=Topico.Estado.ESPERANDO,
    )
    assert client.get(reverse("topico", args=[topico.pk])).status_code == 404
    corpo = client.get(reverse("area", args=[area_publica.slug])).content.decode()
    assert "ainda não aprovado" not in corpo


def test_o_css_e_servido_pela_rota_propria(client):
    """`armadilhas/083`: sem esta rota o estilo é 404 em produção e SÓ lá."""
    resposta = client.get(reverse("estatico", args=["forum.css"]))
    assert resposta.status_code == 200
    assert "text/css" in resposta["Content-Type"]


def test_a_rota_de_estatico_nao_deixa_sair_da_pasta(client):
    """Trava de travessia: `../` não pode virar leitura de arquivo do sistema."""
    resposta = client.get("/static/../config/settings.py")
    assert resposta.status_code == 404


def test_a_pagina_carrega_o_css_por_url_e_nao_por_caminho_cravado(client, area_publica):
    """`{% url %}` e não caminho à mão — é ele que carrega o prefixo público.

    Com `/static/forum.css` escrito na unha, o fórum pediria o CSS ao `funil`
    em produção (`armadilhas/029` e `/081`).
    """
    corpo = client.get(reverse("home")).content.decode()
    assert reverse("estatico", args=["forum.css"]) in corpo
