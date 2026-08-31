"""O rodapé do fórum: em toda tela, e com a mesma assinatura do site.

Cópia do PADRÃO da `funil` (Lei 7), inclusive nos guardas — e os guardas são a
metade que mais importa copiar. Cada um corresponde a uma forma diferente de
esta peça se perder:

1. **A frase "em todas as páginas" envelhecendo em silêncio.** A varredura do
   urlconf real é o que impede isso: tela nova do fórum herda o rodapé, e tela
   que alguém quis SEM rodapé precisa estar dita.
2. **A tabela certa e o template ignorando a decisão.** Por isso toda asserção
   é sobre o CORPO RENDERIZADO, nunca sobre a tabela de regras
   (`armadilhas/087`: vazamento não escolhe a tag que você previu).
3. **O estilo que não chega ao navegador.** O fórum serve o CSS por rota
   própria (`armadilhas/083`), então uma classe nova no HTML sem a regra no
   arquivo é um rodapé sem forma, e nada fica vermelho.
"""

import pytest
from django.urls import get_resolver, reverse

from apps.core import rodape as regras
from apps.forum.models import Area

pytestmark = pytest.mark.django_db


@pytest.fixture
def area_publica():
    return Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        descricao="Pergunte sem medo.",
        visibilidade=Area.Visibilidade.PUBLICA,
    )


def _corpo(resposta) -> str:
    """O corpo, venha ele inteiro ou em pedaços.

    A rota do CSS devolve um `FileResponse`, que NÃO tem `.content` — pedir por
    ele levanta `AttributeError` e o teste fica vermelho por instrumento, não
    por defeito (INV-CI01: não medir não é estar certo).
    """
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as telas
# ---------------------------------------------------------------------------
def test_a_capa_do_forum_tem_rodape(client, area_publica):
    corpo = _corpo(client.get(reverse("home")))
    assert '<footer class="rodape rodape-completo">' in corpo


def test_a_area_tem_rodape(client, area_publica):
    corpo = _corpo(client.get(reverse("area", args=[area_publica.slug])))
    assert '<footer class="rodape' in corpo


def test_a_busca_tem_rodape(client, area_publica):
    corpo = _corpo(client.get(reverse("buscar"), {"q": "textura"}))
    assert '<footer class="rodape' in corpo


def test_nenhuma_rota_de_pagina_fica_sem_decisao_de_rodape():
    """A varredura que impede a frase "em todas as páginas" de envelhecer.

    Mede o urlconf REAL, não uma lista escrita à mão: rota nova que ninguém
    decidiu cai no padrão, e rota sem rodapé precisa estar dita. O silêncio
    nunca significa "sem rodapé".
    """
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None)
    }
    assert "home" in nomes, "a varredura não encontrou o urlconf da célula"
    sem_rodape = {nome for nome in nomes if regras.variante_da_rota(nome) is None}
    assert sem_rodape == set(regras.ROTAS_SEM_PAGINA) & nomes
    for nome in nomes - sem_rodape:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


def test_o_servidor_de_estaticos_nao_ganha_rodape(client):
    """Rota de MÁQUINA: um rodapé dentro de um arquivo CSS seria lixo no
    arquivo, e o navegador o serviria como estilo."""
    assert regras.variante_da_rota("estatico") is None
    corpo = _corpo(client.get(reverse("estatico", args=["forum.css"])))
    assert "<footer" not in corpo


# ---------------------------------------------------------------------------
# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
# ---------------------------------------------------------------------------
def test_o_rodape_completo_tem_marca_links_e_direitos(client, area_publica):
    corpo = _corpo(client.get(reverse("home")))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Fórum", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/"' in corpo
    assert 'href="/docs/"' in corpo


def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(
    client, area_publica, monkeypatch
):
    """A variante que ainda não tem uso, exercitada mesmo assim: é ela que o
    painel vai oferecer, e variante que só nasce no dia do pedido nasce sem
    teste. A prova é sobre o CORPO, não sobre a tabela."""
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "home", "enxuto")
    corpo = _corpo(client.get(reverse("home")))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert "Meshcraft Academy</p>" not in corpo


def test_pagina_declarada_sem_rodape_nao_desenha_footer_nenhum(
    client, area_publica, monkeypatch
):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "home", None)
    assert "<footer" not in _corpo(client.get(reverse("home")))
    assert "<footer" in _corpo(client.get(reverse("area", args=[area_publica.slug])))


def test_o_ano_dos_direitos_vem_do_servidor(client, area_publica):
    from django.utils import timezone

    corpo = _corpo(client.get(reverse("home")))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


# ---------------------------------------------------------------------------
# 3. O estilo chega mesmo ao navegador
# ---------------------------------------------------------------------------
def test_o_estilo_do_rodape_chega_pela_rota_do_css(client):
    """Classe no HTML sem regra no CSS é rodapé sem forma, e nada fica vermelho.
    Esta célula serve o estilo por rota própria (`armadilhas/083`), então a
    prova pergunta ao servidor, não ao disco."""
    css = _corpo(client.get(reverse("estatico", args=["forum.css"])))
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in css
