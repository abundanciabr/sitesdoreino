from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0002_recebivel_destinatario")]
    operations = [
        migrations.AddField("charge", "paypal_return_base", models.URLField(blank=True, max_length=2048)),
        migrations.AddField("charge", "capture_started_at", models.DateTimeField(blank=True, null=True)),
    ]
