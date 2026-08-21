# apps/sites/models.py  # [RECEITA:R7 v1]
import uuid

from django.db import models


class Site(models.Model):
    """Registro canônico do multissítio (Lei 9). Host não cadastrado nunca
    resolve para um site — é 404 em quem consome (INV-P11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    theme = models.JSONField(default=dict, blank=True)
    default_offer_slug = models.CharField(max_length=255, blank=True, default="")

    def save(self, *args, **kwargs):
        self.host = self.host.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.host
# golpe4: comentario trivial e reversivel para teste de orcamento
