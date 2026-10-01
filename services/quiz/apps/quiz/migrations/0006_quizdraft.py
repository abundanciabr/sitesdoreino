from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quiz", "0005_laboratorio_crivo")]
    operations = [
        migrations.CreateModel(
            name="QuizDraft",
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
                ("content", models.JSONField(default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "quiz",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft",
                        to="quiz.quiz",
                    ),
                ),
            ],
        ),
    ]
