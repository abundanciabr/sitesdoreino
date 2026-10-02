"""Verifica o rodapé e o estilo entregue nas telas de Sugestões."""

import pytest
from django.urls import reverse

from apps.core import rodape as regras

pytestmark = pytest.mark.django_db

def _corpo(pessoa, endereco: str) -> str:
    resposta = pessoa.client.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def _css(client) -> str:
    """A folha, pedida ao SERVIDOR e não ao disco.

    A rota devolve um `FileResponse`, que NÃO tem `.content` — pedir por ele
    levanta `AttributeError` e o teste fica vermelho por instrumento, não por
    defeito (INV-CI01: não medir não é estar certo).
    """
    resposta = client.get(
        reverse("estatico", kwargs={"caminho": "sugestoes/caixa.css"})
    )
    assert resposta.status_code == 200, resposta.status_code
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Em TODAS as telas
# ---------------------------------------------------------------------------
def test_o_quadro_tem_rodape(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    assert '<footer class="rodape rodape-completo">' in corpo


def test_a_pagina_de_uma_ideia_tem_rodape(dentro, sugestao):
    corpo = _corpo(dentro, reverse("sugestao", args=[sugestao.id]))
    assert '<footer class="rodape' in corpo


def test_a_tela_de_escrever_uma_ideia_tem_rodape(dentro, categoria):
    assert '<footer class="rodape' in _corpo(dentro, reverse("nova_sugestao"))


def test_rota_que_ninguem_decidiu_herda_o_padrao():
    assert regras.variante_da_rota("uma-tela-que-nascer-amanha") == "completo"


def test_a_porta_da_caixa_tem_o_rodape_enxuto(client, porta):
    """A tela que eu tinha deixado de fora, e a correção de rumo.

    `entrar.html` não tem CSS externo, nem script, nem fonte remota, porque uma
    dependência de rede numa página de LOGIN quebra exatamente quando não
    deveria. No PR #871 eu li essa restrição e declarei a tela "sem rodapé" —
    aceitei o limite em vez de resolvê-lo.

    O PR #734, aberto em 31/08/2026 e nunca pousado, já tinha a solução: o
    rodapé vira PEÇA incluída pelos dois moldes, e o estilo dela entra embutido,
    com as cores do sistema. Este guarda é o que impede a volta atrás.

    Enxuto, e não completo: quem chega numa tela de entrar veio fazer UMA coisa,
    e uma lista de links ali é atrito (mesma escolha da `funil`).
    """
    assert regras.REGRA_POR_ROTA["entrar"] == "enxuto"
    corpo = client.get(reverse("entrar")).content.decode()
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo


def test_o_estilo_do_rodape_da_porta_e_embutido(client, porta):
    """Marcação sem regra é rodapé sem forma, e nada ficaria vermelho.

    Esta tela NÃO carrega o `caixa.css` — de propósito. Se as regras `.rodape`
    só existissem lá, a porta mostraria um rodapé sem borda, sem espaçamento e
    com o tamanho de fonte do corpo, e todo guarda de renderização passaria.
    """
    corpo = client.get(reverse("entrar")).content.decode()
    # A MARCAÇÃO, e não o nome do arquivo: `caixa.css` aparece nesta página
    # dentro de um COMENTÁRIO de CSS, que explica justamente por que a folha não
    # é carregada aqui. Procurar a string solta é a `armadilhas/247` — o guarda
    # ficaria vermelho por ler a explicação como se fosse a coisa explicada.
    assert '<link rel="stylesheet"' not in corpo, (
        "a porta passou a carregar folha de estilo externa — se isso foi de "
        "propósito, este guarda precisa mudar junto; se não, é a dependência de "
        "rede que a tela recusa por desenho."
    )
    assert ".rodape {" in corpo
    assert ".rodape .direitos" in corpo or ".rodape p {" in corpo


def test_o_servidor_de_estaticos_nao_ganha_rodape(client, rf):
    """Rota de MÁQUINA: um rodapé dentro do arquivo CSS seria lixo no arquivo, e
    o navegador o serviria como estilo.

    **A prova é um PAR**, e não uma afirmação de ausência sobre um `.css` que
    não teria `<footer>` de jeito nenhum (`armadilhas/266`): a rota de máquina
    devolve `{}`, a rota de página devolve o rodapé. Arranque `ROTAS_SEM_PAGINA`
    e a primeira cai; arranque `rodape_do_contexto` e cai a segunda.
    """

    class Casamento:
        def __init__(self, nome):
            self.url_name = nome

    def requisicao_de(nome):
        pedido = rf.get("/")
        pedido.resolver_match = Casamento(nome)
        return pedido

    assert regras.rodape_do_contexto(requisicao_de("estatico")) == {}
    assert "rodape" in regras.rodape_do_contexto(requisicao_de("quadro"))
    assert "<footer" not in _css(client)


# ---------------------------------------------------------------------------
# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
# ---------------------------------------------------------------------------
def test_o_rodape_completo_tem_marca_links_e_direitos(dentro, sugestao):
    corpo = _corpo(dentro, reverse("quadro"))
    assert "Meshcraft Academy" in corpo
    assert "Todos os direitos reservados" in corpo
    for rotulo in ("Início do site", "Caixa de Sugestões", "Documentos"):
        assert f">{rotulo}</a>" in corpo
    assert 'href="/docs/"' in corpo


def test_o_rodape_enxuto_perde_os_links_e_guarda_os_direitos(
    dentro, sugestao, monkeypatch
):
    """A variante que ainda não tem uso, exercitada mesmo assim: é ela que o
    painel vai oferecer, e variante que só nasce no dia do pedido nasce sem
    teste. A prova é sobre o CORPO, não sobre a tabela."""
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "quadro", "enxuto")
    corpo = _corpo(dentro, reverse("quadro"))
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo
    assert "Meshcraft Academy</p>" not in corpo


