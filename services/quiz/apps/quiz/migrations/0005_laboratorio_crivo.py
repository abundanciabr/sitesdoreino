from types import SimpleNamespace

from django.db import migrations

from apps.quiz.management.commands.seed_laboratorio_crivo import semear_laboratorio


def semear(apps, schema_editor):
    cadastro = SimpleNamespace(
        **{
            nome: apps.get_model("quiz", nome)
            for nome in (
                "Site",
                "Quiz",
                "QuizVersion",
                "Question",
                "Option",
                "ResultBand",
            )
        }
    )
    site = cadastro.Site.objects.filter(host="meshcraft.top", active=True).first()
    if site is not None:
        semear_laboratorio(site, cadastro)


class Migration(migrations.Migration):
    dependencies = [("quiz", "0004_corrigir_telemetria_e_submissoes")]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
