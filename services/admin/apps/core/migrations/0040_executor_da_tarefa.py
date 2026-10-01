from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_rascunho_de_configuracao"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarefa",
            name="executor",
            field=models.CharField(
                choices=[
                    ("pessoa", "A pessoa"),
                    ("robo", "O robô"),
                    ("compartilhada", "Pessoa e robô"),
                ],
                default="pessoa",
                max_length=20,
            ),
        ),
    ]
