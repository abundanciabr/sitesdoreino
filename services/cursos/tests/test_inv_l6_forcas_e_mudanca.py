"""Teste-guarda [INV-CUR-L6]: exatamente três forças, nenhuma da lista de
genéricos; exatamente uma mudança, com a aula onde se aprende.

Lei: `PLANO-CELULA-CURSOS.md` §9. `apps/cursos/laudo.py::validar_forcas` e
`::_validar_mudanca`. A lista de genéricos é fixa: "bonito", "legal", "bom
trabalho", "ficou bom", "parabéns" — comparação por igualdade (strip +
minúsculo), não substring.

Provado por mutação em 05/09/2026: trocar `len(limpas) != 3` por
`len(limpas) < 3` em `validar_forcas` deixa 1 vermelho (quatro forças
passam a ser aceitas); esvaziar `FORCAS_GENERICAS` deixa 1 vermelho (força
genérica passa a ser aceita); trocar `len(itens) != 1` por `not itens` em
`_validar_mudanca` deixa 1 vermelho (duas mudanças passam a ser aceitas, e só
a primeira é gravada em silêncio). Restaurado, os cinco voltam a verde.
"""

from __future__ import annotations

import pytest

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


# ------------------------------------------------------------- as forças
def test_duas_forcas_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="exatamente três forças"):
        _emitir(envio_na_fila, professora, forcas=forcas_validas()[:2])


def test_quatro_forcas_e_recusado(envio_na_fila, professora):
    quatro = forcas_validas() + ["Mais uma força específica sobre o corte."]
    with pytest.raises(parecer.LaudoRecusado, match="exatamente três forças"):
        _emitir(envio_na_fila, professora, forcas=quatro)


def test_forcas_vazias_contam_como_ausentes(envio_na_fila, professora):
    """Um campo em branco não é uma força a menos disfarçada: é ausência."""
    forcas = ["", "", ""]
    with pytest.raises(parecer.LaudoRecusado, match="exatamente três forças"):
        _emitir(envio_na_fila, professora, forcas=forcas)


@pytest.mark.parametrize(
    "generica",
    ["bonito", "Legal", "BOM TRABALHO", "ficou bom", "Parabéns", "  parabéns  "],
)
def test_forca_generica_e_recusada_case_insensitive(
    envio_na_fila, professora, generica
):
    forcas = forcas_validas()
    forcas[1] = generica
    with pytest.raises(parecer.LaudoRecusado, match="genérica"):
        _emitir(envio_na_fila, professora, forcas=forcas)


def test_tres_forcas_especificas_sao_aceitas(envio_na_fila, professora):
    laudo = _emitir(envio_na_fila, professora)
    assert len(laudo.forcas) == 3


# ------------------------------------------------------------ a mudança
def test_zero_mudancas_e_recusado(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="exatamente uma mudança"):
        _emitir(envio_na_fila, professora, mudanca=[])


def test_duas_mudancas_e_recusado(envio_na_fila, professora):
    duas = mudanca_valida(envio_na_fila.aula) * 2
    with pytest.raises(parecer.LaudoRecusado, match="exatamente uma mudança"):
        _emitir(envio_na_fila, professora, mudanca=duas)


def test_mudanca_com_aula_de_outro_curso_e_recusada(envio_na_fila, professora):
    from apps.cursos.models import Aula, Bloco, Curso

    outro_curso = Curso.objects.create(
        site_id="outra-escola", slug="outro", nome="Outro"
    )
    outro_bloco = Bloco.objects.create(curso=outro_curso, ordem=1, letra="A", parte=1)
    aula_de_fora = Aula.objects.create(
        curso=outro_curso,
        bloco=outro_bloco,
        ordem=1,
        numero="E00",
        titulo_exibido="De outro curso",
    )
    mudanca = [{"texto": "Praticar isso.", "aula_id": aula_de_fora.id}]
    with pytest.raises(parecer.LaudoRecusado, match="aula que existe neste curso"):
        _emitir(envio_na_fila, professora, mudanca=mudanca)


def test_mudanca_com_aula_id_nao_numerico_e_recusada(envio_na_fila, professora):
    mudanca = [{"texto": "Praticar isso.", "aula_id": "não-é-um-id"}]
    with pytest.raises(parecer.LaudoRecusado, match="aula que existe neste curso"):
        _emitir(envio_na_fila, professora, mudanca=mudanca)


def test_mudanca_sem_texto_e_recusada(envio_na_fila, professora):
    mudanca = [{"texto": "   ", "aula_id": envio_na_fila.aula.id}]
    with pytest.raises(parecer.LaudoRecusado, match="Escreva o texto da mudança"):
        _emitir(envio_na_fila, professora, mudanca=mudanca)


def test_mudanca_valida_e_gravada_com_o_id_como_texto(envio_na_fila, professora):
    laudo = _emitir(envio_na_fila, professora)
    assert laudo.mudanca["aula_id"] == str(envio_na_fila.aula.id)
    assert laudo.mudanca["texto"]
