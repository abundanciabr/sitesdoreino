"""Efeitos locais e cartas da outbox da Fila do Dólar."""
from __future__ import annotations

import uuid

from django.db import transaction

from apps.encomendas.marketplace import acesso_aluno, acesso_cliente
from apps.encomendas.models import (
    EventoMarketplace, OfertaMarketplace, OutboxMarketplace, PedidoMarketplace,
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
