import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0042_detalhes_dos_registros"),
    ]

    operations = [
        migrations.CreateModel(
            name="AvisoDaEquipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("pessoa_pedida", "Conversa para uma pessoa"), ("venda_assistida", "Venda com atendimento do agente"), ("conversa_ambigua", "Conversa ambígua"), ("trabalho_parado", "Trabalho comercial parado"), ("envio_incerto", "Envio sem confirmação")], max_length=30)),
                ("site_id", models.CharField(blank=True, default="", max_length=100)),
                ("fato", models.CharField(max_length=200)),
                ("responsavel_informado", models.CharField(blank=True, default="", max_length=200)),
                ("titulo", models.CharField(max_length=200)),
                ("texto", models.TextField(blank=True, default="")),
                ("link", models.CharField(blank=True, default="", max_length=500)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("visto_em", models.DateTimeField(blank=True, null=True)),
                ("visto_por", models.CharField(blank=True, default="", max_length=200)),
                ("email_situacao", models.CharField(choices=[("pendente", "Aguardando envio"), ("pedido", "Enviado ao correio"), ("sem_destinatario", "Sem e-mail para avisar"), ("desistiu", "Não foi possível enviar")], default="pendente", max_length=20)),
                ("email_tentativas", models.PositiveSmallIntegerField(default=0)),
                ("email_erro", models.CharField(blank=True, default="", max_length=300)),
                ("responsavel", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="avisos", to="core.membrodaequipe")),
            ],
            options={
                "ordering": ["-criado_em", "-id"],
                "indexes": [
                    models.Index(fields=["visto_em", "criado_em"], name="aviso_equipe_visto_idx"),
                    models.Index(fields=["email_situacao"], name="aviso_equipe_email_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("tipo", "site_id", "fato"), name="um_aviso_por_fato")],
            },
        ),
    ]
