"""Os dois fatos do funil comercial (medição, etapa 6 do plano do CRM).

`FatoOportunidade` é a projeção de `crm.oportunidade-atualizada` (E3) e
`FatoMensagemRecebida` a de `mensagem.recebida` (E2). Nenhuma das
duas tem gatilho de imutabilidade: são LEITURAS que esta célula faz do
`Evento` (como o `Marco`), e se refazem a partir do livro quando a regra muda.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fatos", "0005_quiz_morto_sem_lead"),
    ]

    operations = [
        migrations.CreateModel(
            name="FatoOportunidade",
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
                ("event_id", models.UUIDField(unique=True)),
                ("site_id", models.CharField(max_length=60)),
                ("oportunidade_id", models.CharField(max_length=60)),
                ("lead_id", models.CharField(blank=True, default="", max_length=60)),
                ("etapa", models.CharField(blank=True, default="", max_length=30)),
                ("motivo", models.CharField(blank=True, default="", max_length=30)),
                ("atendente", models.CharField(blank=True, default="", max_length=20)),
                ("estrategia_versao", models.IntegerField(blank=True, null=True)),
                (
                    "oferta_slug",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("order_id", models.CharField(blank=True, default="", max_length=120)),
                (
                    "payment_id",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("valor_centavos", models.IntegerField(blank=True, null=True)),
                ("telefone", models.CharField(blank=True, default="", max_length=30)),
                ("link_enviado_em", models.DateTimeField(blank=True, null=True)),
                ("ocorrido_em", models.DateTimeField()),
            ],
            options={
                "ordering": ["ocorrido_em"],
                "indexes": [
                    models.Index(
                        fields=["site_id", "ocorrido_em"],
                        name="fatos_fatoo_site_id_46ee19_idx",
                    ),
                    models.Index(
                        fields=["oportunidade_id"],
                        name="fatos_fatoo_oportun_8e2e65_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="FatoMensagemRecebida",
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
                ("event_id", models.UUIDField(unique=True)),
                ("site_id", models.CharField(max_length=60)),
                ("lead_id", models.CharField(blank=True, default="", max_length=60)),
                ("telefone", models.CharField(blank=True, default="", max_length=30)),
                ("canal", models.CharField(blank=True, default="", max_length=20)),
                ("tipo", models.CharField(blank=True, default="", max_length=20)),
                ("descadastro", models.BooleanField(default=False)),
                ("recebida_em", models.DateTimeField()),
            ],
            options={
                "ordering": ["recebida_em"],
                "indexes": [
                    models.Index(
                        fields=["site_id", "telefone", "recebida_em"],
                        name="fatos_fatom_site_id_091022_idx",
                    )
                ],
            },
        ),
    ]
