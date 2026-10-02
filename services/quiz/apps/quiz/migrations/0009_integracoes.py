from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quiz", "0008_experiencias_direcionadas")]

    operations = [
        migrations.CreateModel(
            name="IntegracaoEnvio",
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
                ("servico", models.CharField(max_length=32)),
                ("chave_evento", models.CharField(max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pendente", "pendente"),
                            ("aceito", "aceito"),
                            ("falhou", "falhou"),
                            ("nao_configurado", "nao_configurado"),
                            ("sem_consentimento", "sem_consentimento"),
                        ],
                        default="pendente",
                        max_length=24,
                    ),
                ),
                ("tentativas", models.PositiveSmallIntegerField(default=0)),
                ("ultimo_erro", models.TextField(blank=True, default="")),
                ("enviado_em", models.DateTimeField(blank=True, null=True)),
                ("resposta", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("servico", "chave_evento"),
                        name="integracao_envio_unico",
                    )
                ],
            },
        ),
    ]
