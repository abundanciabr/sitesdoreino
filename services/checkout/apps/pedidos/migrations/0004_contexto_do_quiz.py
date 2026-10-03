from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0003_session_visitor_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="contexto",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="contexto",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
