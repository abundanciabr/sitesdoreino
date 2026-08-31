"""O MASCOTE da página de ideia nova, medido pela borda HTTP.

Pedido do mantenedor em 30/08/2026: um ícone animado, com cara de 3D/Blender/
Roblox, no formulário de CRIAR — aqui e no fórum da escola. Em 31/08 ele
escolheu, entre quatro desenhos animados lado a lado, **o tijolo que gira**: uma
peça de montar numa mesa giratória. A marcação está inline em
`templates/sugestoes/nova.html` e a animação inteira em
`static/sugestoes/caixa.css`.

O guarda que mais importa deste arquivo é o da FOLHA, e ele mede TRÊS coisas
porque são três as maneiras de o tijolo deixar de ser um tijolo: sem
`@keyframes` ele não gira; sem `preserve-3d` as seis faces empilham chapadas e a
volta vira origami; sem `perspective` ele gira sem nada se aproximar do olho.
Qualquer uma das três sozinha devolve um quadrado — e um quadrado passa em
qualquer teste que só procure a marcação. O segundo guarda é o do `:has()`, a
ponte entre o cursor dentro do formulário e o mascote, que mora fora dele; ele é
o tipo de seletor que uma "limpeza" de CSS apaga por parecer sobra.

O mascote é de UMA tela só, e a terceira asserção existe para isso continuar
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

FOLHA = "sugestoes/caixa.css"


def _folha_servida(cliente) -> str:
    """A folha como o navegador a recebe — pela rota, não pelo disco.

    Ler o arquivo com `open()` provaria que ele está no repositório; o que
    importa é que ele chega, e é a rota `estatico` que entrega (armadilhas/083).
    """
    resposta = cliente.get(reverse("estatico", kwargs={"caminho": FOLHA}))
    assert resposta.status_code == 200, resposta.status_code
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode()
    return resposta.content.decode()


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


def test_a_folha_traz_a_volta_a_profundidade_e_o_botao_de_desligar(dentro):
    """As três pernas do tijolo, e o botão de desligar.

    Sem estas regras o mascote é um quadrado parado — e o pedido era um ícone
    ANIMADO e 3D. O `prefers-reduced-motion` entra no mesmo guarda de
    propósito: movimento que não se pode desligar é acessibilidade quebrada, e
    some tão silenciosamente quanto a animação.
    """
    folha = _folha_servida(dentro.client)

    assert "@keyframes mascote-gira" in folha, "a volta do tijolo sumiu da folha"
    assert "preserve-3d" in folha, (
        "sem `transform-style: preserve-3d` as seis faces empilham chapadas: o "
        "cubo deixa de ser cubo e a volta vira origami"
    )
    assert "perspective" in folha, (
        "sem `perspective` o tijolo gira sem nada se aproximar do olho — é a "
        "diferença entre girar e escorregar"
    )
    assert "prefers-reduced-motion" in folha, (
        "a folha perdeu o desligamento de movimento — quem sente enjoo com "
        "animação na tela pede isso ao sistema uma vez, e o site tem de obedecer"
    )


def test_o_mascote_reage_ao_cursor_dentro_do_formulario(dentro):
    """A ponte entre o formulário e o mascote, que mora FORA dele.

    Sem `:has()` não existe seletor de irmão anterior em CSS, e a alternativa
    seria JavaScript — que esta célula não tem, por decisão registrada no topo
    da folha. Este guarda é o que faz uma limpeza futura perceber que a linha
    não é sobra.
    """
    folha = _folha_servida(dentro.client)

    assert ":has(form:focus-within) .mascote-cubo { animation-duration" in folha, (
        "sumiu a regra que faz o tijolo ACELERAR quando a pessoa põe o cursor "
        "num campo. A asserção carrega o `animation-duration` de propósito: o "
        "mesmo seletor reaparece no bloco de `prefers-reduced-motion`, e sem "
        "esta metade o guarda ficaria verde com a aceleração apagada"
    )
    assert ":has(form:focus-within) .mascote { filter" in folha, (
        "sumiu a regra que faz o tijolo ACENDER — a borda de luz do objeto "
        "selecionado"
    )
