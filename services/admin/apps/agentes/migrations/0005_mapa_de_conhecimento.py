import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agentes", "0004_trabalhos_do_quiz")]
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
                    ("conhecimento", "Leitura dos documentos para o mapa de conhecimento"),
                ],
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="FonteDoConhecimento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chave", models.CharField(max_length=120, unique=True)),
                ("titulo", models.CharField(max_length=200)),
                ("endereco", models.CharField(blank=True, default="", max_length=300)),
                ("publica", models.BooleanField(default=False)),
                ("impressao", models.CharField(max_length=64)),
                ("lida_em", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="EntidadeDoConhecimento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=200)),
                ("tipo", models.CharField(max_length=40)),
                ("resumo", models.CharField(blank=True, default="", max_length=500)),
                ("fonte", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entidades", to="agentes.fontedoconhecimento")),
            ],
        ),
        migrations.CreateModel(
            name="LigacaoDoConhecimento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origem", models.CharField(max_length=200)),
                ("relacao", models.CharField(max_length=80)),
                ("destino", models.CharField(max_length=200)),
                ("evidencia", models.CharField(blank=True, default="", max_length=400)),
                ("fonte", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ligacoes", to="agentes.fontedoconhecimento")),
            ],
        ),
    ]
