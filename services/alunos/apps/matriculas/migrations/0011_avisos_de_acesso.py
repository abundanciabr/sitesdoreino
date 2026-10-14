from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("matriculas", "0010_identificador_meshcraft_legado")]
    operations = [
        migrations.AddField(model_name="matricula", name="whatsapp_pedido_id", field=models.UUIDField(null=True, blank=True)),
        migrations.AddField(model_name="matricula", name="whatsapp_confirmacao_codigo", field=models.CharField(max_length=10, blank=True, default="", db_index=True)),
        migrations.AddField(model_name="matricula", name="whatsapp_confirmado_em", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="matricula", name="whatsapp_avisos", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="matricula", name="whatsapp_consentido_em", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="matricula", name="aviso_event_id", field=models.UUIDField(null=True, blank=True)),
    ]
