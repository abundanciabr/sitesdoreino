"""O arquivamento tira do caminho quente o que já foi lido — e só isso.

Lei: `DECISAO-notificacoes` §5.2 (*"arquivamento desde o começo — notificação
lida e velha sai do caminho quente"*). A exigência é da gênese, não de uma fase
futura: uma tabela que só cresce fica lenta exatamente quando o produto der
certo, e aí já é tarde para desenhar o arquivo.

O guarda mais importante daqui é o do **não lido**: arquivar algo que a pessoa
ainda não leu some com um aviso da cara dela, e ela nunca fica sabendo que
existiu.
"""

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.notificacoes.handlers import ao_notificacao_devida
from apps.notificacoes.models import (
    ContadorDeNaoLidos,
    Notificacao,
    NotificacaoArquivada,
)
from apps.notificacoes.services import arquivar_lidas
from tests.conftest import ALGUEM, SITE, envelope_de_carta

pytestmark = pytest.mark.django_db


def _guardar(**kwargs):
    envelope = envelope_de_carta(**kwargs)
    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])
    return Notificacao.objects.order_by("-id").first()


def _marcar_lida(notificacao, *, dias_atras: int):
    notificacao.lido_em = timezone.now() - timezone.timedelta(days=dias_atras)
    notificacao.save(update_fields=["lido_em"])


def test_lida_e_velha_sai_da_caixa_quente_e_vai_para_o_arquivo():
    velha = _guardar()
    _marcar_lida(velha, dias_atras=45)

    assert arquivar_lidas(dias=30) == 1

    assert not Notificacao.objects.filter(pk=velha.pk).exists()
    guardada = NotificacaoArquivada.objects.get()
    assert guardada.assunto == velha.assunto
    assert guardada.parametros == velha.parametros
    assert guardada.origem_event_id == velha.origem_event_id


def test_nao_lida_NUNCA_e_arquivada_por_mais_velha_que_seja():
    """O guarda que impede o pior estrago possível desta função."""
    antiga = _guardar()
    Notificacao.objects.filter(pk=antiga.pk).update(
        criado_em=timezone.now() - timezone.timedelta(days=999)
    )

    assert arquivar_lidas(dias=1) == 0
    assert Notificacao.objects.filter(pk=antiga.pk).exists()


def test_lida_recente_continua_na_caixa():
    recente = _guardar()
    _marcar_lida(recente, dias_atras=3)

    assert arquivar_lidas(dias=30) == 0
    assert Notificacao.objects.filter(pk=recente.pk).exists()


def test_arquivar_nao_mexe_no_contador():
    """Quem sai da conta é o LIDO, no momento da leitura — não o arquivado.

    Se o arquivamento descontasse também, descontaria duas vezes: o contador
    andaria para baixo sozinho, e um contador baixo demais some com avisos da
    cara da pessoa sem nada indicando o que houve.
    """
    velha = _guardar()
    _marcar_lida(velha, dias_atras=45)
    antes = ContadorDeNaoLidos.objects.get(
        site_id=SITE, destinatario_id=ALGUEM
    ).nao_lidos

    arquivar_lidas(dias=30)

    depois = ContadorDeNaoLidos.objects.get(
        site_id=SITE, destinatario_id=ALGUEM
    ).nao_lidos
    assert depois == antes


def test_o_comando_se_recusa_a_escrever_sem_confirmo():
    velha = _guardar()
    _marcar_lida(velha, dias_atras=45)

    with pytest.raises(CommandError):
        call_command("arquivar_lidas", "--dias", "30")

    assert Notificacao.objects.filter(pk=velha.pk).exists()


def test_simular_conta_sem_mover_nada():
    velha = _guardar()
    _marcar_lida(velha, dias_atras=45)

    call_command("arquivar_lidas", "--dias", "30", "--simular")

    assert Notificacao.objects.filter(pk=velha.pk).exists()
    assert not NotificacaoArquivada.objects.exists()
