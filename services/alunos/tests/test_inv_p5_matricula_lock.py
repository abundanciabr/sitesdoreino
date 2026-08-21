# tests/test_inv_p5_matricula_lock.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante (INVARIANTES.md).
import threading

import pytest
from django.db import connection

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db(transaction=True)

EVENTO_DATA = {
    "site_id": "site-1",
    "payment_id": "pay-1",
    "order_id": "order-concorrente",
    "amount_cents": 9900,
    "method": "pix",
    "mp_payment_id": "mp-1",
    "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
}


def test_dois_consumers_mesmo_evento_em_threads_geram_uma_matricula():
    barreira = threading.Barrier(2)
    erros = []

    def processar():
        try:
            barreira.wait(timeout=5)
            ao_pagamento_aprovado(EVENTO_DATA)
        except Exception as exc:  # pragma: no cover - não engolir falha da thread
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=processar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros, erros
    assert Matricula.objects.filter(order_id="order-concorrente").count() == 1
