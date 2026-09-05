"""Teste-guarda [INV-CUR-L7]: a pergunta de amanhã de manhã. `false` não
envia.

Lei: `PLANO-CELULA-CURSOS.md` §9. Dois cadeados, como [INV-CUR-L1]: o BANCO
recusa a LINHA se `sabe_o_que_fazer_amanha` não for `true` (mesmo por fora do
serviço); o SERVIÇO recusa `False` e `None` (não respondida) com a MESMA
frase — a pergunta não tem uma terceira resposta que "envia mesmo assim".

Provado por mutação em 05/09/2026: trocar `is not True` por `is False` em
`apps/cursos/laudo.py::emitir` deixa 1 vermelho (`None`, "não respondida",
passa a ser aceito e grava a decisão sem a pessoa ter respondido nada).
Restaurado, volta a verde.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import forcas_validas, mudanca_valida, notas_validas

pytestmark = pytest.mark.django_db


def _emitir(envio, professora, **mudancas):
    base = dict(
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio.aula),
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=True,
    )
    base.update(mudancas)
    return parecer.emitir(envio, **base)


# ------------------------------------------------------- o banco, sem serviço
def test_false_estoura_no_banco_mesmo_bypassando_o_servico(envio_na_fila, professora):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Laudo.objects.create(
                envio=envio_na_fila,
                avaliador=professora,
                papel=Laudo.Papel.PROFESSOR,
                decisao=Laudo.Decisao.ABERTO,
                sabe_o_que_fazer_amanha=False,
            )


# --------------------------------------------------------------- o serviço
def test_false_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="não se recusa"):
        _emitir(envio_na_fila, professora, sabe_o_que_fazer_amanha=False)
    assert Laudo.objects.count() == 0


def test_ausente_none_tambem_e_recusado(envio_na_fila, professora):
    """Caixa não marcada: o formulário nunca manda `false`, manda ausência —
    e ausência é lida como "não respondida", a MESMA recusa de `false`."""
    with pytest.raises(parecer.LaudoRecusado, match="não se recusa"):
        _emitir(envio_na_fila, professora, sabe_o_que_fazer_amanha=None)
    assert Laudo.objects.count() == 0


def test_true_e_aceito_e_e_o_unico_valor_gravado(envio_na_fila, professora):
    laudo = _emitir(envio_na_fila, professora, sabe_o_que_fazer_amanha=True)
    assert laudo.sabe_o_que_fazer_amanha is True
