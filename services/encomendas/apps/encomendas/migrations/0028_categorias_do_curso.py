from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("encomendas", "0027_site_id_nas_filhas_da_pratica_e_da_fila")]
    operations = [migrations.AlterField(
        model_name="projetosandbox", name="categoria",
        field=models.CharField(blank=True, default="", max_length=24, choices=[
            ("espadas_objetos", "Armas"), ("pets", "Animais"),
            ("carros", "Carros"), ("roupas", "Roupas"), ("livre", "Projeto livre"),
            ("cabelos", "Cabelos"), ("chapeus", "Chapéus"), ("personagens", "Personagens")]),
    )]
