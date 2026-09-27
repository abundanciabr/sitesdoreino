"""O segundo expurgo: `lead` sai também dos `EventoMorto` de `quiz.completado`.

Decisão 6 do mantenedor (sessão de 26/09/2026, "Limpar na entrada e
expurgar", registro `painel/registros/20260927-013`, TAR-819). A TAR-800
(PR #2178, integrado) limpou a tabela `Evento` (migração
`0004_quiz_completado_sem_lead`) e passou a descartar `lead` na entrada
(`recepcao.receber`), inclusive para `EventoMorto` novo. Faltaram os
`EventoMorto` de `quiz.completado` gravados ANTES de 27/09/2026 03h37 UTC: o
campo `corpo` (o envelope cru, em texto) pode ter `data.lead` com e-mail,
nome e telefone, porque a fila de mortos guarda o que chegou tal como
chegou, para inspeção. Dado pessoal não pode ficar no livro (LGPD), e o
mantenedor autorizou, por escrito e só para este caso, apagar esse bloco das
linhas já gravadas.

## Por que não há trava para atravessar aqui

`0002_a_trava_do_banco` cria os gatilhos `fatos_evento_sem_update` e
`fatos_evento_sem_delete` nomeando a tabela `fatos_evento`, e só ela: a
`EventoMorto` (`fatos_evento_morto`) não tem gatilho nenhum, porque ela é
mutável de propósito (`models.py::EventoMorto`, o estado de um problema em
aberto muda por natureza). Por isso esta migração não desliga trava
nenhuma e o `RunPython` abaixo ignora o `schema_editor` que recebe: não há
DDL para executar, só um `UPDATE` comum em uma tabela que já aceita
`UPDATE`.

## O que é varrido, e por quê

O filtro busca `tipo_declarado` igual a `"quiz.completado"` e também
`tipo_declarado` vazio: a recepção só preenche `tipo_declarado` quando o
envelope chega a ser um `dict` JSON com a chave `event` presente
(`recepcao._matar`); um corpo que não é JSON válido, ou que é JSON mas não é
um objeto, morre com `tipo_declarado` vazio mesmo que o `event` dentro dele
fosse `"quiz.completado"`. Cada candidato é inspecionado de verdade: só é
alterado quem tem corpo JSON, cujo `event` é `"quiz.completado"`, com `data`
um objeto que contém `lead`. Todo o resto (corpo que não é JSON, que não é
um objeto, sem `data` objeto, ou sem `lead`) fica intocado, byte a byte.

O reverso não devolve o dado apagado, e é esse o objetivo: não existe cópia
de `lead` para restaurar.
"""

from __future__ import annotations

import json

from django.db import migrations

ASSUNTO = "quiz.completado"
CAMPO = "lead"


def expurgar_lead_dos_mortos_do_quiz(apps, schema_editor):
    EventoMorto = apps.get_model("fatos", "EventoMorto")
    candidatos = EventoMorto.objects.filter(tipo_declarado__in=[ASSUNTO, ""])
    for pk, corpo in candidatos.values_list("pk", "corpo"):
        try:
            envelope = json.loads(corpo)
        except (TypeError, ValueError):
            continue
        if not isinstance(envelope, dict) or envelope.get("event") != ASSUNTO:
            continue
        dados = envelope.get("data")
        if not isinstance(dados, dict) or CAMPO not in dados:
            continue
        envelope["data"] = {k: v for k, v in dados.items() if k != CAMPO}
        EventoMorto.objects.filter(pk=pk).update(
            corpo=json.dumps(envelope, ensure_ascii=False)
        )


class Migration(migrations.Migration):

    dependencies = [("fatos", "0004_quiz_completado_sem_lead")]

    operations = [
        migrations.RunPython(
            expurgar_lead_dos_mortos_do_quiz, migrations.RunPython.noop
        )
    ]
