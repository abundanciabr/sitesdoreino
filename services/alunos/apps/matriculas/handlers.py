# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
from .services import matricular


def ao_pagamento_aprovado(data: dict) -> None:
    """[INV-P5] data é o campo `data` de pagamento.aprovado.v1 (contracts/eventos/).
    O evento não carrega product_id — fica vazio no caminho automático; o reprocesso
    manual (POST /matriculas) é quem pode informá-lo."""
    matricular(
        site_id=data["site_id"],
        order_id=data["order_id"],
        product_id="",
        email=data["customer"]["email"],
        name=data["customer"]["name"],
    )
