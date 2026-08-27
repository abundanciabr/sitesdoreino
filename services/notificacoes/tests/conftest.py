"""Fixtures da caixa central de avisos.

**Nada aqui toca a rede** — esta célula não fala com ninguém: ela ouve o fio e
escreve no próprio banco. O consumidor é exercitado com um Redis DUBLADO (um
objeto em memória com a superfície que a receita R4 usa), porque o que os
guardas medem é a decisão do consumidor, não o Redis.
"""

import uuid

import pytest

SITE = "site-de-teste"
ALGUEM = "idt-pessoa-1"
OUTRA = "idt-pessoa-2"
EQUIPE = "idt-alguem-da-equipe"


def envelope_de_carta(
    *, destinatario_id=ALGUEM, ator_id=EQUIPE, site_id=SITE, origem=None, **parametros
):
    """Um `notificacao.devida.v1` como o relay da Caixa o publica.

    Montado à mão de propósito: o guarda que confere que ele CASA com o contrato
    congelado é `test_inv_carta_casa_com_o_contrato.py`, que lê o schema do
    arquivo. Se esta fixture derivar do contrato, as duas coisas passam a ser a
    mesma e o guarda deixa de medir alguma coisa.
    """
    return {
        "event": "notificacao.devida",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-08-26T22:00:00+00:00",
        "ator_id": ator_id,
        "data": {
            "site_id": site_id,
            "destinatario_id": destinatario_id,
            "assunto": "sugestao.status-alterado",
            "parametros": parametros
            or {
                "suggestion_id": "731",
                "status_anterior": "em_analise",
                "status_novo": "planejado",
            },
            "origem_event_id": origem or str(uuid.uuid4()),
        },
    }


@pytest.fixture
def carta():
    return envelope_de_carta
