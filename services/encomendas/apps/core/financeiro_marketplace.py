"""Ponte de encomendas para a cobrança isolada na célula pagamentos."""
from __future__ import annotations

import os
import uuid

import httpx


class PagamentoIndisponivel(RuntimeError):
    pass


class PagamentoDivergente(ValueError):
    pass


def _endpoint() -> tuple[str, dict[str, str]]:
    token = os.environ.get("PAGAMENTOS_API_TOKEN", "")
    if not token:
        raise PagamentoIndisponivel("par encomendas → pagamentos não configurado")
    return "http://pagamentos:8000/api/pagamentos/marketplace", {"Authorization": "Bearer " + token}


def _pedido(pedido) -> tuple[str, str, int, int, str, str]:
    return (
        str(pedido.site_id), str(pedido.pk), int(pedido.versao),
        int(pedido.valor_cents), str(pedido.moeda), str(pedido.ambiente),
    )


def situacao_do_ambiente() -> dict:
    """Só disponibilidade; nenhuma credencial sai para a tela da escola."""
    try:
        base, headers = _endpoint()
        data = _pedir("GET", base + "/status", headers=headers)
    except PagamentoIndisponivel:
        return {"disponivel": False}
    return {
        "disponivel": data.get("environment") == "sandbox",
        "pix": data.get("pix_configured") is True,
        "paypal": data.get("paypal_configured") is True,
    }


def _validar_resposta(pedido, data: dict) -> None:
    site, order_id, version, amount, currency, environment = _pedido(pedido)
    if (str(data.get("site_id")), str(data.get("order_id")), data.get("order_version"),
        data.get("amount_cents"), data.get("currency"), data.get("environment")) != (
        site, order_id, version, amount, currency, environment):
        raise PagamentoDivergente("cobrança pertence a outro pedido, versão ou valor")
    if data.get("method") not in {"pix", "paypal"} or not data.get("id"):
        raise PagamentoDivergente("cobrança sem identificação válida")


def _pedir(method: str, url: str, *, headers: dict, body: dict | None = None) -> dict:
    try:
        response = httpx.request(method, url, headers=headers, json=body, timeout=20)
        if response.status_code == 404:
            return {"status": "absent"}
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PagamentoIndisponivel("cobrança não confirmada pela célula pagamentos") from exc
    if not isinstance(data, dict):
        raise PagamentoIndisponivel("resposta de pagamentos inválida")
    return data


def _aplicar_confirmacao(pedido, data: dict) -> dict:
    _validar_resposta(pedido, data)
    if data.get("status") != "approved":
        return data
    if not data.get("reference"):
        raise PagamentoDivergente("aprovação sem referência do provedor")
    # Releitura local impede usar uma tela velha após edição da encomenda.
    pedido.refresh_from_db()
    _validar_resposta(pedido, data)
    from apps.encomendas.marketplace import confirmar_pagamento

    site, order_id, version, amount, currency, environment = _pedido(pedido)
    confirmar_pagamento(
        site_id=site, pedido_id=order_id, versao=version,
        valor_cents=amount, moeda=currency, ambiente=environment,
        referencia=str(data["id"]),
    )
    return data


def iniciar_cobranca(pedido, *, metodo: str, email: str, nome: str = "",
                     chave_idempotencia: str | None = None) -> dict:
    """Chamado só depois de autenticar o cliente titular no servidor de encomendas."""
    if pedido.status != "aguardando_pagamento" or metodo not in {"pix", "paypal"}:
        raise PagamentoDivergente("pedido não está disponível para cobrança")
    site, order_id, version, amount, currency, environment = _pedido(pedido)
    if environment != "sandbox":
        raise PagamentoIndisponivel("a Fila do Dólar só cobra em sandbox nesta fase")
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fila-do-dolar:{site}:{order_id}:{version}"))
    if chave_idempotencia and str(uuid.UUID(str(chave_idempotencia))) != key:
        raise PagamentoDivergente("chave de idempotência divergente")
    base, headers = _endpoint()
    result = _pedir("POST", base + "/charges", headers=headers, body={
        "idempotency_key": key, "site_id": site, "order_id": order_id,
        "order_version": version, "amount_cents": amount, "currency": currency,
        "environment": environment, "method": metodo, "customer_email": email,
    })
    return _aplicar_confirmacao(pedido, result)


def consultar_cobranca(pedido, *, capturar_paypal: bool = False) -> dict:
    site, order_id, version, _, _, _ = _pedido(pedido)
    base, headers = _endpoint()
    headers["X-Site-Id"] = site
    result = _pedir("GET", f"{base}/orders/{order_id}/charge?version={version}", headers=headers)
    if result.get("status") == "absent":
        return result
    _validar_resposta(pedido, result)
    if capturar_paypal and result["method"] == "paypal" and result["status"] != "approved":
        result = _pedir("POST", f"{base}/charges/{result['id']}/capture", headers=headers)
    return _aplicar_confirmacao(pedido, result)


def consumir_evento_aprovado(data: dict) -> dict:
    """Consumidor da outbox: reconsulta o provedor antes de mudar a encomenda."""
    from apps.encomendas.models import PedidoMarketplace

    site_id = str(data.get("site_id") or "")
    order_id = str(data.get("order_id") or "")
    if not site_id or not order_id:
        raise PagamentoDivergente("evento sem pedido")
    pedido = PedidoMarketplace.objects.filter(pk=order_id, site_id=site_id).first()
    if pedido is None:
        raise PagamentoDivergente("pedido do evento não existe neste site")
    if (data.get("order_version"), data.get("amount_cents"),
        data.get("currency"), data.get("environment")) != (
        pedido.versao, pedido.valor_cents, pedido.moeda, pedido.ambiente):
        raise PagamentoDivergente("evento de pagamento diverge do pedido")
    result = consultar_cobranca(pedido)
    if result.get("id") != str(data.get("charge_id")) or result.get("status") != "approved":
        raise PagamentoDivergente("evento não corresponde a pagamento aprovado")
    return result


def registrar_recebivel_da_entrega(pedido) -> dict:
    """Registra o aluno destinatário depois da aprovação da entrega, sem repasse."""
    if pedido.status != "aprovado" or not pedido.aluno_id or not pedido.pagamento_referencia:
        raise PagamentoDivergente("entrega ainda não aprovada e paga")
    aluno_id = str(pedido.aluno.pessoa_id)
    base, headers = _endpoint()
    site, order_id, version, _, _, _ = _pedido(pedido)
    data = _pedir("POST", base + "/receivables", headers=headers, body={
        "charge_id": pedido.pagamento_referencia,
        "site_id": site, "order_id": order_id,
        "order_version": version, "aluno_id": aluno_id,
    })
    if (data.get("site_id"), data.get("order_id"), data.get("order_version"),
        data.get("aluno_id"), data.get("charge_id")) != (
        site, order_id, version, aluno_id, pedido.pagamento_referencia):
        raise PagamentoDivergente("recebível financeiro divergente")
    return data
