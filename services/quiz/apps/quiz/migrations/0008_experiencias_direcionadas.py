from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quiz", "0007_portfolio_journey")]

    operations = [
        migrations.AddField(
            model_name="quiz",
            name="directed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="quizversion",
            name="experience",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="submission",
            name="context",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
