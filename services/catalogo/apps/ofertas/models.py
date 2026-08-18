# apps/ofertas/models.py  # [RECEITA:R7 v1]
import uuid

from django.db import models


class Offer(models.Model):
    """[INV-P11] slug único POR site — nunca globalmente.
    Publicada não é editada destrutivamente: mudar preço nasce como nova
    version (mecanismo completo de histórico é FORA DE ESCOPO deste despacho)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        "sites.Site", on_delete=models.CASCADE, related_name="ofertas"
    )
    slug = models.SlugField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    product = models.ForeignKey(
        "produtos.Product", on_delete=models.PROTECT, related_name="ofertas"
    )
    price_cents = (
        models.PositiveIntegerField()
    )  # dinheiro é centavos inteiros — lei da plataforma

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="oferta_unica_por_site"
            ),
            models.CheckConstraint(
                check=models.Q(price_cents__gte=1), name="oferta_price_cents_gte_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.site_id}:{self.slug}"


class Bump(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="bumps")
    product = models.ForeignKey(
        "produtos.Product", on_delete=models.PROTECT, related_name="bumps"
    )
    name = models.CharField(max_length=255)
    price_cents = (
        models.PositiveIntegerField()
    )  # dinheiro é centavos inteiros — lei da plataforma
    headline = models.CharField(max_length=255, blank=True, default="")

    def __str__(self) -> str:
        return self.name