def test_pagina_declarada_sem_rodape_nao_desenha_footer_nenhum(
    dentro, sugestao, monkeypatch
):
    monkeypatch.setitem(regras.REGRA_POR_ROTA, "quadro", None)
    assert "<footer" not in _corpo(dentro, reverse("quadro"))
    assert "<footer" in _corpo(dentro, reverse("sugestao", args=[sugestao.id]))


def test_o_ano_dos_direitos_vem_do_servidor(dentro, sugestao):
    from django.utils import timezone

    corpo = _corpo(dentro, reverse("quadro"))
    assert f"© {timezone.localdate().year} Meshcraft Academy" in corpo


# ---------------------------------------------------------------------------
# 3. O estilo chega ao navegador, e com as cores DESTA área
# ---------------------------------------------------------------------------
def test_o_estilo_do_rodape_chega_pela_rota_do_css(client):
    """Classe no HTML sem regra no CSS é rodapé sem forma, e nada fica vermelho.
    Esta célula serve o estilo por rota própria (`armadilhas/083`), então a
    prova pergunta ao SERVIDOR, não ao disco."""
    css = _css(client)
    for regra in (".rodape {", ".rodape .marca", ".rodape .links", ".rodape .direitos"):
        assert regra in css


# ---------------------------------------------------------------------------
# 4. O pé antigo não volta por engano
# ---------------------------------------------------------------------------
def test_o_pe_antigo_nao_voltou(dentro, sugestao):
    """A troca foi ESCOLHA do mantenedor em 02/09/2026, não descuido.

    Ele viu as duas opções — trocar pelo rodapé do site, ou manter o pé pequeno
    e pôr o do site embaixo — e escolheu trocar: uma assinatura só no fim de
    toda página, em vez de uma por área. Se este guarda ficar vermelho, alguém
    trouxe o pé antigo de volta num merge, e a pergunta certa é para ele, não
    para o código.
    """
    corpo = _corpo(dentro, reverse("quadro"))
    assert 'class="pe"' not in corpo
    assert "o que você pedir, a equipe lê" not in corpo
