"""Cada contato do quiz abre uma oportunidade de venda; pedido e pagamento a movem.

Pedido e pagamento movem só a oferta da compra correspondente: ver `compras.py`.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .compras import ligar_compras_soltas, registrar_pedido
from .models import Oportunidade, RegistroHistoricoOportunidade
from .recuperacao import _responsavel


FONTE = "quiz"
PREFIXO = "oferta:"
ETAPAS_ANTES_DO_PEDIDO = ("nova", "qualificada", "proposta")
PASSO_DA_CAPTURA = (
    "Retomar com a pessoa o quiz {slug}: ela deixou o contato e não chegou ao resultado"
)


@transaction.atomic
def abrir_oferta_do_quiz(lead, data, event_id, evento_timeline=None, origem="quiz_completo"):
    """Uma oportunidade por pessoa e quiz; responder de novo não duplica.

    `origem="captura"` é para quem só deixou o contato: o histórico e o passo
    dizem isso, sem afirmar que a pessoa respondeu o quiz.
    """
    slug = (data.get("quiz_slug") or "").strip() or "quiz"
    referencia = f"{PREFIXO}{slug}"
    type(lead).objects.select_for_update().get(pk=lead.pk)
    oportunidade = Oportunidade.objects.filter(
        lead=lead, fonte_tipo=FONTE, fonte_referencia_id=referencia
    ).first()
    if oportunidade is None:
        if origem == "captura":
            descricao = PASSO_DA_CAPTURA.format(slug=slug)
            evidencia_esperada = "Conversa com a pessoa: quiz concluído ou link de compra enviado"
            historico = f"Começou o quiz {slug} e deixou o contato; oferta aberta."
        else:
            resultado = (data.get("result_key") or "").strip()
            descricao = f"Oferecer o produto indicado pelo quiz {slug}"
            if resultado:
                descricao += f" (resultado: {resultado})"
            evidencia_esperada = "Conversa com a pessoa e link de compra enviado"
            historico = f"Respondeu o quiz {slug}; oferta aberta."
        oportunidade = Oportunidade.objects.create(
            lead=lead, etapa="nova", titular_id=_responsavel(lead.site_id),
            fonte_tipo=FONTE, fonte_referencia_id=referencia,
            passo_descricao=descricao,
            passo_executar_ate=timezone.now() + timedelta(days=1),
            passo_evidencia_esperada=evidencia_esperada,
        )
        RegistroHistoricoOportunidade.objects.create(
            oportunidade=oportunidade, autor_id="sistema", tipo="etapa_alterada",
            descricao=historico, evidencia=str(event_id),
        )
    momento = evento_timeline.occurred_at if evento_timeline is not None else None
    ligar_compras_soltas(lead, oportunidade, momento)
    oportunidade.refresh_from_db()
    return oportunidade


def avancar_ofertas_com_pedido(lead, data, event_id, evento_timeline=None):
    """Pedido criado: só a oferta deste pedido vai para negociação."""
    return registrar_pedido(lead, data, event_id, evento_timeline)
