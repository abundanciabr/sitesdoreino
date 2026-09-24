from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_appmaxwebhookinbox")]

    operations = [
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="failed_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="next_retry_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="dead_lettered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="last_error",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="appmaxwebhookinbox",
            name="operational_action",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
