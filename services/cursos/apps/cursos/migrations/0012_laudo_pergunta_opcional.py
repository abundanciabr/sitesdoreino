from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cursos", "0011_comentarios_de_aulas")]

    operations = [
        migrations.RemoveConstraint(
            model_name="rascunhodaia", name="forcas_mantidas_no_maximo_tres"
        ),
        migrations.RemoveConstraint(
            model_name="laudo", name="pergunta_de_amanha_so_grava_true"
        ),
        migrations.AlterField(
            model_name="laudo",
            name="sabe_o_que_fazer_amanha",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
