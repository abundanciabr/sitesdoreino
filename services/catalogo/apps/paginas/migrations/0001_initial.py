"""As três tabelas da página, e a segunda metade da imutabilidade.

O `save()` e o `QuerySet` de `models.py` fecham o caminho do código, e é lá que
a mensagem em português explica o que fazer. Mas eles não alcançam um `UPDATE`
digitado num console de banco nem um script de migração de dados escrito por
quem não leu a constituição da célula. Página publicada que só é imutável por
convenção não é imutável: é um pedido.

Por isso a trava real fica no Postgres, como gatilho, do mesmo jeito que a da
célula `metricas`. Em SQLite a migração passa sem fazer nada, e o guarda do ORM
continua valendo lá; o CI da célula roda Postgres, que é onde a trava é medida.
"""

import django.db.models.deletion
import uuid
from django.db import migrations, models

CRIA_A_TRAVA = """
CREATE OR REPLACE FUNCTION catalogo_pagina_publicada_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'versao publicada nao se edita nem se apaga: publique uma versao nova '
        '(constituicoes/AGENTS.catalogo.md).';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER paginas_pageversion_sem_update
    BEFORE UPDATE ON paginas_pageversion
    FOR EACH ROW EXECUTE FUNCTION catalogo_pagina_publicada_imutavel();

CREATE TRIGGER paginas_pageversion_sem_delete
    BEFORE DELETE ON paginas_pageversion
    FOR EACH ROW EXECUTE FUNCTION catalogo_pagina_publicada_imutavel();
"""

DESFAZ_A_TRAVA = """
DROP TRIGGER IF EXISTS paginas_pageversion_sem_update ON paginas_pageversion;
DROP TRIGGER IF EXISTS paginas_pageversion_sem_delete ON paginas_pageversion;
DROP FUNCTION IF EXISTS catalogo_pagina_publicada_imutavel();
"""


def cria_a_trava(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CRIA_A_TRAVA)


def desfaz_a_trava(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DESFAZ_A_TRAVA)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ofertas", "0001_initial"),
        ("sites", "0006_menu_ganha_o_atalho_da_equipe"),
    ]

    operations = [
        migrations.CreateModel(
            name="Page",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("slug", models.SlugField(max_length=255)),
                (
                    "offer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="paginas",
                        to="ofertas.offer",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="paginas",
                        to="sites.site",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PageDraft",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("secoes", models.JSONField(blank=True, default=list)),
                ("base_version", models.PositiveIntegerField(default=0)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "page",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rascunho",
                        to="paginas.page",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PageVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("version", models.PositiveIntegerField()),
                ("secoes", models.JSONField(default=list)),
                ("published_at", models.DateTimeField(auto_now_add=True)),
                (
                    "page",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versoes",
                        to="paginas.page",
                    ),
                ),
            ],
            options={
                "ordering": ["-version"],
            },
        ),
        migrations.AddConstraint(
            model_name="page",
            constraint=models.UniqueConstraint(
                fields=("site", "slug"), name="pagina_unica_por_site"
            ),
        ),
        migrations.AddConstraint(
            model_name="pageversion",
            constraint=models.UniqueConstraint(
                fields=("page", "version"), name="versao_unica_por_pagina"
            ),
        ),
        migrations.RunPython(cria_a_trava, desfaz_a_trava),
    ]
