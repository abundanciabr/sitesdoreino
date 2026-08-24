# tests/test_inv_rate_limit_sugestoes.py  # [RECEITA:R5 v1]
"""INV-SUG04 — 3 sugestões por 7 dias, e nem uma a mais.

Spec §10, palavra por palavra: *"rate limit leve (3 sugestões / 7 dias, sem
camadas de reputação ainda)"*. As duas metades importam:

- **morde**: a quarta da janela é recusada, e nada é gravado;
- **é leve, não uma pena**: a janela é deslizante. Passados os 7 dias das
  primeiras, a pessoa publica de novo — sem ninguém liberar, sem reputação a
  acumular, sem estado novo em lugar nenhum.

A segunda metade é a que costuma nascer quebrada. Um limite implementado como
contador que só cresce não é *rate limit*, é cota vitalícia — e a diferença só
aparece uma semana depois, quando a pessoa cala a boca achando que a Caixa a
puniu.

A janela é medida pelo `criado_em` das próprias sugestões; por isso o teste
envelhece as linhas com `update()` em vez de mexer no relógio: é o dado real
que o código consulta, não um `freeze_time` que só existe no teste.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.participacao import JANELA_DO_LIMITE, LIMITE_DE_SUGESTOES
from apps.sugestoes.models import Sugestao

pytestmark = pytest.mark.django_db


def _publicar(cliente, titulo: str):
    return cliente.post(
        reverse("nova_sugestao"),
        {
            "titulo": titulo,
            "problema": f"O problema de {titulo}.",
            "categoria": "curso",
            "publicar": "1",
        },
    )


def test_a_quarta_sugestao_da_janela_e_recusada(dentro, categoria):
    for numero in range(LIMITE_DE_SUGESTOES):
        assert _publicar(dentro.client, f"Pedido {numero}").status_code == 302

    quarta = _publicar(dentro.client, "Pedido de mais um")

    assert quarta.status_code == 429, quarta.status_code
    assert (
        Sugestao.objects.filter(autor=dentro.identidade).count() == LIMITE_DE_SUGESTOES
    )
    assert not Sugestao.objects.filter(titulo="Pedido de mais um").exists()


def test_a_recusa_explica_e_nao_e_uma_porta_fechada(dentro, categoria):
    for numero in range(LIMITE_DE_SUGESTOES):
        _publicar(dentro.client, f"Pedido {numero}")

    corpo = _publicar(dentro.client, "Pedido de mais um").content.decode()

    assert "7 dias" in corpo
    # A página de sugerir continua ali, com o rascunho: a pessoa não perde o
    # que escreveu por causa do limite.
    assert "Pedido de mais um" in corpo


def test_passada_a_janela_a_pessoa_publica_de_novo(dentro, categoria):
    for numero in range(LIMITE_DE_SUGESTOES):
        _publicar(dentro.client, f"Pedido {numero}")
    assert _publicar(dentro.client, "Depois da janela").status_code == 429

    # `update()` não passa por `auto_now_add` — é como se as três tivessem sido
    # escritas há oito dias.
    envelhecidas = timezone.now() - JANELA_DO_LIMITE - timedelta(days=1)
    Sugestao.objects.filter(autor=dentro.identidade).update(criado_em=envelhecidas)

    resposta = _publicar(dentro.client, "Depois da janela")

    assert resposta.status_code == 302, resposta.content
    assert Sugestao.objects.filter(titulo="Depois da janela").exists()


def test_o_limite_e_por_pessoa_e_nao_do_quadro_inteiro(entrar_como, categoria):
    joao = entrar_como("joao@exemplo.test", "João")
    maria = entrar_como("maria@exemplo.test", "Maria")

    for numero in range(LIMITE_DE_SUGESTOES):
        _publicar(joao.client, f"Pedido do João {numero}")
    assert _publicar(joao.client, "Mais um do João").status_code == 429

    assert _publicar(maria.client, "O primeiro da Maria").status_code == 302


def test_o_limite_nao_conta_voto_nem_comentario(dentro, sugestao, categoria):
    """ "Leve" quer dizer leve: o limite é de PUBLICAR, e só."""
    for numero in range(LIMITE_DE_SUGESTOES):
        _publicar(dentro.client, f"Pedido {numero}")

    votou = dentro.client.post(reverse("votar", args=[sugestao.id]))
    comentou = dentro.client.post(
        reverse("comentar", args=[sugestao.id]), {"texto": "também quero"}
    )

    assert (votou.status_code, comentou.status_code) == (302, 302)
