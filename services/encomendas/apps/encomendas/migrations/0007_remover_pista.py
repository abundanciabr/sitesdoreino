from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("encomendas", "0006_prazo_da_chamada_aberta"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="encomenda",
            name="no_mural_so_na_pista_do_mural",
        ),
        migrations.RemoveField(
            model_name="encomenda",
            name="pista",
        ),
    ]
