from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("eventos", "0003_fato_de_provedor_visto")]
    operations = [
        migrations.RemoveConstraint(model_name="envioregistrado", name="uniq_envio_por_order_tipo_canal"),
        migrations.AddConstraint(model_name="envioregistrado", constraint=models.UniqueConstraint(
            fields=("site_id", "order_id", "tipo", "canal"),
            name="uniq_envio_por_site_order_tipo_canal",
        )),
    ]
