"""O selo da escola no portfólio ganha voz na tela do sininho.

**Quem chega neste cartão esperou.** O aluno mandou o portfólio para a fila da
escola e ficou até cinco dias úteis sem saber se alguém tinha olhado (degrau 12
de `docs/changespecs/CS-PAGES-0001.md`, critério AC-12). Sem este cartão, a
carta que a célula `pages` publica cairia no ramo do `desconhecido` e essa
pessoa leria *"este recado é de um tipo que esta tela ainda não sabe mostrar"*,
que é a resposta certa da tela e a errada para quem estava esperando resposta.

**Esta tela aprende o assunto ANTES de a `pages` publicá-lo**, que é a mesma
ordem escrita no bloco [ASSUNTOS] de `apps/core/avisos.py` e no arquivo
`test_avisos_de_outros_assuntos.py` ao lado: quem aprende depois mostra o cartão
honesto e inútil primeiro.

Contrato dos parâmetros: `contracts/eventos/notificacao.devida.v1.json`, ramo
`pages.portfolio-conferido`, acrescentado ao `enum` no Rito de Contrato de
06/09/2026 com o mantenedor presente. Nada aqui inventa campo que não esteja lá.

**O `conferido_por_papel` é opcional e HOJE não chega de ninguém**: a `pages`
reconhece a equipe por uma lista de ids no env e não sabe qual deles é professor.
Os dois casos são medidos aqui de propósito, e o que importa é que a frase sem
ele continue inteira: é esse o estado real da produção no dia em que este
arquivo nasceu.
"""

import httpx
import pytest
from django.urls import reverse

from apps.core.avisos import ASSUNTO_PORTFOLIO, _item_para_o_template

pytestmark = pytest.mark.django_db

#: O único parâmetro obrigatório do ramo, e o estado real de hoje.
MINIMO = {"portfolio_id": "7"}


def _carta(parametros, *, id_="900", lido=False):
    return {
        "id": id_,
        "assunto": ASSUNTO_PORTFOLIO,
        "parametros": parametros,
        "ator_id": "p_monitora",
        "lido_em": "2026-09-06T10:00:00+00:00" if lido else None,
        "criado_em": "2026-09-06T09:00:00+00:00",
    }


def _responde_com(rede, cartas):
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(200, json={"itens": cartas, "proximo_cursor": None})
    )


# --------------------------------------------- 1. a tradução, sozinha


def test_a_carta_do_selo_sai_do_ramo_desconhecido():
    """O guarda mais direto: antes deste cartão ela caía no genérico."""
    item = _item_para_o_template(_carta(MINIMO), {})

    assert "desconhecido" not in item
    assert item["assunto"] == ASSUNTO_PORTFOLIO


def test_a_carta_do_selo_nao_vira_cartao_de_sugestao():
    """Cair no ramo de sugestão é o que faz a página estourar: o título dele
    monta `{% url 'sugestao' aviso.sugestao_id %}` com um id que não existe."""
    item = _item_para_o_template(_carta(MINIMO), {})

    assert "sugestao_id" not in item
    assert "status_novo_label" not in item


def test_sem_o_papel_o_cartao_simplesmente_nao_diz_quem_conferiu():
    """O estado de HOJE, e ele não é erro: a `pages` não sabe o papel."""
    item = _item_para_o_template(_carta(MINIMO), {})

    assert item["papel_frase"] == ""


def test_o_papel_conhecido_vira_frase_e_o_desconhecido_some():
    """Fail-open, a mesma regra do `validador_papel` do marco: papel fora do
    mapa não vira rótulo chutado na cara do aluno."""
    com_papel = _item_para_o_template(
        _carta({**MINIMO, "conferido_por_papel": "monitor"}), {}
    )
    fora_do_mapa = _item_para_o_template(
        _carta({**MINIMO, "conferido_por_papel": "sindico"}), {}
    )

    assert com_papel["papel_frase"] == "Quem olhou foi um monitor da escola."
    assert fora_do_mapa["papel_frase"] == ""


# --------------------------------------------- 2. a tela, de ponta a ponta


def test_o_aluno_le_que_a_escola_conferiu_e_o_que_o_selo_vale(dentro, rede, quadro):
    """A promessa do selo é limitada de propósito, e o aluno lê o limite.

    Ele vale para o que a pessoa da equipe viu NO DIA: a foto entra por link
    colado e a escola não controla o que está do outro lado dele. A estante do
    aluno já diz isso, e um aviso que prometesse mais chegaria primeiro.
    """
    _responde_com(rede, [_carta(MINIMO)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "A escola conferiu o seu portfólio" in corpo
    assert "viu no dia da conferência" in corpo
    assert "ainda não sabe mostrar" not in corpo


def test_a_carta_do_selo_nao_estoura_a_pagina(dentro, rede, quadro):
    """200 com a carta na lista, nunca 500."""
    _responde_com(rede, [_carta(MINIMO)])

    resposta = dentro.client.get(reverse("avisos"))

    assert resposta.status_code == 200
    assert "(sugestão não encontrada)" not in resposta.content.decode()


def test_o_id_opaco_do_portfolio_nunca_chega_na_tela(dentro, rede, quadro):
    """`portfolio_id` existe para reconstruir o histórico de uma conferência
    contestada. Na tela do aluno ele é ruído sobre um dado inutilizável, como o
    `matricula_id` e o `conquista_slug` já são."""
    _responde_com(rede, [_carta({"portfolio_id": "sequencia-improvavel-42"})])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "sequencia-improvavel-42" not in corpo


def test_o_cartao_do_selo_nao_leva_a_lugar_nenhum(dentro, rede, quadro):
    """Sem link, como os cinco cartões acima dele: a Prancheta mora na célula
    `pages`, que esta tela não consulta, e um endereço escrito à mão aqui seria
    a segunda verdade sobre onde ela fica."""
    _responde_com(rede, [_carta(MINIMO)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()
    cartao = corpo.split('<article class="aviso')[1].split("</article>")[0]

    assert "<a href" not in cartao


def test_a_carta_do_selo_pode_ser_marcada_como_lida(dentro, rede, quadro):
    """Aviso que a pessoa não consegue tirar da frente fica contando no sino
    para sempre, e sino que não zera é o que faz alguém parar de olhar."""
    _responde_com(rede, [_carta(MINIMO)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Marcar como lido" in corpo


def test_o_nome_de_quem_conferiu_nunca_aparece(dentro, rede, quadro):
    """`ator_id` viaja na carta e a tela do aluno sempre diz "a equipe". É a
    mesma separação que vale para toda esta página desde a gênese dela."""
    _responde_com(rede, [_carta(MINIMO)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "p_monitora" not in corpo
