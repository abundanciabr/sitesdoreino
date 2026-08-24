# tests/test_inv_outbox_transacional.py  # [RECEITA:R5 v1]
"""INV-P6 — o evento nasce na MESMA transação do fato, e uma vez só.

O invariante tem **duas metades**, e provar só uma é o jeito clássico de
acreditar que a outbox está certa quando não está:

1. **Rollback do fato ⇒ nenhum evento sobra.** Se a linha da outbox fosse
   escrita em autocommit (outra conexão, um `xadd` direto na view), ela
   sobreviveria ao rollback e a plataforma inteira passaria a acreditar num
   fato que não aconteceu.
2. **Falha da emissão ⇒ o fato não acontece.** Esta é a metade que quase
   ninguém escreve, e é a que pega o erro mais provável: emitir **depois** do
   `with transaction.atomic()`. Nessa forma o código parece certo, o teste da
   metade 1 continua verde, e mesmo assim a sugestão nasce muda quando a
   emissão falha.

A metade 2 é varrida sobre os QUATRO pontos de emissão, pela jornada real do
clique — nada aqui chama o ORM direto, senão o guarda continuaria verde no dia
em que a view parasse de emitir.

Neste arquivo mora também a idempotência (invariante 3): um fato, um evento —
e `event_id` único no banco, que é o que dá ao consumidor um jeito de deduplicar
a republicação que o transporte at-least-once garante que vai acontecer.
"""

from unittest import mock

import pytest
from django.db import IntegrityError, transaction

from apps.core.moderacao import registrar_mudanca_de_status
from apps.sugestoes import eventos
from apps.sugestoes.models import OutboxEvent, Sugestao, Voto

pytestmark = pytest.mark.django_db


class SaiuDaTransacao(Exception):
    """Só para forçar o rollback lá de fora — não é erro de ninguém."""


# ---------------------------------------------------------------------------
# Metade 1: rollback do fato ⇒ nenhum evento sobra
# ---------------------------------------------------------------------------


def test_rollback_do_fato_leva_o_evento_junto(caixa):
    """A transação de fora desfaz tudo — inclusive a linha da outbox.

    Se `emitir()` escrevesse fora da transação do fato (outra conexão, ou um
    publish direto no Redis dentro da view), o evento sobreviveria a este
    rollback e ficaria afirmando uma mudança de status que nunca existiu.
    """
    sugestao = caixa.publicar()
    OutboxEvent.objects.all().delete()  # zera o `sugestao.criada` da montagem

    with pytest.raises(SaiuDaTransacao):
        with transaction.atomic():
            registrar_mudanca_de_status(
                sugestao=sugestao,
                status_novo=Sugestao.Status.PLANEJADO,
                nota="",
                por=caixa.equipe.identidade,
            )
            # dentro da transação as duas coisas existem, lado a lado
            assert (
                OutboxEvent.objects.filter(event=eventos.STATUS_ALTERADO).count() == 1
            )
            raise SaiuDaTransacao

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE  # o fato voltou atrás
    assert not OutboxEvent.objects.exists()  # e o evento voltou com ele


# ---------------------------------------------------------------------------
# Metade 2: a emissão falha ⇒ o fato não acontece (os QUATRO pontos)
# ---------------------------------------------------------------------------


def _outbox_quebrada():
    """`emitir()` estourando, como estouraria um banco fora do ar no meio."""
    return mock.patch.object(
        eventos, "emitir", side_effect=RuntimeError("outbox indisponível")
    )


def test_sugestao_nao_nasce_muda(caixa):
    with _outbox_quebrada(), pytest.raises(RuntimeError):
        caixa.publicar(titulo="Uma sugestão que não deve existir")

    assert not Sugestao.objects.filter(
        titulo="Uma sugestão que não deve existir"
    ).exists()
    assert not OutboxEvent.objects.filter(event=eventos.CRIADA).exists()


def test_voto_nao_e_contado_se_o_evento_nao_puder_ser_emitido(caixa):
    sugestao = caixa.publicar()

    with _outbox_quebrada(), pytest.raises(RuntimeError):
        caixa.votar(sugestao)

    assert Voto.objects.filter(sugestao=sugestao).count() == 0


