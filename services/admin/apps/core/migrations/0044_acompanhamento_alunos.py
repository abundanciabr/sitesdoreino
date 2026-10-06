from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0043_avisos_da_equipe")]

    operations = [
        migrations.CreateModel(
            name="RegistroAcompanhamentoAluno",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254)),
                ("product_id", models.CharField(blank=True, default="", max_length=200)),
                ("status", models.CharField(choices=[("esperando_resposta", "Esperando resposta"), ("em_andamento", "Em andamento"), ("resolvido", "Resolvido")], max_length=24)),
                ("situacao_curso", models.CharField(choices=[("atividade_observada", "Atividade observada"), ("dificuldade", "Dificuldade relatada"), ("sem_informacao", "Sem informação")], max_length=24)),
                ("progresso_externo", models.CharField(blank=True, default="", max_length=300)),
                ("fonte", models.CharField(blank=True, default="", max_length=300)),
                ("dificuldade", models.TextField(blank=True, default="")),
                ("responsavel", models.CharField(blank=True, default="", max_length=200)),
                ("proximo_contato", models.TextField(blank=True, default="")),
                ("prazo", models.DateField(blank=True, null=True)),
                ("resultado", models.TextField(blank=True, default="")),
                ("registrado_por", models.CharField(max_length=200)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "core_registroacompanhamentoaluno", "ordering": ["-criado_em", "-id"], "indexes": [models.Index(fields=["site_id", "email", "-criado_em"], name="acom_aluno_chave_idx")]},
        ),
    ]
