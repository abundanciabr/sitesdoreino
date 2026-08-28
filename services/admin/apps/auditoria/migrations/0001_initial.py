"""A tabela de auditoria e o que a torna append-only DE VERDADE.

O `save()` sobrescrito não impede nada (`armadilhas/079`): `QuerySet.update()`
não o chama, `psql` não o conhece, e qualquer código que não importe a classe
passa por baixo. Quem fecha as três metades é o BANCO, e é isso que esta
migration instala.

**Dois dialetos, escritos os dois de propósito.** A produção é Postgres; a
suíte local roda em SQLite. Um trigger só de Postgres deixaria o guarda
inexistente justamente onde o agente o exercita todo dia — e um guarda que
ninguém consegue ver morder é indistinguível de nenhum guarda. Os dois dizem a
mesma coisa e a mesma frase, e `tests/test_auditoria.py` prova que a versão
instalada MORDE, seja qual for o banco.

**O que fica de fora, e é bom saber antes de doer:** no Postgres, um teste
`django_db(transaction=True)` limpa as tabelas com `TRUNCATE`, e o trigger o
recusa. Esta célula não tem nenhum teste assim hoje; quem escrever o primeiro
vai encontrar esta nota — e a saída certa é o teste não tocar nesta tabela, não
afrouxar o trigger.
"""

from django.db import connection, migrations, models

MENSAGEM = "auditoria e append-only: nao se edita nem se apaga linha de auditoria"

POSTGRES = [
    f"""
    CREATE OR REPLACE FUNCTION auditoria_append_only() RETURNS trigger AS $func$
    BEGIN
      -- ERRCODE 23000 (integrity_constraint_violation) NÃO é decoração: sem
      -- ele o Postgres levanta com o código genérico P0001, que o Django
      -- traduz em `ProgrammingError` — enquanto o SQLite, com RAISE(ABORT),
      -- levanta `IntegrityError`. Medido no CI em 28/08/2026: o guarda passava
      -- local e reprovava em produção pela CLASSE da exceção, não pelo
      -- comportamento. Com o código explícito, os dois bancos falham igual, e
      -- quem escrever um `except` daqui a meses acerta nos dois.
      RAISE EXCEPTION '{MENSAGEM} (%)', TG_OP USING ERRCODE = '23000';
    END;
    $func$ LANGUAGE plpgsql;
    """,
    """
    CREATE TRIGGER auditoria_sem_update BEFORE UPDATE ON auditoria_registro
      FOR EACH ROW EXECUTE FUNCTION auditoria_append_only();
    """,
    """
    CREATE TRIGGER auditoria_sem_delete BEFORE DELETE ON auditoria_registro
      FOR EACH ROW EXECUTE FUNCTION auditoria_append_only();
    """,
    # TRUNCATE é a terceira metade, e a mais fácil de esquecer: ele não dispara
    # trigger de linha nenhum, e apagaria a auditoria inteira sem acusar nada.
    """
    CREATE TRIGGER auditoria_sem_truncate BEFORE TRUNCATE ON auditoria_registro
      FOR EACH STATEMENT EXECUTE FUNCTION auditoria_append_only();
    """,
]

SQLITE = [
    f"""
    CREATE TRIGGER auditoria_sem_update BEFORE UPDATE ON auditoria_registro
    BEGIN SELECT RAISE(ABORT, '{MENSAGEM} (UPDATE)'); END;
    """,
    f"""
    CREATE TRIGGER auditoria_sem_delete BEFORE DELETE ON auditoria_registro
    BEGIN SELECT RAISE(ABORT, '{MENSAGEM} (DELETE)'); END;
    """,
]


def instalar(apps, schema_editor):
    comandos = POSTGRES if connection.vendor == "postgresql" else SQLITE
    with schema_editor.connection.cursor() as cursor:
        for comando in comandos:
            cursor.execute(comando)


def desinstalar(apps, schema_editor):
    nomes = ["auditoria_sem_update", "auditoria_sem_delete"]
    if connection.vendor == "postgresql":
        nomes.append("auditoria_sem_truncate")
    with schema_editor.connection.cursor() as cursor:
        for nome in nomes:
            if connection.vendor == "postgresql":
                cursor.execute(f"DROP TRIGGER IF EXISTS {nome} ON auditoria_registro")
            else:
                cursor.execute(f"DROP TRIGGER IF EXISTS {nome}")
        if connection.vendor == "postgresql":
            cursor.execute("DROP FUNCTION IF EXISTS auditoria_append_only()")


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Registro",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("quando", models.DateTimeField(auto_now_add=True)),
                ("quem_email", models.EmailField(max_length=254)),
                ("quem_id", models.CharField(blank=True, default="", max_length=64)),
                (
                    "acao",
                    models.CharField(
                        choices=[("liberar", "liberar"), ("recusar", "recusar")],
                        max_length=20,
                    ),
                ),
                ("alvo", models.CharField(max_length=64)),
                (
                    "desfecho",
                    models.CharField(
                        choices=[
                            ("ok", "ok"),
                            ("recusado", "recusado pela célula dona"),
                            ("nao_respondeu", "não respondeu"),
                        ],
                        max_length=20,
                    ),
                ),
                ("detalhe", models.TextField(blank=True, default="")),
            ],
        ),
        migrations.AddIndex(
            model_name="registro",
            index=models.Index(
                fields=["-quando"], name="auditoria_r_quando_76bd9f_idx"
            ),
        ),
        migrations.RunPython(instalar, desinstalar),
    ]
