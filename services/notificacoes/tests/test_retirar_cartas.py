# tests/test_retirar_cartas.py
"""Retirar a carta cujo fato deixou de existir, sem levar as vizinhas junto.

O CASO REAL, de 31/08/2026: o mantenedor apagou definitivamente ideias da Caixa
de Sugestões e continuou vendo, no perfil dele, o aviso sobre uma delas — um
cartão sem título, com a justificativa da equipe ainda legível ao lado. A
`sugestoes` destruiu o que era dela; a carta mora aqui, e este serviço não
sabia retirar nada: só contar, listar e marcar como lida.

DUAS COISAS PRECISAM SER VERDADE AO MESMO TEMPO, e é por isso que este arquivo
tem duas metades do mesmo tamanho:

1. **A carta órfã some** — a linha, a cópia arquivada e o desconto no contador.
2. **NADA MAIS some.** Um comando que apaga em lote, filtrando por um campo
   dentro de um JSON, é exatamente o tipo de ferramenta que leva vizinho junto
   quando o filtro erra. Carta de outro assunto, de outra pessoa, de outro
   valor: todas continuam de pé, e cada uma tem teste próprio.

O contador tem guarda separado e antigo (`test_inv_contador_bate_com_a_tabela`),
que é quem cobra a igualdade depois de uma jornada inteira. Aqui a medição é
direta: quantas não lidas sumiram, quanto desceu no número.
"""

import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.notificacoes.models import (
    ContadorDeNaoLidos,
    Notificacao,
    NotificacaoArquivada,
)
from apps.notificacoes.services import guardar

pytestmark = pytest.mark.django_db

SUGESTAO = "sugestao.status-alterado"
MATRICULA = "matricula.situacao-alterada"
SITE = "site-de-teste"


def _carta(destinatario, *, assunto=SUGESTAO, parametros=None):
    return guardar(
        site_id=SITE,
        destinatario_id=destinatario,
        ator_id=None,
        assunto=assunto,
        parametros=parametros if parametros is not None else {"suggestion_id": "5"},
        origem_event_id=str(uuid.uuid4()),
    )


def _retirar(valores="5", **extra):
    call_command(
        "retirar_cartas",
        assunto=SUGESTAO,
        parametro="suggestion_id",
        valores=valores,
        verbosity=0,
        **extra,
    )


def _nao_lidos(destinatario) -> int:
    contador = ContadorDeNaoLidos.objects.filter(
        site_id=SITE, destinatario_id=destinatario
    ).first()
    return contador.nao_lidos if contador else 0


# ---------------------------------------------------------------------------
# 1. A carta órfã some
# ---------------------------------------------------------------------------


def test_a_carta_da_ideia_apagada_some():
    _carta("ana")

    _retirar(confirmo=True)

    assert Notificacao.objects.count() == 0


def test_o_contador_desce_junto():
    """Apagar linha sem descontar deixaria o sino com um número que nenhuma
    lista explica — a mesma doença, do outro lado."""
    _carta("ana")
    assert _nao_lidos("ana") == 1

    _retirar(confirmo=True)

    assert _nao_lidos("ana") == 0


def test_carta_ja_lida_some_sem_mexer_no_contador():
    """Ela não estava no número, então descontar por ela cavaria um buraco."""
    lida = _carta("ana")
    outra = _carta("ana")  # noqa: F841 — segura o contador em 1 depois da leitura
    Notificacao.objects.filter(pk=lida.pk).update(lido_em=timezone.now())
    ContadorDeNaoLidos.objects.filter(site_id=SITE, destinatario_id="ana").update(
        nao_lidos=1
    )

    _retirar(valores="5", confirmo=True)

    assert _nao_lidos("ana") == 0


def test_a_copia_arquivada_tambem_some():
    NotificacaoArquivada.objects.create(
        site_id=SITE,
        destinatario_id="ana",
        ator_id=None,
        assunto=SUGESTAO,
        parametros={"suggestion_id": "5"},
        origem_event_id=uuid.uuid4(),
        criado_em=timezone.now(),
        lido_em=timezone.now(),
    )

    _retirar(confirmo=True)

    assert NotificacaoArquivada.objects.count() == 0


def test_apaga_de_todo_mundo_e_nao_so_de_quem_reclamou():
    """A pergunta do mantenedor foi exatamente esta: e as outras pessoas?"""
    _carta("ana")
    _carta("bruno")
    _carta("carla")

    _retirar(confirmo=True)

    assert Notificacao.objects.count() == 0
    assert _nao_lidos("bruno") == 0


# ---------------------------------------------------------------------------
# 2. NADA MAIS some
# ---------------------------------------------------------------------------


def test_carta_de_outro_assunto_fica():
    _carta("ana", assunto=MATRICULA, parametros={"matricula_id": "5"})

    _retirar(confirmo=True)

    assert Notificacao.objects.filter(assunto=MATRICULA).count() == 1


def test_carta_de_outra_ideia_fica():
    _carta("ana", parametros={"suggestion_id": "9"})

    _retirar(valores="5", confirmo=True)

    assert Notificacao.objects.count() == 1


def test_o_contador_de_quem_nao_foi_tocado_fica_de_pe():
    _carta("bruno", parametros={"suggestion_id": "9"})

    _retirar(valores="5", confirmo=True)

    assert _nao_lidos("bruno") == 1


def test_id_como_numero_nao_casa_com_o_json_e_por_isso_ele_viaja_como_texto():
    """O modo de falha SILENCIOSO que este comando podia ter.

    `parametros` é JSON e o id foi gravado como string. Se o comando
    convertesse os valores para inteiro, o filtro não casaria com nada: zero
    linha, nenhum erro, e a limpeza "terminando com sucesso" sem ter feito
    nada. Este teste prova que o texto é o que casa.
    """
    _carta("ana", parametros={"suggestion_id": "5"})

    _retirar(valores=" 5 , ", confirmo=True)

    assert Notificacao.objects.count() == 0


# ---------------------------------------------------------------------------
# 3. As travas
# ---------------------------------------------------------------------------


def test_sem_confirmo_recusa_e_nao_apaga():
    _carta("ana")

    with pytest.raises(CommandError, match="PAROU POR SEGURANCA"):
        _retirar()

    assert Notificacao.objects.count() == 1


def test_simular_conta_e_nao_apaga():
    _carta("ana")

    _retirar(simular=True)

    assert Notificacao.objects.count() == 1
    assert _nao_lidos("ana") == 1


def test_lista_de_valores_vazia_recusa():
    """Apagar sem alvo não é opção: um `--valores` vazio viraria um filtro que
    casa com tudo daquele assunto se alguém "simplificasse" o comando."""
    _carta("ana")

    with pytest.raises(CommandError, match="PAROU POR SEGURANCA"):
        _retirar(valores="  ,  ", confirmo=True)

    assert Notificacao.objects.count() == 1
