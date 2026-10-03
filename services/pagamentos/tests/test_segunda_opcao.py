from __future__ import annotations

import threading
import uuid
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt, PaymentOperation
from pagamentos.core.tentativas import (
    ResultadoDoProvedor,
    SegundaOpcaoIndisponivel,
    abrir_segunda_opcao,
    executar_tentativa,
    fechar_segundas_opcoes_vencidas,
    hash_da_tentativa,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _intent() -> Intent:
    return Intent.objects.create(
        idempotency_key=str(uuid.uuid4()), site_id="site", order_id="ordem",
        method="card", status="pending", amount_cents=1000,
        customer={"email": "teste@example.org", "name": "Teste"},
    )


def _enviar(tentativa: PaymentAttempt) -> ResultadoDoProvedor:
    assert PaymentOperation.objects.filter(
        attempt=tentativa, operation_type="payment", state="sending"
    ).exists()
    return ResultadoDoProvedor(aprovada=False, provider_reference_id="mp-1", motivo="recusado")


def test_hash_appmax_antigo_e_mp_isolado() -> None:
    corpo = {"token": "tok-antigo", "valor": 1000}
    from pagamentos.core.tentativas import _hash_do_corpo

    assert hash_da_tentativa(corpo) == _hash_do_corpo(corpo)
    assert hash_da_tentativa(corpo, provider="mercadopago") != hash_da_tentativa(corpo)


def test_janela_consumida_e_operacao_mp_commitada() -> None:
    intent = _intent()
    abrir_segunda_opcao(intent)
    tentativa = executar_tentativa(
        intent=intent, provider="mercadopago", corpo={"token": "mp"},
        enviar=_enviar, consumir_segunda_opcao=True,
    )
    assert tentativa.fechada_agora is True
    assert tentativa.state == "rejected"
    assert PaymentOperation.objects.get(attempt=tentativa).state == "completed"
    intent.refresh_from_db()
    assert intent.segunda_opcao_ate is None
    with pytest.raises(SegundaOpcaoIndisponivel):
        executar_tentativa(
            intent=intent, provider="mercadopago", corpo={"token": "mp-2"},
            enviar=_enviar, consumir_segunda_opcao=True,
        )
    assert PaymentAttempt.objects.filter(intent=intent).count() == 1


def test_janela_vencida_recusa_uma_vez_sem_cobrar() -> None:
    intent = _intent()
    abrir_segunda_opcao(intent)
    Intent.objects.filter(pk=intent.pk).update(segunda_opcao_ate=timezone.now() - timedelta(seconds=1))
    assert fechar_segundas_opcoes_vencidas(intent) == 1
    assert fechar_segundas_opcoes_vencidas(intent) == 0
    assert PaymentAttempt.objects.filter(intent=intent).count() == 0
    assert OutboxEvent.objects.filter(event="pagamento.recusado", version=2).count() == 1
    intent.refresh_from_db()
    assert intent.status == "rejected"


def test_corrida_consumo_e_vencimento_escolhe_um_resultado() -> None:
    intent = _intent()
    abrir_segunda_opcao(intent)
    barreira = threading.Barrier(2)
    resultados: list[str] = []
    erros: list[BaseException] = []

    def consumir() -> None:
        try:
            barreira.wait()
            executar_tentativa(
                intent=intent, provider="mercadopago", corpo={"token": "mp"},
                enviar=_enviar, consumir_segunda_opcao=True,
            )
            resultados.append("cobrou")
        except SegundaOpcaoIndisponivel:
            resultados.append("fechou")
        except BaseException as exc:
            erros.append(exc)
        finally:
            connection.close()

    def vencer() -> None:
        try:
            barreira.wait()
            with transaction.atomic():
                travada = Intent.objects.select_for_update().get(pk=intent.pk)
                if travada.segunda_opcao_ate is not None:
                    travada.segunda_opcao_ate = timezone.now() - timedelta(seconds=1)
                    travada.save(update_fields=["segunda_opcao_ate"])
            fechar_segundas_opcoes_vencidas(intent)
        except BaseException as exc:
            erros.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=consumir), threading.Thread(target=vencer)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert not erros
    intent.refresh_from_db()
    assert (PaymentAttempt.objects.filter(intent=intent, provider="mercadopago").exists()) != (intent.status == "rejected")
    assert len(resultados) == 1
