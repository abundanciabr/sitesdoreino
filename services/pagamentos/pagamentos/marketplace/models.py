"""Cobranças de encomendas, independentes das Intents de cursos."""
from __future__ import annotations

import uuid
from django.db import models


class Charge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True)
    site_id = models.CharField(max_length=255)
    order_id = models.UUIDField()
    order_version = models.PositiveIntegerField()
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    environment = models.CharField(max_length=16, default="sandbox")
    method = models.CharField(max_length=10, choices=[("pix", "Pix"), ("paypal", "PayPal")])
    status = models.CharField(max_length=24, default="created")
    provider_reference = models.CharField(max_length=255, blank=True)
    capture_reference = models.CharField(max_length=255, blank=True)
    pix_qr_code = models.TextField(blank=True)
    pix_qr_code_base64 = models.TextField(blank=True)
    pix_expires_at = models.DateTimeField(null=True, blank=True)
    approval_url = models.URLField(max_length=2048, blank=True)
    paypal_return_base = models.URLField(max_length=2048, blank=True)
    capture_started_at = models.DateTimeField(null=True, blank=True)
    customer_email = models.EmailField()
    customer_name_digest = models.CharField(max_length=64, blank=True)
    customer_cpf_digest = models.CharField(max_length=64, blank=True)
    wallet_owner_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site_id", "order_id", "order_version"], name="marketplace_one_charge_per_order_version"),
            models.UniqueConstraint(fields=["method", "provider_reference"], condition=~models.Q(provider_reference=""), name="marketplace_unique_provider_reference"),
        ]


class Recebivel(models.Model):
    """Registro separado do repasse; sem decisão comercial não há instrução de envio."""
    charge = models.OneToOneField(Charge, on_delete=models.PROTECT, related_name="recebivel")
    site_id = models.CharField(max_length=255)
    order_id = models.UUIDField()
    aluno_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, default="pendente_definicao")
    provider_reference = models.CharField(max_length=255, blank=True)
    valor_liquido_cents = models.PositiveIntegerField(null=True, blank=True)
    taxas_cents = models.PositiveIntegerField(null=True, blank=True)
    autorizacao_mantenedor_referencia = models.CharField(max_length=160, blank=True)
    comprovante_referencia = models.CharField(max_length=160, blank=True)
    repasse_confirmado_em = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WalletAccount(models.Model):
    site_id = models.CharField(max_length=255)
    environment = models.CharField(max_length=16, default="sandbox")
    owner_kind = models.CharField(max_length=16, choices=[("client", "Cliente"), ("student", "Aluno")])
    owner_id = models.CharField(max_length=64)
    balance_cents = models.BigIntegerField(default=0)
    frozen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["site_id", "environment", "owner_kind", "owner_id"], name="marketplace_unique_wallet_account")]


class WalletEntry(models.Model):
    operation_key = models.CharField(max_length=255, unique=True)
    request_key = models.UUIDField(null=True, blank=True, unique=True)
    account = models.ForeignKey(WalletAccount, on_delete=models.PROTECT, related_name="entries")
    kind = models.CharField(max_length=24)
    amount_cents = models.BigIntegerField()
    order_id = models.UUIDField(null=True, blank=True)
    order_version = models.PositiveIntegerField(null=True, blank=True)
    charge = models.ForeignKey(Charge, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class WithdrawalRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(WalletAccount, on_delete=models.PROTECT)
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=24, default="requested")
    authorization_reference = models.CharField(max_length=160, blank=True)
    bank_reference = models.CharField(max_length=160, blank=True)
    proof_reference = models.CharField(max_length=160, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
