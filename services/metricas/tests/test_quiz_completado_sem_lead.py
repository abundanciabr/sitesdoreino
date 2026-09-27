"""Teste-guarda: o livro de fatos guarda `quiz.completado` sem o bloco `lead`.

Decisão 6 do mantenedor (sessão de 26/09/2026, "Limpar na entrada e
expurgar", registro `painel/registros/20260927-013`): o contrato
`quiz.completado.v1` continua levando `data.lead` (e-mail, nome, telefone),
mas a `metricas` descarta esse bloco ANTES de guardar o fato, e a migração
`0004_quiz_completado_sem_lead` apaga `lead` dos fatos que já estavam
guardados. O que estes guardas protegem:

1. **Na entrada**, `processar` guarda o fato do quiz sem `lead` e com todos os
   outros campos intactos.
2. **Nem o evento morto leva o e-mail**: um `quiz.completado` com envelope
   ruim vira `EventoMorto` já sem `lead`, porque a limpeza vem antes da
   recepção.
3. **O expurgo** apaga `lead` só dos fatos `quiz.completado`, não toca outro
   assunto nem outro campo, e devolve a trava do banco ligada ao terminar.
"""

from __future__ import annotations

import json
import uuid
from importlib import import_module

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.fatos.management.commands.consume_eventos import processar
from apps.fatos.models import Evento, EventoMorto
from apps.fatos.recepcao import GUARDADO, MORTO

pytestmark = pytest.mark.django_db

QUANDO = "2026-09-26T18:00:00+00:00"
EMAIL = "pessoa@exemplo.com"
MIGRACAO = "0004_quiz_completado_sem_lead"

DADOS_SEM_LEAD = {
    "site_id": "meshcraft",
    "quiz_slug": "perfil-de-lideranca",
    "result_key": "pastor",
    "score": 42,
    "version_key": "v-roxa",
    "utm": {"utm_source": "instagram"},
}
LEAD = {"email": EMAIL, "name": "Pessoa de Teste", "phone": "+5511999990000"}


def envelope_do_quiz(dados: dict) -> str:
    return json.dumps(
        {
            "event": "quiz.completado",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": QUANDO,
            "data": dados,
        }
    )


# ------------------------------------------------------------ limpeza na entrada


def test_quiz_completado_com_lead_e_guardado_sem_lead() -> None:
    # guarda: services/metricas/apps/fatos/management/commands/consume_eventos.py:207
    desfecho = processar(
        envelope_do_quiz({**DADOS_SEM_LEAD, "lead": LEAD}).encode("utf-8")
    )

    assert desfecho == GUARDADO
    evento = Evento.objects.get()
    assert "lead" not in evento.dados, (
        "o livro de fatos guardou o bloco `lead` do quiz: e-mail, nome e "
        "telefone não podem entrar no livro (decisão 6 do mantenedor, LGPD)"
    )
    assert EMAIL not in json.dumps(evento.dados)


def test_os_demais_campos_do_quiz_chegam_intactos() -> None:
    processar(envelope_do_quiz({**DADOS_SEM_LEAD, "lead": LEAD}).encode("utf-8"))

    evento = Evento.objects.get()
    assert evento.dados == DADOS_SEM_LEAD
    assert evento.tipo == "quiz.completado"
    assert evento.site_id == "meshcraft"


def test_quiz_morto_nao_guarda_o_email_do_lead() -> None:
    """Sem `site_id` o envelope vira `EventoMorto`, e o corpo guardado para
    inspeção já vem sem `lead`: a limpeza acontece antes da recepção."""
    dados = {k: v for k, v in DADOS_SEM_LEAD.items() if k != "site_id"}

    desfecho = processar(envelope_do_quiz({**dados, "lead": LEAD}).encode("utf-8"))

    assert desfecho == MORTO
    morto = EventoMorto.objects.get()
    assert EMAIL not in morto.corpo
    assert json.loads(morto.corpo)["data"] == dados


def test_outro_assunto_com_campo_lead_nao_e_mexido() -> None:
    """A limpeza é do `quiz.completado`, nomeado na decisão. Outro assunto
    fora do conjunto protegido continua guardado como veio."""
    corpo = json.dumps(
        {
            "event": "sugestao.criada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": QUANDO,
            "data": {"site_id": "meshcraft", "lead": "lead-opaco-1"},
        }
    )

    assert processar(corpo.encode("utf-8")) == GUARDADO
    assert Evento.objects.get().dados["lead"] == "lead-opaco-1"


# --------------------------------------------------------- expurgo dos guardados


def guardar_como_antes(tipo: str, dados: dict) -> Evento:
    """Grava um fato do jeito que o livro gravava antes da limpeza na entrada."""
    evento = Evento(
        event_id=uuid.uuid4(),
        tipo=tipo,
        versao=1,
        site_id="meshcraft",
        ocorrido_em="2026-09-20T12:00:00+00:00",
        dia="2026-09-20",
        dados=dados,
    )
    evento.save()
    return evento


def expurgar() -> None:
    """Roda a função da migração sobre o estado histórico dela, como o
    `migrate` roda em produção."""
    migracao = import_module(f"apps.fatos.migrations.{MIGRACAO}")
    estado = MigrationExecutor(connection).loader.project_state(("fatos", MIGRACAO))
    with connection.schema_editor() as editor:
        migracao.expurgar_lead_do_quiz(estado.apps, editor)


def test_migracao_apaga_lead_dos_fatos_de_quiz_ja_guardados() -> None:
    # guarda: services/metricas/apps/fatos/migrations/0004_quiz_completado_sem_lead.py:46
    antigo = guardar_como_antes("quiz.completado", {**DADOS_SEM_LEAD, "lead": LEAD})

    expurgar()

    antigo = Evento.objects.get(pk=antigo.pk)
    assert antigo.dados == DADOS_SEM_LEAD


def test_migracao_nao_toca_outros_assuntos_nem_quiz_sem_lead() -> None:
    outro = guardar_como_antes("sugestao.criada", {"site_id": "meshcraft", "lead": "x"})
    quiz_limpo = guardar_como_antes("quiz.completado", dict(DADOS_SEM_LEAD))

    expurgar()

    assert Evento.objects.get(pk=outro.pk).dados == {
        "site_id": "meshcraft",
        "lead": "x",
    }
    assert Evento.objects.get(pk=quiz_limpo.pk).dados == DADOS_SEM_LEAD


def test_a_trava_do_banco_volta_ligada_depois_do_expurgo() -> None:
    """O expurgo desliga o gatilho de UPDATE só dentro da própria transação.
    Terminado, um UPDATE qualquer no livro volta a ser recusado pelo banco."""
    if connection.vendor != "postgresql":
        pytest.skip("a trava do banco só existe no Postgres (0002_a_trava_do_banco)")
    evento = guardar_como_antes("quiz.completado", {**DADOS_SEM_LEAD, "lead": LEAD})

    expurgar()

    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE fatos_evento SET site_id = 'outro' WHERE id = %s", [evento.pk]
            )
