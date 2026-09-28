"""Compensa a publicação da 0029 na semente de uma instalação nova.

A produção foi despublicada pelo editor em 27/09/2026, com versão e auditoria.
Esta compensação técnica não inventa um gesto do editor no banco recém-criado.
"""

from django.db import migrations


def fechar_semente(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    Documento.objects.filter(
        nome="plataforma-experimentacao-e-aprendizado-de-conversao", publico=True
    ).update(publico=False)


def nao_reabre(apps, schema_editor):
    """Um rollback conserva a decisão de privacidade do mantenedor."""


class Migration(migrations.Migration):
    dependencies = [("core", "0032_semear_roadmap_da_comunidade")]
    operations = [migrations.RunPython(fechar_semente, nao_reabre)]
