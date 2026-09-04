"""A segunda metade da imutabilidade: a trava mora TAMBÉM no banco.

O `save()` e o `QuerySet` de `models.py` fecham o caminho do código, e é lá que
a mensagem em português explica o que fazer. Mas eles não alcançam um `UPDATE`
digitado num console de banco, um `psql` de emergência às duas da manhã, nem
um script de migração de dados escrito por quem não leu a constituição da
célula. Um livro de fatos que só é append-only por convenção não é
append-only: é um pedido.

Por isso a trava real fica no Postgres, como gatilho. Em SQLite (a máquina de
quem programa) a migração passa sem fazer nada, e o guarda do ORM continua
valendo lá — o CI da célula roda Postgres 17, que é onde a trava é medida.
"""

from django.db import migrations

CRIA = """
CREATE OR REPLACE FUNCTION metricas_fato_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'evento nao se corrige nem se apaga: o livro de fatos e append-only '
        '(constituicoes/AGENTS.metricas.md). Correcao e evento novo.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER fatos_evento_sem_update
    BEFORE UPDATE ON fatos_evento
    FOR EACH ROW EXECUTE FUNCTION metricas_fato_imutavel();

CREATE TRIGGER fatos_evento_sem_delete
    BEFORE DELETE ON fatos_evento
    FOR EACH ROW EXECUTE FUNCTION metricas_fato_imutavel();
"""

DESFAZ = """
DROP TRIGGER IF EXISTS fatos_evento_sem_update ON fatos_evento;
DROP TRIGGER IF EXISTS fatos_evento_sem_delete ON fatos_evento;
DROP FUNCTION IF EXISTS metricas_fato_imutavel();
"""


def cria(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CRIA)


def desfaz(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DESFAZ)


class Migration(migrations.Migration):

    dependencies = [("fatos", "0001_initial")]

    operations = [migrations.RunPython(cria, desfaz)]
