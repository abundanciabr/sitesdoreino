"""O rodapé da casa das Páginas: em toda tela, e com a assinatura do site.

Cópia do PADRÃO da `funil`, do `forum` e da `gamificacao` (Lei 3), inclusive nos
guardas, e os guardas são a metade que mais importa copiar. Cada um corresponde
a uma forma diferente de esta peça se perder:

1. **A frase "em todas as páginas" envelhecendo em silêncio.** A varredura do
   urlconf real é o que impede isso: tela nova desta casa herda o rodapé, e tela
   que alguém quiser SEM rodapé precisa estar dita por nome.
2. **A tabela certa e o molde ignorando a decisão.** Por isso toda asserção é
   sobre o CORPO RENDERIZADO, nunca sobre a tabela de regras (`armadilhas/087`:
   vazamento não escolhe a tag que você previu).
3. **O estilo que não chega ao navegador.** Classe nova no HTML sem regra no
   estilo é um rodapé sem forma, e nada fica vermelho (`armadilhas/083`). Aqui a
   folha é embutida na moldura, então a prova é sobre o corpo servido.

E um quarto, que é desta casa e de nenhuma vizinha: **as três telas da porta são
desenhadas pelo middleware, ANTES de o Django resolver a rota**. Elas chegam ao
processador de contexto sem nome de rota, e são as páginas que um visitante vê
primeiro. Um tratamento ingênuo de "sem nome" as deixaria sem assinatura, e
ninguém perceberia até alguém abrir o site.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.test import Client
from django.urls import get_resolver
from django.utils import timezone

import apps.core as core
from apps.core import rodape as regras

from tests.conftest import ANA, COOKIE, dublar_matricula, dublar_sessao


def bater(caminho: str = "/", *, cookie: str | None = None):
    cabecalhos = {"HTTP_COOKIE": cookie} if cookie else {}
    return Client().get(caminho, **cabecalhos)


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as telas, inclusive nas que a porta desenha
# ---------------------------------------------------------------------------
def test_a_prancheta_tem_rodape(aluna):
    assert '<footer class="rodape rodape-completo">' in texto(bater(cookie=COOKIE))


@pytest.mark.parametrize(
    "motivo,estado",
    [("entrar", 200), ("sem-matricula", 403), ("sem-resposta", 503)],
)
def test_as_tres_telas_da_porta_tambem_tem_rodape(env_dos_pares, rede, motivo, estado):
    """As páginas que o middleware desenha antes da resolução de rota.

    São elas que uma leitura ingênua de `variante_da_rota(None)` deixaria sem
    assinatura, e são as primeiras que um visitante desta casa vê. Recusa é
    página, e página tem rodapé.
    """
    if motivo == "sem-matricula":
        dublar_sessao(rede, ANA)
        dublar_matricula(rede, ANA["email"], "cadastrado")
    elif motivo == "sem-resposta":
        dublar_sessao(rede, status=500)

    resposta = bater(cookie=COOKIE if motivo != "entrar" else None)
    assert resposta.status_code == estado
    assert '<footer class="rodape' in texto(resposta)


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
    assert "prancheta" in nomes, "a varredura não encontrou o urlconf da célula"
    sem_rodape = {nome for nome in nomes if regras.variante_da_rota(nome) is None}
    assert sem_rodape == set(regras.ROTAS_SEM_PAGINA) & nomes
    for nome in nomes - sem_rodape:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


def test_a_tela_sem_nome_de_rota_tambem_herda_o_padrao():
    """A regra que sustenta as três telas da porta, medida na função.

    O par com o guarda de cima é de propósito: aqui se mede a decisão, lá se
    mede o corpo servido. Uma das duas sozinha passaria verde com a outra
    metade quebrada.
    """
    assert regras.variante_da_rota(None) == "completo"


# ---------------------------------------------------------------------------
# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
# ---------------------------------------------------------------------------
def test_o_rodape_completo_tem_marca_links_e_direitos(aluna):
    corpo = texto(bater(cookie=COOKIE))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/docs/"' in corpo


def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(aluna, monkeypatch):
    """A variante que ainda não tem uso, exercitada mesmo assim: é ela que o
    painel vai oferecer, e variante que só nasce no dia do pedido nasce sem
    teste. A prova é sobre o CORPO, não sobre a tabela."""
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "prancheta", "enxuto")
    corpo = texto(bater(cookie=COOKIE))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert "Meshcraft Academy</p>" not in corpo


def test_pagina_declarada_sem_rodape_nao_desenha_footer_nenhum(aluna, monkeypatch):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "prancheta", None)
    assert "<footer" not in texto(bater(cookie=COOKIE))


def test_o_ano_dos_direitos_vem_do_servidor(aluna):
    corpo = texto(bater(cookie=COOKIE))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


def test_o_link_do_site_sai_do_settings_e_nao_de_uma_segunda_verdade(aluna, settings):
    """Uma célula com duas respostas para "onde fica a capa do site" tem uma
    resposta errada esperando a hora. Esta lê a que já existia."""
    settings.URL_DA_CAPA = "https://outra.escola/"
    assert 'href="https://outra.escola/"' in texto(bater(cookie=COOKIE))


def test_o_rodape_leva_para_fora_desta_casa_e_para_mais_nada(aluna, settings):
    """Um link para onde a pessoa já está gasta espaço e ensina a desconfiar da
    navegação. Toda página que desenha este rodapé está dentro de `/pages`.

    A lista é conferida por IGUALDADE, e não por `in`: um terceiro link
    acrescentado com pressa reprova aqui em vez de entrar em silêncio.
    """
    settings.URL_DA_CAPA = "https://meshcraft.test/"
    corpo = texto(bater(cookie=COOKIE))
    inicio = corpo.index('<nav class="links"')
    links = corpo[inicio : corpo.index("</nav>", inicio)]
    assert re.findall(r'href="([^"]+)"', links) == [
        "https://meshcraft.test/",
        regras.URL_DOS_DOCUMENTOS,
    ]


# ---------------------------------------------------------------------------
# 3. O estilo chega mesmo ao navegador
# ---------------------------------------------------------------------------
def test_o_estilo_do_rodape_chega_junto_com_a_pagina(aluna):
    """Esta casa serve o estilo embutido na moldura, então a prova é sobre o
    corpo servido, e não sobre um arquivo em disco que ninguém garante que o
    navegador alcança (`armadilhas/083`)."""
    corpo = texto(bater(cookie=COOKIE))
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in corpo


# ---------------------------------------------------------------------------
# 4. A moldura, a casa onde a peça comum mora
# ---------------------------------------------------------------------------
def test_todas_as_telas_vestem_a_mesma_moldura():
    """Tela solta nasce sem menu e sem rodapé, e nada fica vermelho.

    A varredura lê a PASTA, e não uma lista: tela nova que nascer com o próprio
    `<html>` reprova aqui, e a mensagem diz o que fazer (`armadilhas/242`).
    """
    pasta = Path(core.__file__).parent / "templates" / "pages"
    telas = sorted(p for p in pasta.glob("*.html") if p.name != "moldura.html")
    assert telas, "a varredura não encontrou tela nenhuma — isto é falha de medição"

    soltas = [
        p.name for p in telas if "{% extends" not in p.read_text(encoding="utf-8")
    ]
    assert not soltas, (
        f"estas telas não vestem a moldura: {soltas}. Toda tela desta célula "
        f"estende `pages/moldura.html`, que é quem carrega o rodapé e o menu do "
        f"topo para todas de uma vez. Tela solta nasce sem as duas coisas, e "
        f"nada fica vermelho até alguém olhar o site."
    )
