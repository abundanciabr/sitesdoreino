from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def marcar_ja_publicadas(apps, schema_editor):
    """As capturas antigas saíram na hora, pelo código anterior.

    Sem isto a tarefa as publicaria uma segunda vez com o mesmo `captura_id`.
    Fica só o que ainda está dentro dos 10 minutos de silêncio: essas a tarefa
    publica normalmente. É migração à parte (e não dentro da 0012) porque a
    0012 já tinha sido aplicada no site sem este passo.
    """
    CapturaParcial = apps.get_model("quiz", "CapturaParcial")
    CapturaParcial.objects.filter(
        publicada_em__isnull=True,
        atualizada_em__lt=timezone.now() - timedelta(minutes=10),
    ).update(publicada_em=models.F("criada_em"), publicacoes=1)


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0013_consentimento_whatsapp"),
    ]

    operations = [
        migrations.RunPython(marcar_ja_publicadas, migrations.RunPython.noop),
    ]
