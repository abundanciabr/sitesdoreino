from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("matriculas", "0007_turma")]
    operations = [
        migrations.AddField(
            model_name="matricula",
            name="em_teste",
            field=models.BooleanField(default=False),
        ),
    ]
