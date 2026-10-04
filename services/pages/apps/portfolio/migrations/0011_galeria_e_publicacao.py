import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0010_apresentacao_comercial")]

    operations = [
        migrations.AddField("portfolio", "publicacao_comercial", models.JSONField(blank=True, default=dict, db_default={})),
        migrations.AddField("peca", "titulo", models.CharField(max_length=200, blank=True, default="", db_default="")),
        migrations.AddField("peca", "descricao", models.TextField(blank=True, default="", db_default="")),
        migrations.AddField("peca", "triangulos", models.CharField(max_length=120, blank=True, default="", db_default="")),
        migrations.AddField("peca", "textura", models.CharField(max_length=200, blank=True, default="", db_default="")),
        migrations.AddField("peca", "checklist_preparacao", models.JSONField(blank=True, default=list, db_default=[])),
        migrations.AddField("peca", "arquivada", models.BooleanField(default=False, db_default=False)),
        migrations.CreateModel(
            name="MaterialDaPeca",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("categoria", models.CharField(max_length=16, choices=[("render", "Render"), ("vistas", "Vistas e detalhes"), ("wireframe", "Wireframe"), ("uv", "UV")], default="render")),
                ("legenda", models.CharField(max_length=200, blank=True, default="")),
                ("ordem", models.PositiveIntegerField(default=1)),
                ("principal", models.BooleanField(default=False)),
                ("selecionado_publicacao", models.BooleanField(default=False)),
                ("bytes", models.BinaryField()),
                ("tamanho", models.PositiveIntegerField()),
                ("largura", models.PositiveIntegerField()),
                ("altura", models.PositiveIntegerField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("peca", models.ForeignKey(to="portfolio.peca", on_delete=django.db.models.deletion.CASCADE, related_name="materiais")),
                ("substituido_por", models.ForeignKey(to="portfolio.materialdapeca", on_delete=django.db.models.deletion.SET_NULL, blank=True, null=True)),
            ],
            options={"ordering": ["ordem", "criado_em"]},
        ),
    ]
