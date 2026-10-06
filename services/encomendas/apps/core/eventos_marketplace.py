"""Efeitos locais e cartas da outbox da Fila do Dólar."""
from __future__ import annotations

import uuid

from django.db import transaction

from apps.encomendas.marketplace import acesso_aluno, acesso_cliente
from apps.encomendas.models import (
    EventoMarketplace, OfertaMarketplace, OutboxMarketplace, PedidoMarketplace,
    RecargaMarketplace,
)


ASSUNTOS = {
    "marketplace.oferta_criada": ("aluno", "marketplace.oferta"),
    "marketplace.acordo_aceito": ("cliente", "marketplace.acordo"),
    "marketplace.entrega_enviada": ("cliente", "marketplace.entrega"),
    "marketplace.ajuste_pedido": ("aluno", "marketplace.ajuste"),
    "marketplace.entrega_aprovada": ("aluno", "marketplace.aprovacao"),
    "marketplace.pagamento_confirmado": ("cliente", "marketplace.pagamento"),
    "marketplace.recebimento_confirmado": ("aluno", "marketplace.recebimento"),
}


def _recarga(envelope: dict, dados: dict) -> None:
    """Confere o fato financeiro e avisa somente o titular da recarga local."""
    from apps.core.carteira_marketplace import consultar_recarga, PagamentoDivergente

    site = str(dados.get("site_id") or "")
    cliente = str(dados.get("wallet_owner_id") or "")
    charge_id = str(dados.get("charge_id") or "")
    try:
        chave = uuid.UUID(str(dados.get("idempotency_key")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("recarga sem chave") from exc
    recarga = RecargaMarketplace.objects.filter(pk=chave, site_id=site, cliente_id=cliente).first()
    if not recarga or (recarga.charge_id and recarga.charge_id != charge_id):
        raise ValueError("recarga sem titular local")
    financeiro = consultar_recarga(site_id=site, cliente_id=cliente, charge_id=charge_id)
    status_esperado = "approved" if envelope["event"] == "marketplace.recarga.aprovada" else None
    estados_reversao = {"refunded", "partially_refunded", "charged_back", "cancelled"}
    if (financeiro.get("amount_cents") != recarga.valor_cents
            or financeiro.get("environment") != "sandbox"
            or financeiro.get("currency") != "BRL"
            or str(financeiro.get("idempotency_key")) != str(chave)
            or (status_esperado and financeiro.get("status") not in ({status_esperado} | estados_reversao))
            or (not status_esperado and financeiro.get("status") not in estados_reversao)):
        raise PagamentoDivergente("fato de recarga diverge do provedor")
    with transaction.atomic():
        if not recarga.charge_id:
            recarga.charge_id = charge_id
            recarga.save(update_fields=["charge_id"])
        if status_esperado and financeiro["status"] in estados_reversao:
            return
        assunto = "marketplace.recarga" if status_esperado else "marketplace.recarga_revertida"
        origem = str(envelope["event_id"])
        chave_aviso = f"aviso:{uuid.uuid5(uuid.NAMESPACE_URL, f'{origem}:{cliente}')}"
        evento, criado = EventoMarketplace.objects.get_or_create(
            chave=chave_aviso,
            defaults={"site_id": site, "pedido": None, "tipo": "notificacao.devida.v1",
                      "dados": {"origem_event_id": origem}},
        )
        if criado and acesso_cliente(site_id=site, cliente_id=cliente):
            OutboxMarketplace.objects.create(
                site_id=site, evento=evento, event="notificacao.devida", version=1,
                event_id=uuid.uuid5(uuid.NAMESPACE_URL, chave_aviso),
                payload={"site_id": site, "destinatario_id": cliente,
                         "assunto": assunto,
                         "parametros": {"recarga_id": str(recarga.pk),
                                        "creditos": recarga.valor_cents // 100},
                         "origem_event_id": origem},
            )


def _carta(envelope: dict, pedido: PedidoMarketplace) -> None:
    tipo = envelope["event"]
    papel, assunto = ASSUNTOS[tipo]
    dados = envelope["data"]
    site = str(pedido.site_id)
    if papel == "aluno":
        if tipo == "marketplace.oferta_criada":
            oferta = OfertaMarketplace.objects.filter(
                pk=dados.get("oferta_id"), pedido=pedido, site_id=site,
            ).select_related("aluno").first()
            if not oferta or str(oferta.aluno_id) != str(dados.get("aluno_id")):
                return
            destinatario = oferta.aluno.pessoa_id
        else:
            destinatario = pedido.aluno.pessoa_id if pedido.aluno_id else None
        if not destinatario or not acesso_aluno(site_id=site, pessoa_id=destinatario):
            return
    else:
        destinatario = pedido.cliente_id
        if not acesso_cliente(site_id=site, cliente_id=destinatario):
            return
    origem = str(envelope["event_id"])
    chave = f"aviso:{uuid.uuid5(uuid.NAMESPACE_URL, f'{origem}:{destinatario}')}"
    with transaction.atomic():
        evento, criado = EventoMarketplace.objects.get_or_create(
            chave=chave,
            defaults={"site_id": site, "pedido": pedido,
                      "tipo": "notificacao.devida.v1", "dados": {"origem_event_id": origem}},
        )
        if criado:
            OutboxMarketplace.objects.create(
                site_id=site, evento=evento, event="notificacao.devida", version=1,
                event_id=uuid.uuid5(uuid.NAMESPACE_URL, chave),
                payload={"site_id": site, "destinatario_id": destinatario,
                         "assunto": assunto,
                         "parametros": {"pedido_id": str(pedido.pk)},
                         "origem_event_id": origem},
            )


def processar(envelope: dict) -> None:
    """Revalida o pedido e o acesso na hora do consumo; repetição é segura."""
    tipo = envelope.get("event")
    if envelope.get("version") != 1 or not envelope.get("event_id"):
        raise ValueError("envelope marketplace inválido")
    dados = envelope.get("data")
    if not isinstance(dados, dict):
        raise ValueError("dados marketplace inválidos")
    if tipo == "marketplace.pagamento.aprovado":
        from apps.core.financeiro_marketplace import consumir_evento_aprovado
        consumir_evento_aprovado(dados)
        return
    if tipo in {"marketplace.recarga.aprovada", "marketplace.recarga.revertida"}:
        _recarga(envelope, dados)
        return
    if tipo not in ASSUNTOS and tipo != "marketplace.entrega_aprovada":
        return
    site = str(dados.get("site_id") or "")
    pedido = PedidoMarketplace.objects.filter(
        pk=dados.get("pedido_id"), site_id=site,
    ).select_related("aluno").first()
    if pedido is None:
        raise ValueError("evento sem pedido no site")
    if tipo == "marketplace.entrega_aprovada":
        from apps.core.financeiro_marketplace import registrar_recebivel_da_entrega
        registrar_recebivel_da_entrega(pedido)
    if tipo in ASSUNTOS:
        _carta(envelope, pedido)
