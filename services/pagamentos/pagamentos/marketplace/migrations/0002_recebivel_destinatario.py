from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0001_initial")]
    operations = [
        migrations.AddField("recebivel", "aluno_id", models.CharField(blank=True, max_length=64)),
        migrations.AddField("recebivel", "valor_liquido_cents", models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField("recebivel", "taxas_cents", models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField("recebivel", "autorizacao_mantenedor_referencia", models.CharField(blank=True, max_length=160)),
        migrations.AddField("recebivel", "comprovante_referencia", models.CharField(blank=True, max_length=160)),
        migrations.AddField("recebivel", "repasse_confirmado_em", models.DateTimeField(blank=True, null=True)),
    ]
