import json
import re
from pathlib import Path

from django.db import migrations, models


FIELDS = (
    "arquivo", "tipo", "quando", "titulo", "responde_a", "vence_em_dias",
    "precisa_do_dono", "foto", "problema", "hipotese", "metrica", "guarda",
    "veredito", "portao", "evidencia", "verificado_em",
)


def importar(apps, schema_editor):
    Cartao = apps.get_model("core", "CartaoDoPlacar")
    Versao = apps.get_model("core", "VersaoDoCartaoDoPlacar")
    Registro = apps.get_model("core", "RegistroDoPlacar")
    raiz = Path(__file__).resolve().parents[1]
    for arquivo in sorted((raiz / "cartoes").glob("*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        cartao, _ = Cartao.objects.using(schema_editor.connection.alias).get_or_create(
            nome=arquivo.stem, defaults={"dados": dados}
        )
        Versao.objects.using(schema_editor.connection.alias).get_or_create(
            cartao=cartao, revisao=1,
            defaults={"dados": cartao.dados, "responsavel": "importacao"},
        )
    for arquivo in sorted((raiz / "registros").glob("*.js")):
        texto = arquivo.read_text(encoding="utf-8")
        dados = {}
        for campo in FIELDS:
            encontrado = re.search(
                r"^\s*" + campo + r':\s*(null|true|false|"([^"\\]*(?:\\.[^"\\]*)*)"|(\d+))',
                texto, re.M,
            )
            if not encontrado:
                dados[campo] = None
            elif encontrado.group(1) == "null":
                dados[campo] = None
            elif encontrado.group(1) in ("true", "false"):
                dados[campo] = encontrado.group(1) == "true"
            elif encontrado.group(3) is not None:
                dados[campo] = int(encontrado.group(3))
            else:
                dados[campo] = json.loads('"' + encontrado.group(2) + '"')
        dados["arquivo"] = dados["arquivo"] or arquivo.stem
        Registro.objects.using(schema_editor.connection.alias).get_or_create(
            arquivo=dados["arquivo"],
            defaults={"dados": dados, "texto_original": texto},
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0040_executor_da_tarefa")]

    operations = [
        migrations.CreateModel(
            name="CartaoDoPlacar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=150, unique=True)),
                ("dados", models.JSONField()),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="VersaoDoCartaoDoPlacar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revisao", models.PositiveIntegerField()),
                ("dados", models.JSONField()),
                ("responsavel", models.CharField(blank=True, max_length=200)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("cartao", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="versoes", to="core.cartaodoplacar")),
            ],
        ),
        migrations.AddConstraint(
            model_name="versaodocartaodoplacar",
            constraint=models.UniqueConstraint(fields=("cartao", "revisao"), name="cartao_revisao_unica"),
        ),
        migrations.CreateModel(
            name="RegistroDoPlacar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("arquivo", models.CharField(max_length=150, unique=True)),
                ("dados", models.JSONField()),
                ("texto_original", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="FechamentoDoCiclo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("partida_em", models.DateField(unique=True)),
                ("encerrado_em", models.DateField()),
                ("dados", models.JSONField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RunPython(importar, migrations.RunPython.noop),
    ]

