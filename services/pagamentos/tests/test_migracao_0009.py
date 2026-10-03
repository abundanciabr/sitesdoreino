from __future__ import annotations

import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from pagamentos.core.models import Intent, PaymentAttempt

pytestmark = pytest.mark.django_db(transaction=True)


def test_insert_do_codigo_antigo_sobrevive_a_migracao() -> None:
    anterior = ("core", "0008_appmaxwebhookinbox_redeliveries")
    nova = ("core", "0009_roteamento_pagamentos")
    executor = MigrationExecutor(connection)
    executor.migrate([anterior])
    try:
        antigo = executor.loader.project_state([anterior]).apps
        IntentAntiga = antigo.get_model("core", "Intent")
        AttemptAntiga = antigo.get_model("core", "PaymentAttempt")
        intent = IntentAntiga.objects.create(
            idempotency_key=str(uuid.uuid4()), site_id="site-antigo",
            order_id="ordem-antiga", method="card", amount_cents=1000,
            customer={"email": "teste@example.org"},
        )
        tentativa = AttemptAntiga.objects.create(
            intent=intent, platform_site_id="site-antigo", provider="appmax",
            amount_cents=1000, effective_amount_cents=1000,
            request_hash="a" * 64,
        )
    finally:
        MigrationExecutor(connection).migrate([nova])
    assert Intent.objects.get(pk=intent.pk).segunda_opcao_ate is None
    nova_tentativa = PaymentAttempt.objects.get(pk=tentativa.pk)
    assert nova_tentativa.estorno_estado is None
    assert nova_tentativa.estorno_solicitado_em is None
