from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0003_paypal_recovery")]

    operations = [
        migrations.AddField(
            model_name="charge",
            name="pix_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
