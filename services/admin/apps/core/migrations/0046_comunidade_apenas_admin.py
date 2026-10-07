from django.db import migrations


def reservar(apps, schema_editor):
    Documento = apps.get_model("core", "Documento")
    documento = Documento.objects.filter(nome="comunidade").first()
    if documento is not None:
        documento.publico = False
        nota = "## Ordem do mantenedor em 07/10/2026 sobre os menus"
        if nota not in documento.corpo:
            documento.corpo += "\n\n" + nota + "\n\nÉ proibido acrescentar qualquer link ou qualquer outro elemento aos menus do site sem ordem expressa do mantenedor. A única exceção é o menu do admin.\n\nAs páginas `https://meshcraft.top/docs/comunidade` e `https://meshcraft.top/cursos/comunidade/parte-1/D02` são exclusivas dos administradores. O link Cursos para `https://meshcraft.top/cursos/` foi retirado do rodapé.\n"
        documento.save(update_fields=["publico", "corpo"])


class Migration(migrations.Migration):
    dependencies = [("core", "0045_galeria_da_comunidade")]
    operations = [migrations.RunPython(reservar, migrations.RunPython.noop)]
