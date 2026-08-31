"""O rodapé da casa dentro da Caixa: em toda tela, e igual ao do resto do site.

O mantenedor reparou, olhando o site em 31/08/2026, que o rodapé que entrou no
site (PR #705) e no fórum (PR #711) **não aparecia aqui** — a Caixa tinha um pé
próprio, anterior e diferente. Estes guardas seguram as duas metades do
conserto: o rodapé da casa está presente, e o pé antigo não voltou.

O desenho e o molde dos guardas são os da `armadilhas/242`. Cada um corresponde
a uma forma diferente de esta peça se perder:

1. **A frase "em todas as telas" envelhecendo em silêncio** — a varredura do
   urlconf real. Tela nova da Caixa herda o rodapé, e tela que alguém quis sem
   ele precisa estar dita por nome.
2. **A tabela certa e o molde ignorando a decisão** — toda asserção é sobre o
   CORPO RENDERIZADO, nunca sobre a tabela (`armadilhas/087`).
3. **O estilo que não chega ao navegador** — esta célula serve o CSS por rota
   própria, então classe nova no HTML sem regra no arquivo é rodapé sem forma,
   e nada fica vermelho.
4. **O pé antigo voltando por um molde esquecido** — guarda explícito, porque
   "a classe sumiu do CSS" e "a marcação sumiu da tela" são coisas diferentes.
"""

import pytest
from django.urls import get_resolver, reverse

from apps.core import rodape as regras

pytestmark = pytest.mark.django_db


def _corpo(resposta) -> str:
    """O corpo, venha ele inteiro ou em pedaços.

    A rota do CSS devolve um `FileResponse`, que NÃO tem `.content` — pedir por
    ele levanta `AttributeError` e o teste fica vermelho por INSTRUMENTO, não
    por defeito (INV-CI01: não medir não é estar certo).
    """
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as telas
# ---------------------------------------------------------------------------
def test_o_quadro_da_caixa_tem_o_rodape_da_casa(dentro, quadro, sugestao):
    corpo = _corpo(dentro.client.get(reverse("quadro")))
    assert '<footer class="rodape rodape-completo">' in corpo
    assert "Meshcraft Academy" in corpo


def test_a_ideia_por_dentro_tem_rodape(dentro, quadro, sugestao):
    corpo = _corpo(dentro.client.get(reverse("sugestao", args=[sugestao.pk])))
    assert '<footer class="rodape' in corpo


def test_a_porta_de_entrada_tem_rodape(porta):
    """A tela de entrar é a primeira que um visitante vê — e era justamente
    uma das que davam a impressão de "outro lugar"."""
    corpo = _corpo(porta.client.get(reverse("entrar")))
    assert '<footer class="rodape rodape-enxuto">' in corpo


def test_nenhuma_rota_de_tela_fica_sem_decisao_de_rodape():
    """A varredura que impede a frase "em todas as telas" de envelhecer.

    Mede o urlconf REAL, não uma lista à mão: rota nova que ninguém decidiu cai
    no padrão, e rota sem rodapé precisa estar dita. Silêncio nunca significa
    "sem rodapé".
    """
    nomes = {
        padrao.name
        for padrao in get_resolver().url_patterns
        if getattr(padrao, "name", None)
    }
    assert "quadro" in nomes, "a varredura não encontrou o urlconf da célula"
    sem_rodape = {nome for nome in nomes if regras.variante_da_rota(nome) is None}
    assert sem_rodape == set(regras.ROTAS_SEM_PAGINA) & nomes
    for nome in nomes - sem_rodape:
        assert regras.variante_da_rota(nome) in regras.VARIANTES


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


def test_o_servidor_de_estaticos_nao_ganha_rodape(client):
    assert regras.variante_da_rota("estatico") is None
    corpo = _corpo(client.get(reverse("estatico", args=["sugestoes/caixa.css"])))
    assert "<footer" not in corpo


# ---------------------------------------------------------------------------
# 2. As variantes, e a régua que o mantenedor aprovou
# ---------------------------------------------------------------------------
def test_a_tela_de_escrever_uma_ideia_mostra_o_rodape_enxuto(dentro, quadro):
    """A mesma régua do cadastro e do login do site: onde a pessoa veio fazer
    UMA coisa, uma lista de links é convite para sair no meio do caminho."""
    corpo = _corpo(dentro.client.get(reverse("nova_sugestao")))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo


def test_o_rodape_completo_tem_marca_links_e_direitos(dentro, quadro, sugestao):
    corpo = _corpo(dentro.client.get(reverse("quadro")))
    for rotulo in ("Início do site", "Fórum", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/"' in corpo
    assert 'href="/forum/"' in corpo
    assert 'href="/docs/"' in corpo
    assert "Todos os direitos reservados" in corpo


def test_tela_declarada_sem_rodape_nao_desenha_footer_nenhum(
    dentro, quadro, sugestao, monkeypatch
):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "quadro", None)
    assert "<footer" not in _corpo(dentro.client.get(reverse("quadro")))
    assert "<footer" in _corpo(
        dentro.client.get(reverse("sugestao", args=[sugestao.pk]))
    )


def test_o_ano_dos_direitos_vem_do_servidor(dentro, quadro, sugestao):
    from django.utils import timezone

    corpo = _corpo(dentro.client.get(reverse("quadro")))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


