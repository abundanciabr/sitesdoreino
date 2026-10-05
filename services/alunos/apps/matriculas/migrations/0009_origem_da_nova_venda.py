from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("matriculas", "0008_matricula_em_teste")]
    operations = [
        migrations.AddField(model_name="matricula", name="venda_origem",
                            field=models.CharField(max_length=16, blank=True, default="")),
        migrations.AddField(model_name="matricula", name="contato_crm_id",
                            field=models.CharField(max_length=64, blank=True, default="")),
    ]
