import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("forum", "0012_rascunho_de_area")]

    operations = [
        migrations.CreateModel(
            name="RascunhoDeTopico",
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
                ("area_slug", models.SlugField(max_length=60)),
                ("titulo", models.CharField(max_length=180)),
                ("texto", models.TextField()),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("publicado_em", models.DateTimeField(blank=True, null=True)),
                (
                    "topico",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rascunho_do_editor",
                        to="forum.topico",
                    ),
                ),
            ],
        ),
    ]
