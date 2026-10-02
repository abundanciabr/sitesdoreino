# tests/test_a_carta_vira_aviso.py  # [RECEITA:R5 v1]
"""O que esta célula ACEITA do fio vira aviso com todos os campos da carta.

A `sugestoes` publica `notificacao.devida` v1; aqui se prova que a caixa central
guarda cada campo que a carta traz, e que carta sem ator (fato de máquina) é
guardada como sem ator.
"""

import pytest

from apps.notificacoes.handlers import ao_notificacao_devida
from apps.notificacoes.models import Notificacao
from tests.conftest import envelope_de_carta

pytestmark = pytest.mark.django_db


def test_a_celula_guarda_todos_os_campos_que_o_contrato_promete():
    """Campo prometido e ignorado é campo que some sem ninguém notar."""
    envelope = envelope_de_carta()
    dados = envelope["data"]

    ao_notificacao_devida(dados, ator_id=envelope["ator_id"])

    guardada = Notificacao.objects.get()
    assert guardada.site_id == dados["site_id"]
    assert guardada.destinatario_id == dados["destinatario_id"]
    assert guardada.assunto == dados["assunto"]
    assert guardada.parametros == dados["parametros"]
    assert str(guardada.origem_event_id) == dados["origem_event_id"]
    assert guardada.ator_id == envelope["ator_id"]
    assert guardada.lido_em is None, "aviso nasce não lido"


def test_carta_sem_ator_e_aceita_e_guardada_como_sem_ator():
    """O contrato declara `ator_id` nulável — fato de máquina não tem gente.

    Guardar `""` em vez de `None` criaria duas formas de "não sei", e dois
    pedaços de código as consultariam de jeitos diferentes.
    """
    envelope = envelope_de_carta(ator_id=None)

    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])

    assert Notificacao.objects.get().ator_id is None
