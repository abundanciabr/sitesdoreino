from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="Charge", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("idempotency_key", models.UUIDField(unique=True)),
            ("site_id", models.CharField(max_length=255)),
            ("order_id", models.UUIDField()),
            ("order_version", models.PositiveIntegerField()),
            ("amount_cents", models.PositiveIntegerField()),
            ("currency", models.CharField(max_length=3)),
            ("environment", models.CharField(default="sandbox", max_length=16)),
            ("method", models.CharField(choices=[("pix", "Pix"), ("paypal", "PayPal")], max_length=10)),
            ("status", models.CharField(default="created", max_length=24)),
            ("provider_reference", models.CharField(blank=True, max_length=255)),
            ("capture_reference", models.CharField(blank=True, max_length=255)),
            ("pix_qr_code", models.TextField(blank=True)),
            ("pix_qr_code_base64", models.TextField(blank=True)),
            ("approval_url", models.URLField(blank=True, max_length=2048)),
            ("customer_email", models.EmailField(max_length=254)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"constraints": [
            models.UniqueConstraint(fields=("site_id", "order_id", "order_version"), name="marketplace_one_charge_per_order_version"),
            models.UniqueConstraint(condition=~models.Q(provider_reference=""), fields=("method", "provider_reference"), name="marketplace_unique_provider_reference"),
        ]}),
        migrations.CreateModel(name="Recebivel", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("site_id", models.CharField(max_length=255)),
            ("order_id", models.UUIDField()),
            ("status", models.CharField(default="pendente_definicao", max_length=24)),
            ("provider_reference", models.CharField(blank=True, max_length=255)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("charge", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="recebivel", to="marketplace.charge")),
        ]),
    ]
