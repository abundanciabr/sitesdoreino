from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("agentes", "0008_alter_execucao_tipo_analisesatisfacao")]
    operations = [
        migrations.AlterField(model_name="execucao", name="robo", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name="execucoes", to="agentes.robopessoal")),
        migrations.AlterField(model_name="entrega", name="robo", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name="entregas", to="agentes.robopessoal")),
    ]
