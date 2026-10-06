import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0004_pix_expires_at")]
    operations = [
        migrations.AddField("charge", "wallet_owner_id", models.CharField(blank=True, max_length=64)),
        migrations.AddField("charge", "customer_name_digest", models.CharField(blank=True, max_length=64)),
        migrations.AddField("charge", "customer_cpf_digest", models.CharField(blank=True, max_length=64)),
        migrations.CreateModel(name="WalletAccount", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("site_id", models.CharField(max_length=255)),
            ("environment", models.CharField(default="sandbox", max_length=16)),
            ("owner_kind", models.CharField(choices=[("client", "Cliente"), ("student", "Aluno")], max_length=16)),
            ("owner_id", models.CharField(max_length=64)),
            ("balance_cents", models.BigIntegerField(default=0)),
            ("frozen", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"constraints": [models.UniqueConstraint(
            fields=("site_id", "environment", "owner_kind", "owner_id"), name="marketplace_unique_wallet_account")]}),
        migrations.CreateModel(name="WalletEntry", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("operation_key", models.CharField(max_length=255, unique=True)),
            ("request_key", models.UUIDField(blank=True, null=True, unique=True)),
            ("kind", models.CharField(max_length=24)),
            ("amount_cents", models.BigIntegerField()),
            ("order_id", models.UUIDField(blank=True, null=True)),
            ("order_version", models.PositiveIntegerField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="marketplace.walletaccount")),
            ("charge", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="marketplace.charge")),
        ]),
        migrations.CreateModel(name="WithdrawalRequest", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("amount_cents", models.PositiveIntegerField()),
            ("status", models.CharField(default="requested", max_length=24)),
            ("authorization_reference", models.CharField(blank=True, max_length=160)),
            ("bank_reference", models.CharField(blank=True, max_length=160)),
            ("proof_reference", models.CharField(blank=True, max_length=160)),
            ("confirmed_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="marketplace.walletaccount")),
        ]),
    ]
