"""Teste-guarda [INV-CUR-L1]: nenhum laudo devolvido sem `data_de_retorno` ≥
amanhã.

Lei: `PLANO-CELULA-CURSOS.md` §9. Dois cadeados, como o prazo do envio
([INV-CUR-L3]) já ensinou: o BANCO garante a metade "não é nulo" (e a
metade simétrica: nenhuma OUTRA decisão pode ter data), sem consultar
relógio nenhum; o SERVIÇO garante a metade "amanhã em diante", que depende
da hora em que a linha é escrita.

Provado por mutação em 05/09/2026: comentar o `if data_de_retorno is None or
data_de_retorno < amanha: raise` de `apps/cursos/laudo.py::emitir` deixa 3
vermelhos (hoje passa, ontem passa, e o guarda de `test_laudo.py` que espera
a recusa); restaurado, os três voltam a verde.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

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
        decisao=Laudo.Decisao.DEVOLVIDO,
        sabe_o_que_fazer_amanha=True,
    )
    base.update(mudancas)
    return parecer.emitir(envio, **base)


# ------------------------------------------------- o banco, sem relógio
def test_devolvido_sem_data_estoura_no_banco(envio_na_fila, professora):
    """Bypassando o serviço: mesmo direto no modelo, a linha não existe."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Laudo.objects.create(
                envio=envio_na_fila,
                avaliador=professora,
                papel=Laudo.Papel.PROFESSOR,
                decisao=Laudo.Decisao.DEVOLVIDO,
                data_de_retorno=None,
                sabe_o_que_fazer_amanha=True,
            )


def test_aberto_com_data_preenchida_tambem_estoura_no_banco(envio_na_fila, professora):
    """A metade simétrica: uma decisão que NÃO é devolvido não pode ter data —
    senão a coluna deixaria de dizer, sozinha, "isto foi devolvido"."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Laudo.objects.create(
                envio=envio_na_fila,
                avaliador=professora,
                papel=Laudo.Papel.PROFESSOR,
                decisao=Laudo.Decisao.ABERTO,
                data_de_retorno=dt.date.today() + dt.timedelta(days=1),
                sabe_o_que_fazer_amanha=True,
            )


# ------------------------------------------------- o serviço, com relógio
def test_servico_recusa_data_de_hoje(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="amanhã em diante"):
        _emitir(envio_na_fila, professora, data_de_retorno=dt.date.today())


def test_servico_recusa_data_de_ontem(envio_na_fila, professora):
    ontem = dt.date.today() - dt.timedelta(days=1)
    with pytest.raises(parecer.LaudoRecusado, match="amanhã em diante"):
        _emitir(envio_na_fila, professora, data_de_retorno=ontem)


def test_servico_recusa_data_ausente(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="amanhã em diante"):
        _emitir(envio_na_fila, professora, data_de_retorno=None)


def test_servico_aceita_amanha_no_fuso_de_sao_paulo(envio_na_fila, professora):
    amanha = timezone.localdate() + dt.timedelta(days=1)
    laudo = _emitir(envio_na_fila, professora, data_de_retorno=amanha)
    assert laudo.data_de_retorno == amanha


def test_servico_aceita_uma_data_bem_mais_a_frente(envio_na_fila, professora):
    daqui_a_10_dias = timezone.localdate() + dt.timedelta(days=10)
    laudo = _emitir(envio_na_fila, professora, data_de_retorno=daqui_a_10_dias)
    assert laudo.data_de_retorno == daqui_a_10_dias
