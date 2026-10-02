"""O MASCOTE da página de ideia nova, medido pela borda HTTP.

Pedido do mantenedor em 30/08/2026: um ícone animado, com cara de 3D/Blender/
Roblox, no formulário de CRIAR — aqui e no fórum da escola. Em 31/08 ele
escolheu, entre quatro desenhos animados lado a lado, **o tijolo que gira**: uma
peça de montar numa mesa giratória. A marcação está inline em
`templates/sugestoes/nova.html` e a animação inteira em
`static/sugestoes/caixa.css`.

O mascote é de UMA tela só, e o segundo teste existe para isso continuar
verdade: ele marca o momento de encarar um formulário em branco. Espalhado pela
Caixa inteira, viraria papel de parede.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

# O que prova que o mascote CHEGOU: a moldura do desenho e uma peça de dentro
# dele. Só `class="mascote"` ficaria verde com um `<svg>` vazio.
MOLDURA = 'class="mascote"'
PECA = 'class="mascote-cubo"'


def _pagina(cliente, endereco: str) -> str:
    """A página, com o 200 conferido ANTES de qualquer asserção.

    Sem esta linha, um guarda de AUSÊNCIA (o do quadro, abaixo) ficaria verde
    contra a página de 404, que também não tem mascote nenhum. É o falso-verde
    mais barato de cometer e o mais caro de perceber.
    """
    resposta = cliente.get(endereco)
    assert resposta.status_code == 200, resposta.status_code
    return resposta.content.decode()


def test_a_pagina_de_ideia_nova_chega_com_o_mascote(dentro, categoria):
    corpo = _pagina(dentro.client, reverse("nova_sugestao"))

    assert "O que está faltando?" in corpo
    assert MOLDURA in corpo, "a página de ideia nova veio sem o mascote"
    assert PECA in corpo, "a caixa do mascote chegou vazia"


def test_o_quadro_nao_leva_o_mascote(dentro, categoria):
    """Ele é o convite para CRIAR. No quadro, que é a tela de ler e votar, um
    bloco animado só disputaria a atenção com as ideias das outras pessoas."""
    corpo = _pagina(dentro.client, reverse("quadro"))

    assert MOLDURA not in corpo, "o mascote vazou para o quadro"
