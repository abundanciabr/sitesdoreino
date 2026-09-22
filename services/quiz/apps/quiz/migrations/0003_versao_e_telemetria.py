# A pergunta e a faixa passam a ser da versão. O quiz continua a campanha.
#
# Expand-and-contract: a coluna nova nasce nula, a versão `original` recebe o
# que já estava plantado, e só então a coluna fica obrigatória. Um ADD NOT NULL
# direto quebraria o banco que já tem pergunta.

import django.db.models.deletion
from django.db import migrations, models


def ligar_versao_original(apps, schema_editor):
    Quiz = apps.get_model("quiz", "Quiz")
    Versao = apps.get_model("quiz", "QuizVersion")
    Pergunta = apps.get_model("quiz", "Question")
    Faixa = apps.get_model("quiz", "ResultBand")
    for quiz in Quiz.objects.all():
        versao = Versao.objects.create(
            quiz_id=quiz.pk, key="original", weight=100, active=True
        )
        Pergunta.objects.filter(quiz_id=quiz.pk).update(version_id=versao.pk)
        Faixa.objects.filter(quiz_id=quiz.pk).update(version_id=versao.pk)


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0002_botao_por_faixa"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuizVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.SlugField(max_length=100)),
                ("weight", models.PositiveSmallIntegerField(default=100)),
                ("active", models.BooleanField(default=True)),
                (
                    "quiz",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="quiz.quiz",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="quizversion",
            constraint=models.UniqueConstraint(
                fields=("quiz", "key"), name="quiz_version_quiz_key_unico"
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="quiz.quizversion",
            ),
        ),
        migrations.AddField(
            model_name="resultband",
            name="version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bands",
                to="quiz.quizversion",
            ),
        ),
        migrations.RunPython(ligar_versao_original, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="question",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="quiz.quizversion",
            ),
        ),
        migrations.AlterField(
            model_name="resultband",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bands",
                to="quiz.quizversion",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="question", name="question_quiz_order_unico"
        ),
        migrations.RemoveConstraint(
            model_name="resultband", name="band_quiz_key_unico"
        ),
        migrations.RemoveField(model_name="question", name="quiz"),
        migrations.RemoveField(model_name="resultband", name="quiz"),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                fields=("version", "order"), name="question_version_order_unico"
            ),
        ),
        migrations.AddConstraint(
            model_name="resultband",
            constraint=models.UniqueConstraint(
                fields=("version", "key"), name="band_version_key_unico"
            ),
        ),
        migrations.AddField(
            model_name="submission",
            name="session_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="submission",
            name="version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="submissions",
                to="quiz.quizversion",
            ),
        ),
        migrations.CreateModel(
            name="TelemetryEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("session_id", models.UUIDField()),
                ("site_id", models.CharField(max_length=64)),
                ("quiz_slug", models.SlugField(max_length=100)),
                ("version_key", models.SlugField(max_length=100)),
                ("event_type", models.CharField(max_length=32)),
                (
                    "element_id",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="telemetryevent",
            index=models.Index(
                fields=["quiz_slug", "event_type", "occurred_at"],
                name="quiz_telemetria_funil",
            ),
        ),
    ]
