from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("agentes", "0002_autorizacao_de_gasto_inicial")]
    operations = [
        migrations.AddField(
            model_name="autorizacaodegasto", name="destino",
            field=models.CharField(default="equipe", max_length=20),
        ),
        migrations.AddField(
            model_name="consumo", name="origem",
            field=models.CharField(default="equipe", max_length=20),
        ),
        migrations.CreateModel(
            name="RoboDosAlunos",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(default="Robô dos alunos", max_length=120)),
                ("modelo", models.CharField(default="gpt-6-luna", max_length=60)),
                ("instrucoes", models.TextField(blank=True, default="")),
                ("ativo", models.BooleanField(default=False)),
                ("alterado_em", models.DateTimeField(auto_now=True)),
                ("autorizacao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="agentes.autorizacaodegasto")),
            ],
        ),
    ]
