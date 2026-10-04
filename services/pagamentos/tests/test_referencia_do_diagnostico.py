"""A referência que o comprador vê no erro do Pix Appmax acha a tentativa.

A tela (checkout/static/checkout/dados.js `referenciaDiagnostico`) mostra
sha256 do id da sessão do checkout. O diagnóstico da VPS (ci/operacoes_vps.py)
roda dentro do contêiner de pagamentos e procura a tentativa por essa
referência. A chave de idempotência da intent deixou de ser a sessão (é a
compra inteira), então a ponte é `metadata.checkout_session_id`; as intents
antigas, sem esse metadata, tinham a sessão como chave.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import uuid
from pathlib import Path
from typing import Any

import pytest

from pagamentos.core.models import Intent, PaymentAttempt

pytestmark = pytest.mark.django_db(transaction=True)

_OPERACOES = Path(__file__).resolve().parents[3] / "ci" / "operacoes_vps.py"


@pytest.fixture
def operacoes(monkeypatch: pytest.MonkeyPatch, settings: Any):
    if not _OPERACOES.is_file():
        pytest.skip("ci/operacoes_vps.py fora desta árvore")
    spec = importlib.util.spec_from_file_location("operacoes_vps_ref", _OPERACOES)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    settings.APPMAX_AUTH_URL = modulo.APPMAX_AUTH_SANDBOX
    settings.APPMAX_API_URL = modulo.APPMAX_API_SANDBOX

    def rodar_no_conteiner(_servico: str, _identificador: str, codigo: str) -> str:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            exec(codigo, {})  # noqa: S102 — o mesmo código que vai ao shell do contêiner
        return saida.getvalue()

    monkeypatch.setattr(modulo, "comando", lambda *_a, **_k: "a" * 64)
    monkeypatch.setattr(modulo, "comando_shell", rodar_no_conteiner)
    return modulo


def _tentativa(chave: str, metadata: dict, site_id: str) -> PaymentAttempt:
    intent = Intent.objects.create(
        idempotency_key=chave,
        site_id=site_id,
        order_id=str(uuid.uuid4()),
        method="pix",
        status="pending",
        amount_cents=1005,
        currency="BRL",
        customer={"email": "cliente@exemplo.com"},
        metadata=metadata,
    )
    return PaymentAttempt.objects.create(
        intent=intent,
        platform_site_id=site_id,
        provider="appmax",
        request_hash="a" * 64,
        amount_cents=1005,
        effective_amount_cents=1005,
        state="failed",
        reason="appmax_diagnostico_campo_document_number",
    )


def _referencia_da_tela(sessao_id: str) -> str:
    # Igual a dados.js: SHA-256 do texto do id da sessão, em hexadecimal.
    return hashlib.sha256(sessao_id.encode()).hexdigest()


def test_referencia_da_tela_acha_a_intent_de_chave_da_compra(operacoes) -> None:
    sessao = uuid.uuid4()
    chave_da_compra = str(uuid.uuid5(sessao, '{"method": "pix"}'))
    _tentativa(
        chave_da_compra,
        {"checkout_session_id": str(sessao)},
        operacoes.SITE_MESHCRAFT,
    )
    _tentativa(
        str(uuid.uuid4()),
        {"checkout_session_id": str(uuid.uuid4())},
        operacoes.SITE_MESHCRAFT,
    )

    resumo = operacoes.medir("appmax-pix", "pagamentos", _referencia_da_tela(str(sessao)))

    assert resumo["tentativa"] == "failed"
    assert resumo["motivo"] == "campo_document_number"
    descoberta = operacoes.medir("appmax-pix", "pagamentos")
    assert _referencia_da_tela(str(sessao)) in {
        c["referencia"] for c in descoberta["candidatas"]
    }
    assert hashlib.sha256(chave_da_compra.encode()).hexdigest() not in {
        c["referencia"] for c in descoberta["candidatas"]
    }


def test_intent_antiga_sem_metadata_continua_achada_pela_chave(operacoes) -> None:
    sessao = str(uuid.uuid4())
    _tentativa(sessao, {}, operacoes.SITE_MESHCRAFT)

    resumo = operacoes.medir("appmax-pix", "pagamentos", _referencia_da_tela(sessao))

    assert resumo["tentativa"] == "failed"
