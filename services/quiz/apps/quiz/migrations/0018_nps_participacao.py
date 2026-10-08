from django.db import migrations, models


def carregar(apps, schema_editor):
    Tentativa = apps.get_model("quiz", "NPSTentativa")
    Participacao = apps.get_model("quiz", "NPSParticipacao")
    banco = schema_editor.connection.alias
    for a in Tentativa.objects.using(banco).filter(status="concluida", concluida_em__isnull=False).order_by("concluida_em", "criada_em", "id").iterator():
        resultado = a.resultado or {}
        nota = resultado.get("nps")
        if type(nota) is not int or not 0 <= nota <= 10 or resultado.get("pessoa_respondente") == "responsavel":
            continue
        p, _ = Participacao.objects.using(banco).get_or_create(site_id=a.site_id, aluno_id=a.aluno_id)
        segmento = "promotor" if nota >= 9 else "neutro" if nota >= 7 else "detrator"
        if segmento == "detrator" and p.teve_positiva:
            p.conquistas_privadas_ate = p.conquistas_privadas_ate or a.concluida_em
        if segmento != "detrator":
            p.teve_positiva = True
        if segmento == "promotor":
            p.embaixador_desde = p.embaixador_desde or a.concluida_em
        p.segmento, p.nota, p.avaliacao_id, p.avaliada_em = segmento, nota, a.id, a.concluida_em
        p.save(using=banco)


class Migration(migrations.Migration):
    dependencies = [("quiz", "0017_nps_arquivo")]
    operations = [
        migrations.CreateModel(name="NPSParticipacao", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("site_id", models.CharField(max_length=64)),
            ("aluno_id", models.CharField(max_length=128)),
            ("segmento", models.CharField(default="sem_avaliacao", max_length=20)),
            ("nota", models.PositiveSmallIntegerField(null=True)),
            ("avaliacao_id", models.UUIDField(null=True)),
            ("avaliada_em", models.DateTimeField(null=True)),
            ("teve_positiva", models.BooleanField(default=False)),
            ("embaixador_desde", models.DateTimeField(null=True)),
            ("conquistas_privadas_ate", models.DateTimeField(null=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=("site_id", "aluno_id"), name="nps_participacao_aluno_site")]}),
        migrations.RunPython(carregar, migrations.RunPython.noop),
    ]
