"""Leitura: pedidos pagos ligados a um quiz, por versão, campanha e dia."""

from django.db.models import Count, Q, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import TruncDate

from apps.pedidos.models import Order

# Ordem do agrupamento: versão, campanha, criativo, segmento, formato, dia.
DIMENSOES = ("v", "cpg", "ctv", "seg", "fmt")


def pagos_do_quiz(slug: str, site_id: str | None = None, desde=None, ate=None):
    """Uma linha por (v, cpg, ctv, seg, fmt, dia): `pedidos` e `receita_cents`.

    Só pedidos com status "pago" cuja atribuição trouxe `qz == slug`. Cada
    pedido é uma linha da tabela e só vira "pago" uma vez (o FatoAplicado
    barra a reentrega do aviso antes do UPDATE), então reenviar o webhook não
    soma duas vezes. `desde`/`ate` são datas (inclusivas) do dia de criação.
    """
    # Reembolsado entra só para ser mostrado à parte: a venda estornada sai de
    # `pedidos` e de `receita_cents` e aparece em `reembolsos`.
    # Pedido de teste (sandbox do provedor, ensaio) é dinheiro de mentira: fica
    # fora, como já fica do resumo do CRM em comercial.py.
    consulta = Order.objects.filter(
        status__in=("pago", "reembolsado"), contexto__qz=slug, em_teste=False
    )
    if site_id:
        consulta = consulta.filter(site_id=site_id)
    if desde:
        consulta = consulta.filter(created_at__date__gte=desde)
    if ate:
        consulta = consulta.filter(created_at__date__lte=ate)
    campos = {f"d_{d}": KeyTextTransform(d, "contexto") for d in DIMENSOES}
    linhas = (
        consulta.annotate(dia=TruncDate("created_at"), **campos)
        .values(*campos, "dia")
        .annotate(
            pedidos=Count("id", filter=Q(status="pago")),
            receita_cents=Sum("total_cents", filter=Q(status="pago")),
            reembolsos=Count("id", filter=Q(status="reembolsado")),
            reembolsado_cents=Sum("total_cents", filter=Q(status="reembolsado")),
        )
        .order_by("dia", *campos)
    )
    return [
        {
            **{d: linha[f"d_{d}"] or "" for d in DIMENSOES},
            "dia": linha["dia"],
            "pedidos": linha["pedidos"],
            "receita_cents": linha["receita_cents"] or 0,
            "reembolsos": linha["reembolsos"],
            "reembolsado_cents": linha["reembolsado_cents"] or 0,
        }
        for linha in linhas
    ]
