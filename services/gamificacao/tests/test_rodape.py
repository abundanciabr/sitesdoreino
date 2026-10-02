"""Verifica o rodapé e o estilo entregue nas telas de Conquistas."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core import rodape as regras

SITE = "site-de-teste"
ALGUEM = "pes-abc"


@pytest.fixture
def com_site(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)


@pytest.fixture
def visitante(monkeypatch):
    """Visitante basta para todo guarda daqui: o rodapé não depende de quem é.

    E é de propósito que ele baste — um rodapé que só aparecesse para quem
    entrou seria uma página sem assinatura justamente para quem chega de fora.
    """
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)


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
@pytest.mark.django_db
def test_a_base_tem_rodape(client, com_site, visitante):
    corpo = _corpo(client.get(reverse("base")))
    assert '<footer class="rodape rodape-completo">' in corpo


@pytest.mark.django_db
def test_a_trilha_de_marcos_tem_rodape(client, com_site, visitante):
    assert '<footer class="rodape' in _corpo(client.get(reverse("marcos")))


@pytest.mark.django_db
def test_a_forja_tem_rodape(client, com_site, visitante):
    assert '<footer class="rodape' in _corpo(client.get(reverse("forja")))


@pytest.mark.django_db
def test_a_recusa_da_fila_da_equipe_tambem_tem_rodape(client, com_site, visitante):
    """A tela de 403 é página, e página tem rodapé.

    Ela é o caso que uma lista escrita à mão esqueceria: não é uma rota, é o
    outro desfecho de uma rota que já existe.
    """
    resposta = client.get(reverse("interno"))
    assert resposta.status_code == 403
    assert '<footer class="rodape' in _corpo(resposta)


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


@pytest.mark.django_db
def test_o_servidor_de_estaticos_nao_ganha_rodape(client, rf):
    """Rota de MÁQUINA: um rodapé dentro de um arquivo CSS seria lixo no
    arquivo, e o navegador o serviria como estilo.

    **A prova é um PAR, e essa é a correção de 02/09/2026** (revisor de pouso do
    PR #868, `armadilhas/266`). A versão anterior afirmava só ausência —
    `"<footer" not in corpo` sobre um arquivo `.css` — e um arquivo de estilo não
    teria `<footer>` de jeito nenhum: o guarda ficaria verde com a regra
    arrancada do código, que é o falso-verde exato daquela armadilha.

    Aqui as duas metades correm sobre a MESMA função e o mesmo dublê de
    requisição: a rota de máquina devolve `{}`, a rota de página devolve o
    rodapé. Arranque `ROTAS_SEM_PAGINA` e a primeira cai; arranque
    `rodape_do_contexto` e cai a segunda.
    """

    class Casamento:
        def __init__(self, nome):
            self.url_name = nome

    def requisicao_de(nome):
        pedido = rf.get("/")
        pedido.resolver_match = Casamento(nome)
        return pedido

    assert regras.rodape_do_contexto(requisicao_de("estatico")) == {}
    assert "rodape" in regras.rodape_do_contexto(requisicao_de("base"))

    # E a ponta solta: o corpo servido de verdade continua sem rodapé.
    corpo = _corpo(client.get(reverse("estatico", args=["gamificacao.css"])))
    assert "<footer" not in corpo


# ---------------------------------------------------------------------------
# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_o_rodape_completo_tem_marca_links_e_direitos(client, com_site, visitante):
    corpo = _corpo(client.get(reverse("base")))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Conquistas", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/docs/"' in corpo


@pytest.mark.django_db
def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(
    client, com_site, visitante, monkeypatch
):
    """A variante que ainda não tem uso, exercitada mesmo assim: é ela que o
    painel vai oferecer, e variante que só nasce no dia do pedido nasce sem
    teste. A prova é sobre o CORPO, não sobre a tabela."""
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "base", "enxuto")
    corpo = _corpo(client.get(reverse("base")))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert "Meshcraft Academy</p>" not in corpo


@pytest.mark.django_db
def test_pagina_declarada_sem_rodape_nao_desenha_footer_nenhum(
    client, com_site, visitante, monkeypatch
):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "base", None)
    assert "<footer" not in _corpo(client.get(reverse("base")))
    assert "<footer" in _corpo(client.get(reverse("marcos")))


@pytest.mark.django_db
def test_o_ano_dos_direitos_vem_do_servidor(client, com_site, visitante):
    from django.utils import timezone

    corpo = _corpo(client.get(reverse("base")))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


@pytest.mark.django_db
def test_o_link_do_site_sai_do_settings_e_nao_de_uma_segunda_verdade(
    client, com_site, visitante, settings
):
    """Uma célula com duas respostas para "onde fica a capa do site" tem uma
    resposta errada esperando a hora. Esta lê a que já existia."""
    settings.URL_DA_CAPA = "https://outra.escola/"
    assert 'href="https://outra.escola/"' in _corpo(client.get(reverse("base")))


# ---------------------------------------------------------------------------
# 3. O estilo chega mesmo ao navegador
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_o_estilo_do_rodape_chega_pela_rota_do_css(client):
    """Classe no HTML sem regra no CSS é rodapé sem forma, e nada fica vermelho.
    Esta célula serve o estilo por rota própria (`armadilhas/083`), então a
    prova pergunta ao SERVIDOR, não ao disco."""
    css = _corpo(client.get(reverse("estatico", args=["gamificacao.css"])))
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in css


# ---------------------------------------------------------------------------
# 4. A moldura — a casa onde a peça comum mora
# ---------------------------------------------------------------------------
