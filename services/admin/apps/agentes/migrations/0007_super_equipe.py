from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agentes", "0006_conhecimento_comercial")]

    operations = [
        migrations.AlterField(
            model_name="execucao", name="tipo",
            field=models.CharField(max_length=30, choices=[
                ("conversa", "Resposta na conversa"),
                ("panorama_semanal", "Panorama semanal"),
                ("conferencia_quiz", "Conferência dos links do quiz"),
                ("leitura_quiz", "Leitura dos números do quiz"),
                ("conhecimento", "Leitura dos documentos para o mapa de conhecimento"),
                ("super_equipe", "Equipe de especialistas técnicos"),
            ]),
        ),
    ]
