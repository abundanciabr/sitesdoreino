"""Leitura: pedidos pagos ligados a um quiz, por versão, campanha e dia."""

from django.db.models import Count, Sum
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
    consulta = Order.objects.filter(status="pago", contexto__qz=slug)
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
        .annotate(pedidos=Count("id"), receita_cents=Sum("total_cents"))
        .order_by("dia", *campos)
    )
    return [
        {
            **{d: linha[f"d_{d}"] or "" for d in DIMENSOES},
            "dia": linha["dia"],
            "pedidos": linha["pedidos"],
            "receita_cents": linha["receita_cents"],
        }
        for linha in linhas
    ]
