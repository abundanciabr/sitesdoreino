import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quiz", "0015_nps")]

    operations = [
        migrations.CreateModel(name="NPSRevisao", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("site_id", models.CharField(max_length=64)),
            ("aluno_id", models.CharField(max_length=128)),
            ("situacao_id", models.CharField(max_length=64)),
            ("tipo", models.CharField(max_length=20)),
            ("prova", models.JSONField(blank=True, default=dict)),
            ("criada_em", models.DateTimeField(auto_now_add=True)),
            ("tentativa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revisoes", to="quiz.npstentativa")),
        ]),
    ]
