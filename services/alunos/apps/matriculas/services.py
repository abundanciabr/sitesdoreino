# apps/matriculas/services.py
from django.db import IntegrityError, transaction

from .models import Matricula


def matricular(
    *, site_id: str, order_id: str, product_id: str, email: str, name: str
) -> tuple[Matricula, bool]:
    """[INV-P5] Matrícula sob select_for_update() + transaction.atomic(), idempotente
    por order_id. Chamada tanto pelo consumer do evento (R4) quanto pelo reprocesso
    manual (POST /matriculas) — as duas portas usam a MESMA idempotência.

    select_for_update() não trava linha que ainda não existe, então a corrida de
    criação é fechada pela unicidade de order_id: quem perde o INSERT recebe
    IntegrityError e lê a linha do vencedor sob lock (bloqueia até o commit dele).
    """
    with transaction.atomic():
        existente = (
            Matricula.objects.select_for_update().filter(order_id=order_id).first()
        )
        if existente is not None:
            return existente, False
        try:
            with transaction.atomic():
                nova = Matricula.objects.create(
                    site_id=site_id,
                    order_id=order_id,
                    product_id=product_id,
                    email=email,
                    name=name,
                )
            return nova, True
        except IntegrityError:
            return Matricula.objects.select_for_update().get(order_id=order_id), False
