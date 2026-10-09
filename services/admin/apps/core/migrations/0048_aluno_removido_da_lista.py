from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0047_docs_somente_publicacao_manual")]

    operations = [
        migrations.CreateModel(
            name="AlunoRemovidoDaLista",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=64)),
                ("email", models.EmailField(max_length=254)),
                ("removido", models.BooleanField(default=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("site_id", "email"), name="aluno_removido_por_escola")]},
        ),
    ]
