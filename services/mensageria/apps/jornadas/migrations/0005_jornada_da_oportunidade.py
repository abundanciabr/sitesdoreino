from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jornadas", "0004_estados_whatsapp")]

    operations = [
        migrations.AddField(
            model_name="inscricao",
            name="oportunidade_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="inscricao",
            name="lead_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="inscricao",
            name="ultima_conferencia",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="entrega",
            name="crm_registrado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
