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
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone

from pagamentos.core.models import Intent, PaymentAttempt
from pagamentos.providers.appmax.client import AppmaxClient

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
        try:
            with contextlib.redirect_stdout(saida):
                exec(codigo, {})  # noqa: S102 — o mesmo código que vai ao shell do contêiner
        except SystemExit as saida_do_shell:
            # No contêiner, `exit(0)` encerra o comando sem erro; outro código é falha.
            if saida_do_shell.code not in (0, None):
                raise modulo.Falha("comando") from None
        except Exception:
            # Exceção no shell do contêiner = saída diferente de zero = Falha do `comando`.
            raise modulo.Falha("comando") from None
        return saida.getvalue()

    monkeypatch.setattr(modulo, "comando", lambda *_a, **_k: "a" * 64)
    monkeypatch.setattr(modulo, "comando_shell", rodar_no_conteiner)
    return modulo


def _tentativa(
    chave: str,
    metadata: dict,
    site_id: str,
    *,
    motivo: str = "appmax_diagnostico_campo_document_number",
    pedido: str = "",
    cliente: str = "",
    estado: str = "failed",
) -> PaymentAttempt:
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
        state=estado,
        reason=motivo,
        external_order_id=pedido,
        customer_id=cliente,
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


def _sessao_com_duas_tentativas(
    operacoes, antiga: dict, recente: dict
) -> tuple[str, PaymentAttempt, PaymentAttempt]:
    """O comprador corrige CPF/e-mail/telefone depois da falha: a mesma sessão
    ganha outra intent (chave uuid5 diferente), com a mesma referência na tela.
    """
    sessao = uuid.uuid4()
    metadata = {"checkout_session_id": str(sessao)}
    a = _tentativa(
        str(uuid.uuid5(sessao, '{"method": "pix", "cpf": "antigo"}')),
        metadata,
        operacoes.SITE_MESHCRAFT,
        **antiga,
    )
    b = _tentativa(
        str(uuid.uuid5(sessao, '{"method": "pix", "cpf": "corrigido"}')),
        metadata,
        operacoes.SITE_MESHCRAFT,
        **recente,
    )
    agora = timezone.now()
    PaymentAttempt.objects.filter(pk=a.pk).update(created_at=agora - timedelta(minutes=5))
    PaymentAttempt.objects.filter(pk=b.pk).update(created_at=agora)
    return _referencia_da_tela(str(sessao)), a, b


def test_duas_intents_da_mesma_sessao_medem_a_tentativa_mais_recente(operacoes) -> None:
    referencia, _antiga, _recente = _sessao_com_duas_tentativas(
        operacoes,
        {"motivo": "appmax_diagnostico_campo_expiration_date"},
        {"motivo": "appmax_diagnostico_campo_document_number"},
    )

    resumo = operacoes.medir("appmax-pix", "pagamentos", referencia)

    assert resumo["motivo"] == "campo_document_number"
    descoberta = operacoes.medir("appmax-pix", "pagamentos")
    # A descoberta lista uma candidata por referência: a mais recente.
    mesma_sessao = [c for c in descoberta["candidatas"] if c["referencia"] == referencia]
    assert [c["motivo"] for c in mesma_sessao] == ["campo_document_number"]


def test_referencia_sem_nenhuma_tentativa_continua_dando_erro(operacoes) -> None:
    with pytest.raises(operacoes.Falha):
        operacoes.medir(
            "appmax-pix", "pagamentos", _referencia_da_tela(str(uuid.uuid4()))
        )


def test_aviso_com_duas_intents_da_mesma_sessao_acha_a_candidata(operacoes) -> None:
    referencia, _antiga, _recente = _sessao_com_duas_tentativas(operacoes, {}, {})

    resumo = operacoes.medir("appmax-pix-aviso", "pagamentos", referencia)

    # Sem instalação cadastrada o aviso não se mede, mas a candidata foi achada.
    assert resumo["acao"] == "instalacao_ausente"


def test_latencia_com_duas_intents_da_mesma_sessao_usa_a_mais_recente(operacoes) -> None:
    referencia, _antiga, _recente = _sessao_com_duas_tentativas(
        operacoes, {"pedido": "5501"}, {"pedido": ""}
    )

    resumo = operacoes.medir("appmax-inbox-latencia", "pagamentos", referencia)

    # A mais recente ainda não tem pedido; a antiga tem, e não pode ser a medida.
    assert resumo["acao"] == "pedido_ausente"


def test_pedido_com_duas_intents_da_mesma_sessao_consulta_a_mais_recente(
    operacoes, monkeypatch: pytest.MonkeyPatch
) -> None:
    consultados: list[int] = []

    def consultar_pedido(_cliente, pedido_id: int) -> dict:
        consultados.append(pedido_id)
        return {}

    monkeypatch.setattr(AppmaxClient, "consultar_pedido", consultar_pedido)
    referencia, _antiga, _recente = _sessao_com_duas_tentativas(
        operacoes,
        {"pedido": "5501", "cliente": "9001"},
        {"pedido": "5502", "cliente": "9001"},
    )

    resumo = operacoes.medir("appmax-pix-pedido", "pagamentos", referencia)

    assert consultados == [5502]
    assert resumo["acao"] == "identidade_nao_comprovada"


def test_pendentes_com_duas_tentativas_abertas_da_mesma_sessao_lista_a_mais_recente(
    operacoes,
) -> None:
    # Cada intent da sessão tem a mesma referência (a da tela); duas abertas ao
    # mesmo tempo não podem fazer o validador do host ver referência repetida.
    referencia, _antiga, _recente = _sessao_com_duas_tentativas(
        operacoes,
        {"estado": "reconciliation_required"},
        {"estado": "pending"},
    )
    _tentativa(
        str(uuid.uuid4()),
        {"checkout_session_id": str(uuid.uuid4())},
        operacoes.SITE_MESHCRAFT,
        estado="pending",
    )

    resultado = operacoes.medir("appmax-pendentes", "pagamentos")

    assert len(resultado["tentativas"]) == 2
    mesma_sessao = [t for t in resultado["tentativas"] if t["referencia"] == referencia]
    assert [t["estado_tentativa"] for t in mesma_sessao] == ["pending"]
