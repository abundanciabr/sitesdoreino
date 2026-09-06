# O ELO entre o curso e o produto do catálogo (TAR-227).
#
# ESQUEMA E SÓ ESQUEMA. A coluna nasce vazia em toda linha que já existe, e
# quem a preenche é `manage.py apontar_o_produto_do_curso` — nunca um
# `RunPython` daqui: [INV-CUR-C2] proíbe migração que roda código nesta célula
# (`tests/test_inv_c2_conteudo_so_pela_porta.py`).
#
# Curso com a coluna vazia FECHA a sala, e a decisão está escrita por extenso
# em `apps/cursos/models.py`.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0005_corpo_do_rascunho_da_ia"),
    ]

    operations = [
        migrations.AddField(
            model_name="curso",
            name="produto_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
