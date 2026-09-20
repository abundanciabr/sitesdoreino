# tests/test_inv_p5_matricula_lock.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante (INVARIANTES.md).
import threading

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

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


def _insercoes_de_matricula(consultas):
    tabela = Matricula._meta.db_table
    return [
        c["sql"]
        for c in consultas.captured_queries
        if "INSERT INTO" in c["sql"].upper() and tabela in c["sql"]
    ]


def test_reentrega_le_a_matricula_existente_em_vez_de_tentar_criar_de_novo():
    """O teste acima mede o RESULTADO (uma matrícula só), e a unicidade de
    `order_id` entrega esse resultado sozinha: sem a leitura sob lock, o
    segundo consumer leva IntegrityError e lê a linha do vencedor. Foi assim
    que apagar o `select_for_update()` de `matricular()` deixou este arquivo
    verde.

    O que a leitura guarda é o CAMINHO. Entrega at-least-once faz da reentrega
    o caso normal, não a exceção, e o caminho normal não pode ser um INSERT que
    o banco rejeita: isso transforma o `except IntegrityError` de
    `matricular()`, feito para a corrida rara de criação, no caminho comum.

    A primeira chamada é medida junto, de propósito: ela é o controle positivo
    que prova que este detector enxerga um INSERT quando existe um.
    """
    order_id = EVENTO_DATA["order_id"]

    with CaptureQueriesContext(connection) as primeira:
        ao_pagamento_aprovado(EVENTO_DATA)
    assert _insercoes_de_matricula(primeira), (
        "o detector de INSERT não viu a criação da matrícula; ele está cego e "
        "a asserção de baixo passaria vazia. Confira se o SQL capturado ainda "
        f"cita a tabela {Matricula._meta.db_table}."
    )

    with CaptureQueriesContext(connection) as reentrega:
        ao_pagamento_aprovado(EVENTO_DATA)  # o MESMO evento, de novo

    tentativas = _insercoes_de_matricula(reentrega)
    assert not tentativas, (
        "a reentrega tentou criar a matrícula de novo em vez de ler a que já "
        "existe. Devolva a leitura idempotente ao começo de matricular(), "
        f"antes do try: {tentativas}"
    )
    assert Matricula.objects.filter(order_id=order_id).count() == 1
