"""Teste-guarda: o `EventoMorto` de `quiz.completado` também perde o `lead`.

Decisão 6 do mantenedor (sessão de 26/09/2026, "Limpar na entrada e
expurgar", registro `painel/registros/20260927-013`, TAR-819). A TAR-800
(PR #2178) limpou a tabela `Evento` (migração `0004_quiz_completado_sem_lead`)
e passou a descartar `lead` na entrada, inclusive para `EventoMorto` novo
(`recepcao._matar` só grava o corpo cru, mas a limpeza acontece antes da
recepção). Faltam os `EventoMorto` de `quiz.completado` gravados ANTES de
27/09/2026 03h37 UTC: o campo `corpo` (texto cru) pode ter `data.lead` com
e-mail, nome e telefone. Esta migração (`0005_quiz_morto_sem_lead`) apaga
`lead` do envelope guardado em `corpo`, sem tocar mais nada.

O que estes guardas protegem:

1. **O morto de quiz com `lead`** perde só o `lead`, e os demais campos do
   envelope, `motivo`, `estado` e `recebido_em` continuam intactos.
2. **Outro assunto com uma chave `lead`** no corpo fica intacto: o expurgo é
   nomeado para `quiz.completado`, igual à decisão 6.
3. **Corpo que não é JSON** fica intacto e a migração não estoura: a causa
   mais comum de um `EventoMorto` é justamente não ser JSON válido.
4. **Morto de quiz sem `lead`** fica byte a byte igual: sem o campo, não há o
   que expurgar, e a linha não é sequer escrita de novo.
5. **`tipo_declarado` vazio com envelope de quiz** também é limpo: o envelope
   pode ter morrido antes de `recepcao.receber` conseguir ler `event` (corpo
   que não é um dict JSON, por exemplo), e o quiz ainda pode estar ali dentro.
"""

from __future__ import annotations

import json
import uuid
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.fatos.models import EventoMorto

pytestmark = pytest.mark.django_db

QUANDO = "2026-09-20T18:00:00+00:00"
EMAIL = "pessoa@exemplo.com"
MIGRACAO = "0005_quiz_morto_sem_lead"

DADOS_SEM_LEAD = {
    "quiz_slug": "perfil-de-lideranca",
    "result_key": "pastor",
    "score": 42,
}
LEAD = {"email": EMAIL, "name": "Pessoa de Teste", "phone": "+5511999990000"}


def envelope_do_quiz(dados: dict, event_id: str | None = None) -> str:
    return json.dumps(
        {
            "event": "quiz.completado",
            "version": 1,
            "event_id": event_id or str(uuid.uuid4()),
            "occurred_at": QUANDO,
            "data": dados,
        }
    )


def guardar_morto(
    corpo: str,
    *,
    tipo_declarado: str = "quiz.completado",
    motivo: str = "faltam chaves do envelope canônico: site_id",
) -> EventoMorto:
    """Grava um `EventoMorto` do jeito que a recepção gravava antes do
    expurgo, com o corpo cru exatamente como chegou."""
    return EventoMorto.objects.create(
        corpo=corpo,
        motivo=motivo,
        tipo_declarado=tipo_declarado,
        event_id_declarado="",
    )


def expurgar() -> None:
    """Roda a função da migração sobre o estado histórico dela, como o
    `migrate` roda em produção. `EventoMorto` não tem gatilho no banco (só
    `fatos_evento` tem), então a função não precisa do `schema_editor` de
    verdade: passar `None` evita um `connection.schema_editor()` que o SQLite
    recusa dentro da transação de teste, e no Postgres da CI o argumento seria
    igualmente ignorado."""
    migracao = import_module(f"apps.fatos.migrations.{MIGRACAO}")
    estado = MigrationExecutor(connection).loader.project_state(("fatos", MIGRACAO))
    migracao.expurgar_lead_dos_mortos_do_quiz(estado.apps, None)


def test_morto_de_quiz_com_lead_perde_so_o_lead() -> None:
    morto = guardar_morto(envelope_do_quiz({**DADOS_SEM_LEAD, "lead": LEAD}))

    expurgar()

    morto.refresh_from_db()
    envelope = json.loads(morto.corpo)
    assert envelope["data"] == DADOS_SEM_LEAD
    assert EMAIL not in morto.corpo
    assert morto.motivo == "faltam chaves do envelope canônico: site_id"
    assert morto.tipo_declarado == "quiz.completado"


def test_morto_de_outro_assunto_com_chave_lead_fica_intacto() -> None:
    corpo = json.dumps(
        {
            "event": "sugestao.criada",
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "occurred_at": QUANDO,
            "data": {"lead": "lead-opaco-1"},
        }
    )
    morto = guardar_morto(corpo, tipo_declarado="sugestao.criada")

    expurgar()

    morto.refresh_from_db()
    assert json.loads(morto.corpo)["data"]["lead"] == "lead-opaco-1"


def test_morto_com_corpo_que_nao_e_json_fica_intacto_e_nao_estoura() -> None:
    morto = guardar_morto("<bytes ilegíveis>", tipo_declarado="")

    expurgar()

    morto.refresh_from_db()
    assert morto.corpo == "<bytes ilegíveis>"


def test_morto_de_quiz_sem_lead_fica_byte_a_byte_igual() -> None:
    corpo = envelope_do_quiz(dict(DADOS_SEM_LEAD))
    morto = guardar_morto(corpo)

    expurgar()

    morto.refresh_from_db()
    assert morto.corpo == corpo


def test_morto_com_tipo_declarado_vazio_e_envelope_de_quiz_tambem_e_limpo() -> None:
    """O envelope pode ter morrido antes de `recepcao.receber` ler `event`
    (corpo JSON que não é um dict, por exemplo). Ainda assim, se o corpo
    guardado tiver `event == "quiz.completado"` com `data.lead`, o expurgo
    precisa alcançar."""
    morto = guardar_morto(
        envelope_do_quiz({**DADOS_SEM_LEAD, "lead": LEAD}),
        tipo_declarado="",
        motivo="o corpo é JSON, mas não é um objeto",
    )

    expurgar()

    morto.refresh_from_db()
    envelope = json.loads(morto.corpo)
    assert envelope["data"] == DADOS_SEM_LEAD
    assert EMAIL not in morto.corpo
