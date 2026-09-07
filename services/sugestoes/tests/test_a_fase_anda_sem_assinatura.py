# tests/test_a_fase_anda_sem_assinatura.py  # [RECEITA:R5 v1]
"""A fase anda sozinha: `planejado → em_desenvolvimento` não pede assinatura.

Este arquivo ocupa o lugar do `test_inv_changespec_trava_o_desenvolvimento.py`,
que media a trava do EVO-40 nos três degraus. O mantenedor mandou tirar a trava
em 06/09/2026, em pergunta estruturada, junto com a tela de assinatura do Admin
que era a única chave dela — motivo medido na hora: nenhum workflow, nenhum robô
e nenhuma tarefa da fila leem `em_desenvolvimento`, então a trava guardava um
rótulo de roadmap, não um gatilho de máquina.

**Uma lei revogada precisa de guarda tanto quanto a lei precisava.** Sem este
arquivo, os três degraus voltariam sozinhos na primeira sessão que lesse o
`FORMATO-CHANGESPEC.md` §5 e "consertasse" a ausência. Cada teste aqui mede um
degrau que foi embora, pelo mesmo caminho por onde ele recusava antes:

| # | onde estava | como se mede que foi |
|---|---|---|
| 1 | `registrar_mudanca_de_status` (`apps/core/moderacao.py`) | a porta da equipe responde 200 |
| 2 | `Sugestao.save()` | o `manage.py shell` grava |
| 3 | trigger `sugestoes_exige_changespec` no Postgres | `QuerySet.update()` e SQL cru gravam |

**O que NÃO foi revogado, e continua medido aqui:** o registro
`ChangeSpecAprovado` segue append-only nos três degraus (§4 do formato). A
tabela ficou, com tudo que já foi assinado dentro; o que saiu foi a EXIGÊNCIA.
Religar é reaplicar o `reverse_sql` da migration `0014`.
"""

import pytest
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from apps.sugestoes.models import (
    Aviso,
    ChangeSpecAprovado,
    HistoricoStatus,
    OutboxEvent,
    RegistroImutavel,
    Sugestao,
)

pytestmark = pytest.mark.django_db

EM_DESENVOLVIMENTO = Sugestao.Status.EM_DESENVOLVIMENTO
PLANEJADO = Sugestao.Status.PLANEJADO


@pytest.fixture
def planejada(sugestao):
    """Uma ideia em `planejado`, escrita pelo caminho mais cru de propósito."""
    Sugestao.objects.filter(pk=sugestao.pk).update(status=PLANEJADO)
    sugestao.refresh_from_db()
    return sugestao


# ---------------------------------------------------------------------------
# Degrau 1 — a porta por onde a equipe muda o status
# ---------------------------------------------------------------------------


def test_a_equipe_move_para_em_desenvolvimento_sem_assinatura(equipe, planejada):
    resposta = equipe.gestao.mudar_status(
        equipe, planejada, EM_DESENVOLVIMENTO, "começou"
    )

    assert resposta.status_code == 200, resposta.content
    planejada.refresh_from_db()
    assert planejada.status == EM_DESENVOLVIMENTO


def test_a_mudanca_deixa_o_mesmo_rastro_de_sempre(equipe, planejada):
    """Tirar a trava não abriu caminho paralelo: o histórico, o aviso da
    plateia e o evento nascem como em qualquer outra mudança de fase."""
    equipe.gestao.mudar_status(equipe, planejada, EM_DESENVOLVIMENTO, "começou")

    assert HistoricoStatus.objects.count() == 1
    assert Aviso.objects.count() == 1
    assert OutboxEvent.objects.filter(event="sugestao.status-alterado").count() == 1


def test_nao_planejado_continua_exigindo_justificativa(equipe, planejada):
    """A outra recusa do mesmo ponto de estrangulamento continua de pé — o que
    saiu foi a trava do ChangeSpec, e só ela."""
    resposta = equipe.gestao.mudar_status(
        equipe, planejada, Sugestao.Status.NAO_PLANEJADO, ""
    )

    assert resposta.status_code == 422, resposta.content
    planejada.refresh_from_db()
    assert planejada.status == PLANEJADO


# ---------------------------------------------------------------------------
# Degrau 2 — o `save()`, o caminho do `manage.py shell`
# ---------------------------------------------------------------------------


def test_o_save_grava_sem_changespec(planejada):
    planejada.status = EM_DESENVOLVIMENTO
    planejada.save(update_fields=["status"])

    assert Sugestao.objects.get(pk=planejada.pk).status == EM_DESENVOLVIMENTO


# ---------------------------------------------------------------------------
# Degrau 3 — o Postgres, que era o degrau mais fundo
# ---------------------------------------------------------------------------


def test_queryset_update_grava_sem_changespec(planejada):
    Sugestao.objects.filter(pk=planejada.pk).update(status=EM_DESENVOLVIMENTO)

    assert Sugestao.objects.get(pk=planejada.pk).status == EM_DESENVOLVIMENTO


def test_sql_cru_grava_sem_changespec(planejada):
    """O trigger `sugestoes_exige_changespec` não existe mais no banco: se a
    migration `0014` sumir do caminho, é aqui que se descobre."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sugestoes_sugestao SET status = %s WHERE id = %s",
            [EM_DESENVOLVIMENTO, planejada.pk],
        )

    assert Sugestao.objects.get(pk=planejada.pk).status == EM_DESENVOLVIMENTO


# ---------------------------------------------------------------------------
# O que NÃO foi revogado: o registro continua append-only
# ---------------------------------------------------------------------------


def test_o_registro_assinado_continua_imutavel(changespec):
    """§4 do formato, intacto: o que já foi assinado não se edita nem se apaga.

    A trava saiu; a memória do que foi autorizado, não. Sem isto, "tiramos a
    exigência" viraria "apagamos a auditoria" na primeira leitura apressada.
    """
    changespec.aprovado_por = "outra pessoa"
    with pytest.raises(RegistroImutavel):
        changespec.save()

    with pytest.raises(RegistroImutavel):
        changespec.delete()

    with pytest.raises(RegistroImutavel):
        ChangeSpecAprovado.objects.filter(pk=changespec.pk).update(aprovado_por="x")

    assert (
        ChangeSpecAprovado.objects.get(pk=changespec.pk).aprovado_por
        == "Davi (mantenedor)"
    )


def test_o_banco_recusa_editar_e_apagar_o_registro(changespec):
    """O degrau que sobrevive a `psql` — o trigger append-only ficou."""
    for sql in (
        "UPDATE sugestoes_changespecaprovado SET aprovado_por = 'x' WHERE id = %s",
        "DELETE FROM sugestoes_changespecaprovado WHERE id = %s",
    ):
        with pytest.raises(DatabaseError, match="INV-SUG10"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, [changespec.pk])

    assert ChangeSpecAprovado.objects.filter(pk=changespec.pk).exists()
