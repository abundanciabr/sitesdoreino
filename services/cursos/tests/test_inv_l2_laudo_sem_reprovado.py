"""O laudo tem três decisões, e o serviço recusa uma quarta ("reprovado")."""

from __future__ import annotations

import pytest

from apps.cursos import laudo as parecer
from apps.cursos.models import Laudo
from tests.conftest import forcas_validas, mudanca_valida, notas_validas

pytestmark = pytest.mark.django_db


def test_laudo_decisao_e_exatamente_as_tres_da_lei():
    assert Laudo.Decisao.values == ["aberto", "aberto_com_ajuste", "devolvido"]


def test_o_servico_recusa_reprovado_explicitamente(envio_na_fila, professora):
    with pytest.raises(parecer.LaudoRecusado, match="quarta decisão"):
        parecer.emitir(
            envio_na_fila,
            avaliador=professora,
            papel=Laudo.Papel.PROFESSOR,
            notas=notas_validas(),
            forcas=forcas_validas(),
            mudanca=mudanca_valida(envio_na_fila.aula),
            decisao="reprovado",
            sabe_o_que_fazer_amanha=True,
        )
    assert Laudo.objects.count() == 0
