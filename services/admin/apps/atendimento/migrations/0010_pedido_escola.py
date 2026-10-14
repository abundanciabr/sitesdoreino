from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies=[("atendimento", "0009_referencia_entrada_canal")]
    operations=[
        migrations.AddField(model_name="conversa", name="pedido_escola_id", field=models.CharField(max_length=30,blank=True)),
        migrations.AddField(model_name="conversa", name="pedido_escola_event_id", field=models.UUIDField(null=True,blank=True)),
    ]
