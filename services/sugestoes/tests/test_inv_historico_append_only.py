# tests/test_inv_historico_append_only.py  # [RECEITA:R5 v1]
"""INV-SUG02 — `HistoricoStatus` é append-only.

Spec §8: nenhuma linha é editada ou apagada depois de criada; correção é um
registro NOVO. O invariante é imposto em três degraus (Lei 1), e cada degrau
tem o seu teste aqui — porque um degrau sozinho tem porta dos fundos:

1. `save()` na instância        — pega `obj.campo = x; obj.save()`
2. `AppendOnlyQuerySet`          — pega `.update()`, `.bulk_update()`, `.delete()`
   ([armadilhas/023] `QuerySet.update()` NÃO passa por `Model.save()`)
3. **trigger no Postgres**       — pega SQL cru, `psql` e o collector de CASCADE
   do Django, que emite `DELETE` sem passar por `QuerySet.delete()`

O degrau 3 é o que transforma "convenção" em "impossibilidade física": nenhum
código futuro desta célula precisa conhecer a classe para ficar preso à regra.
"""

import pytest
from django.db import DatabaseError, connection, models, transaction
from django.db.models import ProtectedError

from apps.sugestoes.models import HistoricoStatus, RegistroImutavel, Sugestao

pytestmark = pytest.mark.django_db


@pytest.fixture
def registro(sugestao, aluno):
    return HistoricoStatus.objects.create(
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        nota="entra na próxima trilha",
        alterado_por=aluno,
    )


# --------------------------------------------------------------------------
# Degrau 1 — a instância
# --------------------------------------------------------------------------
def test_save_de_linha_ja_existente_e_recusado(registro):
    recarregado = HistoricoStatus.objects.get(pk=registro.pk)
    recarregado.nota = "reescrevendo a história"

    with pytest.raises(RegistroImutavel):
        recarregado.save()

    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_delete_da_instancia_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        registro.delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# Degrau 2 — o QuerySet (a porta dos fundos da armadilhas/023)
# --------------------------------------------------------------------------
def test_update_em_massa_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.filter(pk=registro.pk).update(nota="via update()")
    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_bulk_update_e_recusado(registro):
    registro.nota = "via bulk_update()"
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.bulk_update([registro], ["nota"])


def test_delete_em_massa_e_recusado(registro):
    with pytest.raises(RegistroImutavel):
        HistoricoStatus.objects.filter(pk=registro.pk).delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


def test_apagar_a_sugestao_nao_leva_o_historico_junto(registro, sugestao):
    """CASCADE apagaria o histórico por dentro do collector do Django, que
    emite `DELETE` direto e não passa pelo `QuerySet.delete()`. Por isso a FK
    é `PROTECT` — divergência deliberada da §6 da spec, a favor da §8."""
    with pytest.raises(ProtectedError):
        sugestao.delete()
    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# Degrau 3 — o banco, que não conhece nem o ORM nem esta classe
# --------------------------------------------------------------------------
def test_update_em_sql_cru_e_recusado_pelo_postgres(registro):
    with pytest.raises(DatabaseError, match="INV-SUG02"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE sugestoes_historicostatus SET nota = 'sql cru' "
                    "WHERE id = %s",
                    [registro.pk],
                )

    assert HistoricoStatus.objects.get(pk=registro.pk).nota == (
        "entra na próxima trilha"
    )


def test_delete_em_sql_cru_e_recusado_pelo_postgres(registro):
    with pytest.raises(DatabaseError, match="INV-SUG02"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM sugestoes_historicostatus WHERE id = %s",
                    [registro.pk],
                )

    assert HistoricoStatus.objects.filter(pk=registro.pk).exists()


# --------------------------------------------------------------------------
# O que o invariante NÃO proíbe: acrescentar.
# --------------------------------------------------------------------------
def test_correcao_e_registro_novo_e_o_anterior_continua_de_pe(registro, aluno):
    HistoricoStatus.objects.create(
        sugestao=registro.sugestao,
        status_anterior=Sugestao.Status.PLANEJADO,
        status_novo=Sugestao.Status.EM_ANALISE,
        nota="voltou: o ChangeSpec não foi aprovado",
        alterado_por=aluno,
    )
    notas = list(
        HistoricoStatus.objects.filter(sugestao=registro.sugestao).values_list(
            "nota", flat=True
        )
    )
    assert notas == [
        "entra na próxima trilha",
        "voltou: o ChangeSpec não foi aprovado",
    ]


def test_o_gerente_do_historico_recusa_escrita_e_nao_e_o_padrao_do_django():
    """Guarda contra a regressão silenciosa: alguém reescreve
    `objects = models.Manager()` e os degraus 1 e 2 evaporam sem erro nenhum."""
    queryset = type(HistoricoStatus.objects.all())
    assert queryset.update is not models.QuerySet.update
    assert queryset.delete is not models.QuerySet.delete
