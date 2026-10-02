"""A pergunta de amanhã é opcional e sua resposta fica no laudo."""

import pytest

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import notas_validas

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("resposta", [True, False, None])
def test_resposta_opcional_e_preservada(envio_na_fila, professora, resposta):
    laudo = parecer.emitir(
        envio_na_fila,
        avaliador=professora,
        papel=Laudo.Papel.PROFESSOR,
        notas=notas_validas(),
        forcas=[],
        mudanca=[],
        decisao=Laudo.Decisao.ABERTO,
        sabe_o_que_fazer_amanha=resposta,
    )
    laudo.refresh_from_db()
    assert laudo.sabe_o_que_fazer_amanha is resposta
