from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0009_jornada_autoral")]
    operations = [
        migrations.AddField(model_name="portfolio", name=nome,
                            field=models.JSONField(blank=True, default=dict, db_default={}))
        for nome in ("oferta_comercial", "apresentacao_comercial", "kit_vendas", "prospeccao_comercial")
    ] + [migrations.AddField(model_name="peca", name="provas_comerciais",
                            field=models.JSONField(blank=True, default=list, db_default=[]))]
