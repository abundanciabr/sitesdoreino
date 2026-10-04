from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="IdentidadeAssistente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_id", models.CharField(max_length=80, unique=True)),
                ("nome_do_site", models.CharField(blank=True, default="", max_length=200)),
                ("nome", models.CharField(blank=True, default="", max_length=80)),
                ("apresentacao", models.CharField(blank=True, default="", max_length=300)),
                ("assinatura", models.CharField(blank=True, default="", max_length=200)),
                ("tom", models.CharField(choices=[("acolhedor", "Acolhedor e objetivo"), ("direto", "Direto e curto"), ("descontraido", "Descontraído"), ("formal", "Formal")], default="acolhedor", max_length=20)),
                ("resposta_em_voz", models.CharField(choices=[("texto", "Sempre em texto"), ("espelhar", "Em voz só quando a pessoa mandar áudio"), ("sempre", "Em voz sempre que o canal permitir")], default="texto", max_length=20)),
                ("atualizado_por", models.CharField(blank=True, default="", max_length=200)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
