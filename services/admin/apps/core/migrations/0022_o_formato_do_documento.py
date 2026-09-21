"""O documento ganha FORMATO: `texto` (o que sempre foi) ou `pagina`.

TAR-596, 21/09/2026. Pedido do mantenedor: *"o documento pode ser uma página
visual inteira, não só texto"*.

`default="texto"` não é escolha de conveniência: é o que faz esta migração não
mudar NADA do que já está no banco. Todo documento que existe hoje continua
sendo desenhado pelo renderizador que escapa o texto antes de formatar, e virar
página visual passa a ser um gesto de propósito no editor, como publicar.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0021_semear_o_crivo_explicado")]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="formato",
            field=models.CharField(
                choices=[("texto", "Texto escrito"), ("pagina", "Página visual")],
                default="texto",
                max_length=6,
            ),
        ),
    ]
