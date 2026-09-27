"""O expurgo único: `lead` sai dos fatos `quiz.completado` já guardados.

Decisão 6 do mantenedor (sessão de 26/09/2026, "Limpar na entrada e
expurgar", registro `painel/registros/20260927-013`, TAR-800). O contrato
`quiz.completado.v1` leva `data.lead` com e-mail, nome e telefone, e o livro
guardou esse bloco em cada fato do quiz até `consume_eventos.processar`
passar a descartá-lo na entrada. Dado pessoal não pode ficar no livro (LGPD),
e por isso o mantenedor autorizou, por escrito e só para este caso, alterar
fatos de um livro que é append-only.

## Como a trava é atravessada, e só aqui

A trava é dupla (`0002_a_trava_do_banco`): o ORM recusa `update()` e o banco
recusa `UPDATE` pelo gatilho `fatos_evento_sem_update`.

- **ORM:** o modelo histórico que a migração recebe não carrega o
  `EventoQuerySet` de `models.py` (o gerente não é `use_in_migrations`), então
  o `update()` daqui é o do Django, sem a recusa.
- **Banco:** o gatilho de UPDATE é desligado com `ALTER TABLE ... DISABLE
  TRIGGER`, o `UPDATE` tira `lead` apenas das linhas `quiz.completado` que o
  têm, e o gatilho é religado em seguida, tudo dentro da transação da
  migração. Se qualquer passo falhar, o Postgres desfaz os três juntos e a
  trava continua ligada. O gatilho de DELETE nem é tocado, e nenhuma outra
  migração ou código ganha caminho para alterar fato.

O reverso não devolve o dado apagado, e é esse o objetivo: não existe cópia
de `lead` para restaurar.
"""

from django.db import migrations

ASSUNTO = "quiz.completado"
CAMPO = "lead"


def expurgar_lead_do_quiz(apps, schema_editor):
    Evento = apps.get_model("fatos", "Evento")
    postgres = schema_editor.connection.vendor == "postgresql"
    if postgres:
        schema_editor.execute(
            "ALTER TABLE fatos_evento DISABLE TRIGGER fatos_evento_sem_update"
        )
    for pk, dados in Evento.objects.filter(tipo=ASSUNTO).values_list("pk", "dados"):
        if isinstance(dados, dict) and CAMPO in dados:
            limpos = {k: v for k, v in dados.items() if k != CAMPO}
            Evento.objects.filter(pk=pk).update(dados=limpos)
    if postgres:
        schema_editor.execute(
            "ALTER TABLE fatos_evento ENABLE TRIGGER fatos_evento_sem_update"
        )


class Migration(migrations.Migration):

    dependencies = [("fatos", "0003_o_marco")]

    operations = [
        migrations.RunPython(expurgar_lead_do_quiz, migrations.RunPython.noop)
    ]
