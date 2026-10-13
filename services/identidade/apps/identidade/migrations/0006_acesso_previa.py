from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [("identidade", "0005_recuperacao_senha")]
    operations = [migrations.CreateModel(name="AcessoPrevia", fields=[
        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
        ("site_id", models.CharField(max_length=100)),
        ("canal", models.CharField(max_length=12)),
        ("destino", models.CharField(max_length=254)),
        ("codigo_hash", models.CharField(max_length=64)),
        ("criado_em", models.DateTimeField(auto_now_add=True)),
        ("expira_em", models.DateTimeField()),
        ("consumido_em", models.DateTimeField(null=True, blank=True)),
        ("tentativas", models.PositiveSmallIntegerField(default=0)),
        ("identidade", models.ForeignKey(to="identidade.identidade", on_delete=django.db.models.deletion.PROTECT)),
    ], options={"indexes": [models.Index(fields=["identidade", "criado_em"], name="idt_previa_pessoa_data")]})]
