import django.db.models.deletion
from django.db import migrations, models


def preencher_versoes_historicas(apps, schema_editor):
    Submission = apps.get_model("quiz", "Submission")
    QuizVersion = apps.get_model("quiz", "QuizVersion")
    for submission in Submission.objects.filter(version__isnull=True).iterator():
        versao = QuizVersion.objects.filter(
            quiz_id=submission.quiz_id, key="original"
        ).first()
        if versao is None:
            raise RuntimeError(f"quiz {submission.quiz_id} sem versao original")
        submission.version_id = versao.pk
        submission.save(update_fields=["version"])


class Migration(migrations.Migration):
    dependencies = [("quiz", "0003_versao_e_telemetria")]

    operations = [
        migrations.AddField(
            model_name="telemetryevent",
            name="stream_id",
            field=models.CharField(max_length=64, null=True, unique=True),
        ),
        migrations.RunPython(preencher_versoes_historicas, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="submission",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="submissions",
                to="quiz.quizversion",
            ),
        ),
        migrations.AddConstraint(
            model_name="submission",
            constraint=models.UniqueConstraint(
                fields=("quiz", "session_id"), name="submission_quiz_session_unica"
            ),
        ),
    ]
