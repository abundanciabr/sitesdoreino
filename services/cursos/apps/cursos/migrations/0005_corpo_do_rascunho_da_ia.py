"""O corpo do `RascunhoDaIA`: o que o Assistente de laudo sugeriu, e as duas
medidas da Ficha de Série do agente (degrau 2.3, TAR-157).

`modelo` entra NÃO NULA e sem default permanente (`preserve_default=False`), e
isso é seguro porque a tabela está vazia em toda instalação: o esqueleto nasceu
no degrau 2.2 e nunca teve escritor. Um default permanente ali deixaria uma
linha nascer sem dizer qual modelo a escreveu, que é justamente o dado sem o
qual a Ficha de Série não sabe o que está medindo.

`forcas_mantidas` e `mudanca_mantida` nascem NULAS de propósito: nula é "o
laudo ainda não saiu", zero é "a professora reescreveu as três". As duas só são
escritas por `apps/cursos/laudo.py::emitir`.

[INV-CUR-C2]: esta migração cria esquema e NÃO roda código.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0004_rascunhodaia_laudo"),
    ]

    operations = [
        migrations.AddField(
            model_name="rascunhodaia",
            name="conteudo",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="rascunhodaia",
            name="modelo",
            field=models.CharField(default="", max_length=60),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rascunhodaia",
            name="tokens_entrada",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="rascunhodaia",
            name="tokens_saida",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="rascunhodaia",
            name="forcas_mantidas",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="rascunhodaia",
            name="mudanca_mantida",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="rascunhodaia",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("forcas_mantidas__isnull", True),
                    ("forcas_mantidas__lte", 3),
                    _connector="OR",
                ),
                name="forcas_mantidas_no_maximo_tres",
            ),
        ),
    ]
