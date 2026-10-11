from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("encomendas", "0030_avaliacao_automatica_e_testes")]

    operations = [
        migrations.AddField(
            model_name="participacaosandbox",
            name="mensagens_recolhidas_ate",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
