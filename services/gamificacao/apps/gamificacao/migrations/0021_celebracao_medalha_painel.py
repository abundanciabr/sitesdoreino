from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("gamificacao", "0020_avaliacoes_da_jornada")]
    operations = [
        migrations.AlterField(
            model_name="concessao", name="validador_papel",
            field=models.CharField(max_length=9, default="sistema", choices=[
                ("admin", "Administrador"), ("professor", "Professor"), ("monitor", "Monitor"),
                ("par", "Um colega"), ("sistema", "O sistema (conta automática)"),
            ]),
        ),
        migrations.CreateModel(
            name="CelebracaoDeMedalha",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120)),
                ("mensagem", models.CharField(max_length=1000)),
                ("referencia", models.CharField(blank=True, default="", max_length=200)),
                ("vista_em", models.DateTimeField(blank=True, null=True)),
                ("concessao", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="celebracao_medalha", to="gamificacao.concessao")),
            ],
        ),
    ]
