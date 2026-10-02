"""A migração conserva o histórico e permite metadados vazios."""

from datetime import date

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_migracao_conserva_linha_antiga_e_aceita_metadados_vazios(equipe, sugestao):
    anterior = [("sugestoes", "0015_resposta_da_equipe")]
    atual = [("sugestoes", "0016_changespec_metadados_opcionais")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(anterior)
        apps_antigas = executor.loader.project_state(anterior).apps
        ChangeSpecAntigo = apps_antigas.get_model("sugestoes", "ChangeSpecAprovado")
        antigo = ChangeSpecAntigo.objects.create(
            sugestao_id=sugestao.pk,
            change_id="legado",
            documento="docs/legado.md",
            aprovado_por="Pessoa",
            aprovado_em=date(2026, 8, 25),
            registrado_por_id=equipe.identidade.pk,
        )
    finally:
        MigrationExecutor(connection).migrate(atual)

    from apps.sugestoes.models import ChangeSpecAprovado

    preservado = ChangeSpecAprovado.objects.get(pk=antigo.pk)
    assert (preservado.documento, preservado.aprovado_por, preservado.aprovado_em) == (
        "docs/legado.md", "Pessoa", date(2026, 8, 25)
    )
    novo = ChangeSpecAprovado.objects.create(
        sugestao_id=sugestao.pk,
        change_id="novo",
        registrado_por_id=equipe.identidade.pk,
    )
    assert (novo.documento, novo.aprovado_por, novo.aprovado_em) == ("", "", None)
    assert preservado.registrado_por_id == novo.registrado_por_id
