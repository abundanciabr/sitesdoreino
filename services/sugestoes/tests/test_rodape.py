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
    """A folha, pedida ao servidor e não ao disco: a rota devolve `FileResponse`, sem
    `.content`."""
    resposta = client.get(
        reverse("estatico", kwargs={"caminho": "sugestoes/caixa.css"})
    )
    assert resposta.status_code == 200, resposta.status_code
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


# 1. Em todas as telas
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
    """A porta (`entrar`) tem o rodapé enxuto, incluído como peça e com o estilo
    embutido."""
    assert regras.REGRA_POR_ROTA["entrar"] == "enxuto"
    corpo = client.get(reverse("entrar")).content.decode()
    assert '<footer class="rodape rodape-enxuto">' in corpo
    assert "Todos os direitos reservados" in corpo
    assert 'class="links"' not in corpo


def test_o_servidor_de_estaticos_nao_ganha_rodape(client, rf):
    """A rota de máquina não ganha rodapé e a de página ganha, medido em par."""

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


# 2. O que o rodapé completo mostra, e a variante que o painel vai oferecer
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
    """A variante enxuta, exercitada pelo corpo da página e não pela tabela."""
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


# 3. O pé antigo não volta por engano
def test_o_pe_antigo_nao_voltou(dentro, sugestao):
    """O pé antigo foi trocado de propósito pelo rodapé do site e não pode voltar num
    merge."""
    corpo = _corpo(dentro, reverse("quadro"))
    assert 'class="pe"' not in corpo
    assert "o que você pedir, a equipe lê" not in corpo
