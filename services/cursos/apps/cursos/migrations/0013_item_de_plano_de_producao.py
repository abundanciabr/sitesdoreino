from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cursos", "0012_laudo_pergunta_opcional")]

    operations = [
        migrations.CreateModel(
            name="ItemDePlanoDeProducao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=160)),
                ("plano", models.CharField(max_length=100)),
                ("chave", models.CharField(max_length=100)),
                ("feito", models.BooleanField(default=False)),
                ("nota", models.TextField(blank=True, default="")),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("site_id", "plano", "chave"), name="item_de_plano_por_site_e_chave")]},
        ),
    ]
