# apps/produtos/models.py  # [RECEITA:R7 v1]
import uuid

from django.db import models


class Product(models.Model):
    """Produto é global — quem é por site é a Offer (contracts/catalogo.openapi.yaml)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="Chave interna para seed/cadastro idempotente — não faz parte do contrato.",
    )
    name = models.CharField(max_length=255)
    price_cents = (
        models.PositiveIntegerField()
    )  # dinheiro é centavos inteiros — lei da plataforma
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name
# golpe4: comentario trivial e reversivel para teste de orcamento
