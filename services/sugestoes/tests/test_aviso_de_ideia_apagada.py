# tests/test_aviso_de_ideia_apagada.py
"""Apagar a ideia destrói a cópia local dos avisos dela.
O recado lido vive em `/notificacoes`; aqui só se mede a cópia local."""

import pytest

from apps.core.apagamento import apagar_definitivamente
from apps.sugestoes.models import Aviso, Sugestao

pytestmark = pytest.mark.django_db


def test_apagar_destroi_a_copia_local_do_recado(dentro, sugestao):
    Aviso.objects.create(
        destinatario=dentro.identidade,
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.NAO_PLANEJADO,
        nota="Nao entra no roadmap deste semestre.",
    )

    apagar_definitivamente(sugestao)

    assert Aviso.objects.filter(sugestao=sugestao).count() == 0
