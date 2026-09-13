from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0018_o_apendice_vivo_e_o_aviso_de_verificacao_vencida")]

    operations = [
        migrations.CreateModel(
            name="MensagemDoRadio",
            fields=[
                ("sequencia", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "autor",
                    models.CharField(
                        choices=[
                            ("claude", "claude"),
                            ("codex", "codex"),
                            ("antigravity", "antigravity"),
                            ("mantenedor", "mantenedor"),
                        ],
                        max_length=12,
                    ),
                ),
                ("quando", models.DateTimeField(auto_now_add=True)),
                ("texto", models.CharField(max_length=2000)),
                ("tarefa", models.CharField(blank=True, max_length=7)),
            ],
            options={"ordering": ("sequencia",)},
        )
    ]
