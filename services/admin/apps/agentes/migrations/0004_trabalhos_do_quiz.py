from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agentes", "0003_robo_dos_alunos")]
    operations = [
        migrations.AlterField(
            model_name="execucao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("conversa", "Resposta na conversa"),
                    ("panorama_semanal", "Panorama semanal"),
                    ("conferencia_quiz", "Conferência dos links do quiz"),
                    ("leitura_quiz", "Leitura dos números do quiz"),
                ],
                max_length=30,
            ),
        ),
    ]
