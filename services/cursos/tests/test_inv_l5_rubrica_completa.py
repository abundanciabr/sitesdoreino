"""Teste-guarda [INV-CUR-L5]: a rubrica completa, com uma frase por nota,
antes de qualquer campo livre; nota sem frase é 422.

Lei: `PLANO-CELULA-CURSOS.md` §9. `apps/cursos/laudo.py::_validar_rubrica`
reutiliza `envio.py::criterios_de` (a MESMA ordem alfabética que o checkpoint
do aluno já usa) e recusa, critério por critério, o primeiro que faltar nota
válida ou frase.

Provado por mutação em 05/09/2026: trocar `if not frase: raise` por `pass` em
`_validar_rubrica` deixa 1 vermelho (nota sem frase passa a ser aceita e
gravada); trocar a checagem de `nota` por `nota is not None` (aceitando
qualquer coisa não-`None`, inclusive fora da escala) deixa 2 vermelhos.
Restaurado, os três voltam a verde.
"""

from __future__ import annotations

import pytest

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import CRITERIO_1, CRITERIO_2, forcas_validas, mudanca_valida

pytestmark = pytest.mark.django_db


def _emitir(envio, professora, notas):
    return parecer.emitir(
        envio,
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas,
        forcas=forcas_validas(),
        mudanca=mudanca_valida(envio.aula),
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=True,
    )


def test_criterio_ausente_e_recusado(envio_na_fila, professora):
    notas = {CRITERIO_1: {"nota": 4, "frase": "Boa execução."}}  # falta o 2º
    with pytest.raises(parecer.LaudoRecusado, match="rubrica está incompleta"):
        _emitir(envio_na_fila, professora, notas)


def test_nota_fora_da_escala_e_recusada(envio_na_fila, professora):
    notas = {
        CRITERIO_1: {"nota": 99, "frase": "Fora da escala."},
        CRITERIO_2: {"nota": 3, "frase": "Ok."},
    }
    with pytest.raises(parecer.LaudoRecusado, match="rubrica está incompleta"):
        _emitir(envio_na_fila, professora, notas)


def test_nota_booleana_e_recusada(envio_na_fila, professora):
    """`bool` é `int` em Python: `True` não pode colar como nota válida."""
    notas = {
        CRITERIO_1: {"nota": True, "frase": "Não é nota de verdade."},
        CRITERIO_2: {"nota": 3, "frase": "Ok."},
    }
    with pytest.raises(parecer.LaudoRecusado, match="rubrica está incompleta"):
        _emitir(envio_na_fila, professora, notas)


def test_nota_sem_frase_e_recusada(envio_na_fila, professora):
    notas = {
        CRITERIO_1: {"nota": 4, "frase": ""},
        CRITERIO_2: {"nota": 3, "frase": "Ok."},
    }
    with pytest.raises(parecer.LaudoRecusado, match="nota sem frase"):
        _emitir(envio_na_fila, professora, notas)


def test_frase_so_com_espaco_conta_como_ausente(envio_na_fila, professora):
    notas = {
        CRITERIO_1: {"nota": 4, "frase": "   "},
        CRITERIO_2: {"nota": 3, "frase": "Ok."},
    }
    with pytest.raises(parecer.LaudoRecusado, match="nota sem frase"):
        _emitir(envio_na_fila, professora, notas)


def test_rubrica_completa_e_valida_e_aceita(envio_na_fila, professora):
    notas = {
        CRITERIO_1: {"nota": 4, "frase": "As bordas ficaram consistentes."},
        CRITERIO_2: {"nota": 5, "frase": "A proporção bateu com a referência."},
    }
    laudo = _emitir(envio_na_fila, professora, notas)
    assert laudo.notas == notas


def test_criterio_desconhecido_no_envio_e_ignorado_silenciosamente(
    envio_na_fila, professora
):
    """Chave extra que não é critério nenhum não vaza para o laudo gravado:
    só os critérios da escala do instrumento entram."""
    notas = {
        CRITERIO_1: {"nota": 4, "frase": "As bordas ficaram consistentes."},
        CRITERIO_2: {"nota": 5, "frase": "A proporção bateu com a referência."},
        "Um critério que não existe": {"nota": 1, "frase": "x"},
    }
    laudo = _emitir(envio_na_fila, professora, notas)
    assert "Um critério que não existe" not in laudo.notas
