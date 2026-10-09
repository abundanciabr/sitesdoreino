from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("identidade", "0004_idioma_de_cadastro")]

    operations = [
        migrations.CreateModel(
            name="RecuperacaoSenha",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("pedido_key", models.CharField(max_length=64)),
                ("expira_em", models.DateTimeField()),
                ("consumida_em", models.DateTimeField(blank=True, null=True)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("identidade", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="identidade.identidade")),
            ],
            options={"indexes": [models.Index(fields=["identidade", "consumida_em"], name="idt_rec_pendente")]},
        ),
        migrations.AddConstraint(
            model_name="recuperacaosenha",
            constraint=models.UniqueConstraint(fields=("identidade", "pedido_key"), name="idt_rec_pedido_unico"),
        ),
    ]