def test_desvoto_nao_apaga_a_linha_se_o_evento_nao_puder_ser_emitido(caixa):
    sugestao = caixa.publicar()
    caixa.votar(sugestao)

    with _outbox_quebrada(), pytest.raises(RuntimeError):
        caixa.desvotar(sugestao)

    # o voto continua de pé: desvotar sem avisar ninguém não é meio-desvoto
    assert Voto.objects.filter(sugestao=sugestao).count() == 1


def test_status_nao_muda_se_o_evento_nao_puder_ser_emitido(caixa):
    sugestao = caixa.publicar()

    with _outbox_quebrada(), pytest.raises(RuntimeError):
        caixa.mudar_status(sugestao, Sugestao.Status.IMPLEMENTADO)

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert sugestao.historico.count() == 0  # nem o histórico ficou


# ---------------------------------------------------------------------------
# O degrau estrutural: `emitir()` recusa ser chamado fora de transação
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_de_transacao_e_recusado():
    """Lei 1: em vez de confiar que todo ponto de emissão futuro se lembre do
    `atomic`, a função recusa a escrita.

    Precisa de `transaction=True` para significar alguma coisa: no `django_db`
    padrão TODO teste já roda dentro de um atomic, e a recusa nunca dispararia
    (`armadilhas/057`, §6.5 — a mesma pegadinha, do outro lado).
    """
    with pytest.raises(eventos.EventoForaDaTransacao):
        eventos.emitir(eventos.CRIADA, {"site_id": "x"})

    assert not OutboxEvent.objects.exists()


# ---------------------------------------------------------------------------
# Invariante 3 — um fato, um evento; e `event_id` único
# ---------------------------------------------------------------------------


def test_um_fato_um_evento_o_segundo_clique_nao_duplica(caixa):
    """Votar duas vezes é UM voto (spec §9) — logo, UM evento.

    Emitir no segundo clique faria quem escuta contar dois votos onde há um, e
    o `total_votos` do evento passaria a divergir da contagem do banco.
    """
    sugestao = caixa.publicar()

    caixa.votar(sugestao)
    caixa.votar(sugestao)

    assert Voto.objects.filter(sugestao=sugestao).count() == 1
    assert OutboxEvent.objects.filter(event=eventos.VOTO_ADICIONADO).count() == 1


def test_desvotar_o_que_nao_estava_votado_nao_e_fato_nenhum(caixa):
    sugestao = caixa.publicar()

    caixa.desvotar(sugestao)  # nunca votou

    assert OutboxEvent.objects.filter(event=eventos.VOTO_REMOVIDO).count() == 0


def test_event_id_e_unico_no_banco(caixa):
    """A unicidade é do Postgres, não do Python: é ela que dá ao consumidor
    (EVO-21, R4) um `event_id` em que dá para confiar para deduplicar."""
    sugestao = caixa.publicar()
    primeiro = OutboxEvent.objects.get(event=eventos.CRIADA)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OutboxEvent.objects.create(
                event_id=primeiro.event_id,
                event=eventos.CRIADA,
                payload={"suggestion_id": str(sugestao.pk)},
            )


def test_cada_fato_gera_um_evento_e_nenhum_a_mais(caixa):
    """A jornada inteira: quatro fatos, quatro linhas na outbox — não cinco.

    Comentar, conferir duplicatas e olhar a fila NÃO são fatos que a Caixa
    afirma (nenhum deles tem contrato congelado), e este guarda é o que impede
    um evento de nascer por engano junto com um deles.
    """
    sugestao = caixa.os_quatro_fatos()
    caixa.aluno.client.post(
        f"/sugestoes/{sugestao.id}/comentarios", {"texto": "eu também."}
    )

    assert list(OutboxEvent.objects.order_by("id").values_list("event", flat=True)) == [
        eventos.CRIADA,
        eventos.VOTO_ADICIONADO,
        eventos.VOTO_REMOVIDO,
        eventos.STATUS_ALTERADO,
    ]
