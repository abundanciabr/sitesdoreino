"""Porta da carteira mantida exclusivamente pela célula pagamentos."""
from __future__ import annotations

import uuid

from apps.core.financeiro_marketplace import (
    PagamentoDivergente, PagamentoIndisponivel, _endpoint, _pedir,
)


def _chave(pedido_id, operacao: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"marketplace:{operacao}:{pedido_id}"))


def saldo(*, site_id: str, pessoa_id: str, tipo: str) -> dict:
    if tipo not in {"client", "students"}:
        raise ValueError("tipo de carteira inválido")
    base, headers = _endpoint()
    headers["X-Site-Id"] = site_id
    data = _pedir("GET", f"{base}/wallets/{tipo}/{pessoa_id}", headers=headers)
    if (data.get("site_id") != site_id or data.get("owner_id") != pessoa_id
            or data.get("environment") != "sandbox"):
        raise PagamentoDivergente("carteira pertence a outra pessoa ou escola")
    if not isinstance(data.get("balance_cents"), int):
        raise PagamentoDivergente("saldo da carteira inválido")
    return data


def extrato_aluno(*, site_id: str, aluno_id: str) -> dict:
    base, headers = _endpoint()
    headers["X-Site-Id"] = site_id
    data = _pedir("GET", f"{base}/wallets/students/{aluno_id}/statement", headers=headers)
    if (data.get("site_id") != site_id or data.get("owner_id") != aluno_id
            or data.get("environment") != "sandbox" or not isinstance(data.get("balance_cents"), int)):
        raise PagamentoDivergente("extrato pertence a outro aluno ou escola")
    return data


def saques_da_escola(*, site_id: str) -> list[dict]:
    base, headers = _endpoint()
    headers["X-Site-Id"] = site_id
    data = _pedir("GET", base + "/wallets/withdrawals", headers=headers)
    saques = data.get("withdrawals")
    if not isinstance(saques, list) or any(
        not isinstance(item, dict) or item.get("site_id") != site_id for item in saques
    ):
        raise PagamentoDivergente("saques de outra escola")
    return saques


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or len(set(cpf)) == 1:
        return False
    for tamanho in (9, 10):
        digito = (sum(int(numero) * peso for numero, peso in zip(
            cpf[:tamanho], range(tamanho + 1, 1, -1),
        )) * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False
    return True


def iniciar_recarga(*, site_id: str, cliente_id: str, valor_cents: int,
                    chave_idempotencia: str, email: str, nome: str, cpf: str) -> dict:
    cpf = "".join(c for c in cpf if c.isdigit())
    if (valor_cents < 100 or valor_cents % 100 or not email or "@" not in email
            or len(nome.split()) < 2 or not _cpf_valido(cpf)):
        raise PagamentoDivergente("recarga exige créditos inteiros e dados do pagador válidos")
    base, headers = _endpoint()
    data = _pedir("POST", base + "/wallets/topups", headers=headers, body={
        "site_id": site_id, "client_id": cliente_id, "amount_cents": valor_cents,
        "idempotency_key": str(uuid.UUID(str(chave_idempotencia))),
        "customer_email": email, "customer_name": nome.strip(), "customer_cpf": cpf,
    })
    if (data.get("site_id"), data.get("wallet_owner_id"), data.get("amount_cents"),
            data.get("method"), data.get("environment")) != (
        site_id, cliente_id, valor_cents, "pix", "sandbox"
    ) or not data.get("id"):
        raise PagamentoDivergente("recarga Pix divergente")
    return data


def consultar_recarga(*, site_id: str, cliente_id: str, charge_id: str) -> dict:
    base, headers = _endpoint()
    headers["X-Site-Id"] = site_id
    data = _pedir("GET", f"{base}/charges/{charge_id}", headers=headers)
    if (data.get("site_id") != site_id or str(data.get("id")) != str(charge_id)
            or data.get("wallet_owner_id") != cliente_id):
        raise PagamentoDivergente("recarga pertence a outro cliente ou site")
    return data


def usar_creditos(pedido) -> dict:
    if pedido.ambiente != "sandbox" or pedido.status != "aguardando_pagamento":
        raise PagamentoDivergente("pedido não disponível para compra com créditos")
    base, headers = _endpoint()
    data = _pedir("POST", base + "/wallets/orders", headers=headers, body={
        "site_id": str(pedido.site_id), "client_id": pedido.cliente_id,
        "order_id": str(pedido.pk), "order_version": pedido.versao,
        "amount_cents": pedido.valor_cents,
        "idempotency_key": _chave(pedido.pk, f"spend:{pedido.versao}"),
    })
    if (str(data.get("order_id")), data.get("status"), data.get("amount_cents")) != (
        str(pedido.pk), "debited", pedido.valor_cents,
    ):
        raise PagamentoDivergente("débito de créditos divergente")
    return data


def creditar_aluno(pedido) -> dict:
    if pedido.status != "aprovado" or not pedido.aluno_id or not pedido.pagamento_referencia.startswith("wallet-spend:"):
        raise PagamentoDivergente("pedido ainda não aprovado para crédito do aluno")
    base, headers = _endpoint()
    data = _pedir("POST", base + "/wallets/student-credits", headers=headers, body={
        "site_id": str(pedido.site_id), "aluno_id": pedido.aluno.pessoa_id,
        "order_id": str(pedido.pk), "order_version": pedido.versao,
        "amount_cents": pedido.valor_cents,
        "idempotency_key": _chave(pedido.pk, f"earn:{pedido.versao}"),
    })
    if (str(data.get("order_id")), data.get("status"), data.get("amount_cents")) != (
        str(pedido.pk), "credited", pedido.valor_cents,
    ):
        raise PagamentoDivergente("crédito do aluno divergente")
    return data


def solicitar_saque(*, site_id: str, aluno_id: str, valor_cents: int,
                    chave_idempotencia: str) -> dict:
    if valor_cents < 5000 or valor_cents % 100:
        raise PagamentoDivergente("saque mínimo de 50 créditos inteiros")
    base, headers = _endpoint()
    data = _pedir("POST", base + "/wallets/withdrawals", headers=headers, body={
        "site_id": site_id, "aluno_id": aluno_id,
        "amount_cents": valor_cents,
        "idempotency_key": str(uuid.UUID(str(chave_idempotencia))),
    })
    if data.get("status") != "requested" or data.get("amount_cents") != valor_cents:
        raise PagamentoDivergente("solicitação de saque divergente")
    return data
