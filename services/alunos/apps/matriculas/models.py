# apps/matriculas/models.py
from django.db import models


class Matricula(models.Model):
    STATUS_ATIVA = "ativa"
    STATUS_SUSPENSA = "suspensa"
    STATUS_REEMBOLSADA = "reembolsada"
    STATUS_CHOICES = [
        (STATUS_ATIVA, "ativa"),
        (STATUS_SUSPENSA, "suspensa"),
        (STATUS_REEMBOLSADA, "reembolsada"),
    ]

    site_id = models.CharField(max_length=64)  # [INV-P5] guarda o site_id do evento
    order_id = models.CharField(
        max_length=128, unique=True
    )  # [INV-P5] chave de idempotência
    product_id = models.CharField(max_length=64, blank=True, default="")
    email = models.EmailField()
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVA
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["email"])]
