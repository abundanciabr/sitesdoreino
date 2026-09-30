"""A crase que faltava em "perde o acesso à mesma" no texto já gravado no banco.

A página `/docs/como-funciona-a-entrada` sai do banco, não do `.md`. Corrigir o
arquivo não muda o documento que já está publicado, então a troca também é feita
aqui, no molde da `0005`: só onde o trecho antigo está literalmente presente.
Documento ausente ou já reescrito pelo mantenedor fica como está.
"""

from django.db import migrations

DOCUMENTO = "como-funciona-a-entrada"
SEM_CRASE = "perde o acesso a mesma."
COM_CRASE = "perde o acesso à mesma."


def _trocar(apps, antes, depois):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome=DOCUMENTO).first()
    if documento is None or antes not in documento.corpo:
        return
    documento.corpo = documento.corpo.replace(antes, depois, 1)
    documento.save(update_fields=["corpo"])


def colocar_a_crase(apps, schema_editor):
    _trocar(apps, SEM_CRASE, COM_CRASE)


def tirar_a_crase(apps, schema_editor):
    _trocar(apps, COM_CRASE, SEM_CRASE)


class Migration(migrations.Migration):
    dependencies = [("core", "0033_manter_o_manual_de_experimentacao_privado")]
    operations = [migrations.RunPython(colocar_a_crase, tirar_a_crase)]
