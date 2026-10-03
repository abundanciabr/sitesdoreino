"""Cada contato do quiz abre uma oportunidade de venda; pedido e pagamento a movem."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Oportunidade, RegistroHistoricoOportunidade, TimelineEvent
from .recuperacao import _ganhar, _responsavel


FONTE = "quiz"
PREFIXO = "oferta:"
ETAPAS_ANTES_DO_PEDIDO = ("nova", "qualificada", "proposta")


def _abertas(lead):
    return Oportunidade.objects.select_for_update().filter(
        lead=lead, fonte_tipo=FONTE, desfecho_encerrada_em__isnull=True
    )


def _compra_depois(lead, momento):
    compras = TimelineEvent.objects.filter(lead=lead, event="pagamento.aprovado")
    if momento is not None:
        compras = compras.filter(occurred_at__gte=momento)
    return compras.order_by("occurred_at", "id").first()


@transaction.atomic
def abrir_oferta_do_quiz(lead, data, event_id, evento_timeline=None):
    """Uma oportunidade por pessoa e quiz; responder de novo não duplica."""
    slug = (data.get("quiz_slug") or "").strip() or "quiz"
    referencia = f"{PREFIXO}{slug}"
    type(lead).objects.select_for_update().get(pk=lead.pk)
    oportunidade = Oportunidade.objects.filter(
        lead=lead, fonte_tipo=FONTE, fonte_referencia_id=referencia
    ).first()
    if oportunidade is None:
        resultado = (data.get("result_key") or "").strip()
        descricao = f"Oferecer o produto indicado pelo quiz {slug}"
        if resultado:
            descricao += f" (resultado: {resultado})"
        oportunidade = Oportunidade.objects.create(
            lead=lead, etapa="nova", titular_id=_responsavel(lead.site_id),
            fonte_tipo=FONTE, fonte_referencia_id=referencia,
            passo_descricao=descricao,
            passo_executar_ate=timezone.now() + timedelta(days=1),
            passo_evidencia_esperada="Conversa com a pessoa e link de compra enviado",
        )
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
            descricao=f"Respondeu o quiz {slug}; oferta aberta.",
            evidencia=str(event_id),
        )
    momento = evento_timeline.occurred_at if evento_timeline is not None else None
    if not oportunidade.encerrada:
        compra = _compra_depois(lead, momento)
        if compra is not None:
            _ganhar(oportunidade, str(compra.event_id or compra.id),
                    "Venda feita: pagamento aprovado.")
    return oportunidade


@transaction.atomic
def avancar_ofertas_com_pedido(lead, data, event_id):
    pedido = data.get("order_id", "")
    for oportunidade in _abertas(lead).filter(etapa__in=ETAPAS_ANTES_DO_PEDIDO):
        oportunidade.etapa = "negociacao"
        oportunidade.passo_descricao = f"Acompanhar o pagamento do pedido {pedido}".strip()
        oportunidade.passo_executar_ate = timezone.now() + timedelta(days=1)
        oportunidade.passo_evidencia_esperada = "Pagamento aprovado"
        oportunidade.save(update_fields=[
            "etapa", "passo_descricao", "passo_executar_ate",
            "passo_evidencia_esperada", "atualizada_em",
        ])
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
            descricao=f"Fez o pedido {pedido}; oferta em negociação.".replace("  ", " "),
            evidencia=str(event_id),
        )


@transaction.atomic
def ganhar_ofertas(lead, event_id):
    for oportunidade in _abertas(lead):
        _ganhar(oportunidade, str(event_id), "Venda feita: pagamento aprovado.")
