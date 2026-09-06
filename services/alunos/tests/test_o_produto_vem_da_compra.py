"""A matrícula que nasce de uma COMPRA passa a dizer de qual produto ela é.

Degrau 4 da escada do Rito de Contrato #1209, e o fechamento de
[INV-ALU-C1] na porta que faltava. A porta da liberação já exigia o produto
(#1178); esta é a da compra, e a lei
(`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` §4) diz que ela é a
PRINCIPAL: é por ela que entra quem paga.

**O caso que decide se este arquivo presta é o segundo**, não o primeiro. Que a
matrícula grave o produto quando ele vem é o caminho feliz. O que custa dinheiro
de verdade é a compra que chega SEM o produto: alguém pagou, e a resposta não
pode ser nem recusar (o dinheiro dela não depende de um campo que o emissor
esqueceu) nem adivinhar um produto padrão (o palpite faria a escolha errada
parecer escolha, e só apareceria quando a pessoa abrisse a sala errada).
"""

import logging

import pytest

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db

SITE = "site-da-escola"
PRODUTO = "11111111-1111-4111-8111-111111111111"


def _aviso_da_compra(*, pedido: str, produto: str | None) -> dict:
    """O campo `data` do evento, na forma exata do contrato congelado."""
    dados = {
        "site_id": SITE,
        "payment_id": f"pay-{pedido}",
        "order_id": pedido,
        "amount_cents": 19700,
        "method": "pix",
        "mp_payment_id": f"mp-{pedido}",
        "customer": {"email": "aluna@exemplo.com.br", "name": "Aluna Exemplo"},
    }
    if produto is not None:
        dados["product_id"] = produto
    return dados


def test_a_compra_com_produto_grava_o_produto_na_matricula():
    ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-1", produto=PRODUTO))

    matricula = Matricula.objects.get(order_id="ped-1")
    assert matricula.product_id == PRODUTO
    assert matricula.status == Matricula.STATUS_ATIVA


def test_a_compra_sem_produto_ainda_matricula_porque_a_pessoa_pagou(caplog):
    """Recusar seria pior: o dinheiro dela não depende de um campo esquecido."""
    with caplog.at_level(logging.WARNING):
        ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-2", produto=None))

    matricula = Matricula.objects.get(order_id="ped-2")
    assert matricula.status == Matricula.STATUS_ATIVA
    assert matricula.product_id == ""


def test_a_compra_sem_produto_deixa_aviso_com_o_pedido_dentro(caplog):
    """O aviso serve para achar A PESSOA depois, e por isso cita o pedido.

    Sem o número do pedido no texto, a linha de log vira ruído: quem investiga
    "por que fulano não entra na sala" não tem por onde começar.
    """
    with caplog.at_level(logging.WARNING):
        ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-3", produto=None))

    (aviso,) = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert "ped-3" in aviso.getMessage()
    assert "INV-ALU-C1" in aviso.getMessage()


def test_produto_em_branco_e_o_mesmo_que_ausente(caplog):
    """String vazia não é "sei que é nada": o contrato manda OMITIR a chave, e
    um emissor que mandar vazio não pode produzir uma matrícula diferente da de
    quem omitiu."""
    with caplog.at_level(logging.WARNING):
        ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-4", produto=""))

    assert Matricula.objects.get(order_id="ped-4").product_id == ""
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_produto_nulo_nao_vira_a_palavra_none_dentro_da_matricula(caplog):
    """Este teste existe porque uma sabotagem NÃO mordeu, e o motivo importa.

    Trocar `data.get("product_id") or ""` por `data.get("product_id", "")` passa
    em todos os testes acima: com a chave ausente ou vazia, os dois devolvem a
    mesma coisa. Onde eles divergem é com `null` (que o JSON permite escrever e
    um emissor descuidado manda): o segundo devolveria `None`, e `str(None)`
    grava a palavra **"None"** como se fosse o id de um produto. A matrícula
    passaria por qualquer conferência de forma e apontaria para um curso que não
    existe.

    Em vez de apagar a peneira que a sabotagem expôs, ela é medida aqui, onde
    carrega significado.
    """
    with caplog.at_level(logging.WARNING):
        ao_pagamento_aprovado(
            _aviso_da_compra(pedido="ped-7", produto=None) | {"product_id": None}
        )

    matricula = Matricula.objects.get(order_id="ped-7")
    assert matricula.product_id == ""
    assert matricula.product_id != "None"


def test_a_compra_com_produto_nao_deixa_aviso_nenhum(caplog):
    """O aviso é para o caso ruim. Se ele saísse sempre, ninguém o leria."""
    with caplog.at_level(logging.WARNING):
        ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-5", produto=PRODUTO))

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


def test_reentrega_do_mesmo_pedido_nao_duplica_nem_apaga_o_produto():
    """A fila de eventos entrega pelo menos uma vez ([INV-P5]). A segunda
    entrega não pode criar matrícula nova nem zerar o produto da primeira."""
    ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-6", produto=PRODUTO))
    ao_pagamento_aprovado(_aviso_da_compra(pedido="ped-6", produto=PRODUTO))

    assert Matricula.objects.filter(order_id="ped-6").count() == 1
    assert Matricula.objects.get(order_id="ped-6").product_id == PRODUTO