# ---------------------------------------------------------------------------
# 3. O pé antigo foi aposentado, e não volta
# ---------------------------------------------------------------------------
def test_o_pe_antigo_so_desta_celula_nao_aparece_mais(dentro, quadro, sugestao):
    """A Caixa tinha um pé PRÓPRIO (`<footer class="pe">`, duas colunas em
    fonte mono). Ele saiu porque a Caixa é parte do site e, com um pé só dela,
    parecia outro lugar. Empilhar os dois seria dois rodapés na mesma tela.

    A asserção é sobre a marcação servida, e não sobre o CSS: some a regra e
    fica a marcação, ou o contrário, e nos dois casos a tela está errada.
    """
    corpo = _corpo(dentro.client.get(reverse("quadro")))
    assert 'class="pe"' not in corpo
    assert "o que você pedir, a equipe lê" not in corpo


def test_o_estilo_do_rodape_chega_pela_rota_do_css(client):
    """Classe no HTML sem regra no CSS é rodapé sem forma, e nada fica
    vermelho. A prova pergunta ao SERVIDOR, não ao disco."""
    css = _corpo(client.get(reverse("estatico", args=["sugestoes/caixa.css"])))
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in css
    assert ".pe {" not in css, "a regra do pé aposentado ficou para trás"


# ---------------------------------------------------------------------------
# 4. A tela que NÃO usa o molde comum — o buraco que esta célula revelou
# ---------------------------------------------------------------------------
def test_todo_molde_de_pagina_inteira_inclui_a_peca_do_rodape():
    """O guarda que a `entrar.html` ensinou a escrever.

    A `armadilhas/242` diz para pôr a peça no molde-base, e isso não basta
    sozinho: **um molde-base só cobre quem o estende.** Esta célula tem DOIS
    moldes de página inteira, e o segundo (a porta de entrada) é standalone,
    com `<html>` próprio e estilo embutido. O rodapé entrou no molde comum e
    continuou ausente lá, sem nada ficar vermelho — que foi exatamente o que o
    mantenedor viu no site em 31/08/2026.

    Por isso o guarda mede os ARQUIVOS, e não as telas: um molde standalone
    novo é justamente o caso em que ninguém lembra de escrever um teste de
    tela para ele. Ele reprova antes de a página existir.
    """
    from pathlib import Path

    pasta = Path(__file__).resolve().parent.parent / "apps/core/templates/sugestoes"
    # A marca de página inteira é o `<!doctype`, e não a tag `<html>`: a
    # própria peça do rodapé CITA `<html>` num comentário, e procurar pela tag
    # a acusaria de não incluir a si mesma. O doctype não aparece em comentário
    # de peça nenhuma, e é o que de fato distingue "página" de "pedaço".
    moldes = [
        arquivo
        for arquivo in sorted(pasta.glob("*.html"))
        if "<!doctype" in arquivo.read_text(encoding="utf-8").lower()
    ]
    assert len(moldes) >= 2, f"a varredura não achou os moldes: {moldes}"
    sem_rodape = [
        arquivo.name
        for arquivo in moldes
        if 'include "sugestoes/_rodape.html"' not in arquivo.read_text(encoding="utf-8")
    ]
    assert not sem_rodape, (
        f"molde de página inteira sem a peça do rodapé: {sem_rodape}. "
        'Acrescente {% if rodape %}{% include "sugestoes/_rodape.html" %}{% endif %} '
        "dentro do container de largura da página."
    )


def test_a_porta_de_entrada_leva_o_estilo_do_rodape_junto(porta):
    """A porta é standalone e não carrega o `caixa.css`: o estilo dela é
    embutido. Marcação sem regra é rodapé sem forma, e nada fica vermelho."""
    corpo = _corpo(porta.client.get(reverse("entrar")))
    assert ".rodape {" in corpo, "o estilo do rodapé não viajou com a página"


# ---------------------------------------------------------------------------
# 5. A isenção que o rodapé exigiu NÃO é um cheque em branco
# ---------------------------------------------------------------------------
def test_a_isencao_dos_links_de_fora_nao_cala_o_guarda_de_prefixo():
    """O rodapé obrigou a afrouxar os guardas de `*_script_name.py`.

    Até 31/08/2026 eles partiam de uma premissa verdadeira na época: todo link
    que começa com `/` é desta célula, logo tem de levar o prefixo público
    (`armadilhas/029` e `/081`). O rodapé trouxe três endereços de OUTRAS
    células, que morreriam 404 no gateway se ganhassem `/forms/sugestoes` na
    frente — e a premissa caiu.

    Afrouxar guarda é onde nasce falso-verde, então a isenção tem duas cercas,
    e este teste prova as duas:

    1. **a lista de isentos é IMPORTADA do código de produção**, nunca escrita
       à mão no teste: quem quiser calar o guarda para um link interno
       esquecido tem de declará-lo como endereço de outra célula, no código,
       onde a revisão vê;
    2. **link interno sem prefixo continua reprovando** — que é a mordida
       inteira do guarda original.
    """
    from tests.conftest import ENDERECOS_DE_FORA, links_sem_prefixo

    prefixo = "/forms/sugestoes"

    # A mordida original, intacta: um link desta célula escrito à mão.
    esquecido = '<a href="/sugestoes/nova">Nova</a>'
    assert links_sem_prefixo(esquecido, prefixo) == ["/sugestoes/nova"]

    # E o link com prefixo passa, como sempre passou.
    certo = f'<a href="{prefixo}/sugestoes/nova">Nova</a>'
    assert links_sem_prefixo(certo, prefixo) == []

    # Os isentos são exatamente os endereços que o rodapé declara — e a prova
    # é contra o módulo de produção, não contra uma cópia escrita aqui.
    assert ENDERECOS_DE_FORA == {
        regras.URL_DO_SITE,
        regras.URL_DO_FORUM,
        regras.URL_DOS_DOCUMENTOS,
    }
    for endereco in ENDERECOS_DE_FORA:
        assert links_sem_prefixo(f'<a href="{endereco}">x</a>', prefixo) == []
