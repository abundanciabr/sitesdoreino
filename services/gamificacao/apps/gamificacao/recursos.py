"""Recursos retirados por ordem do mantenedor em 08/10/2026.

Os registros antigos ficam no banco, sem exposição nem novas recompensas.
"""
from django.db.models import Q

SLUGS_RETIRADOS = frozenset({
    "dez-forjas", "primeira-contribuicao", "portfolio-publicado",
    "primeiro-cliente", "primeiros-dolares",
})
CRITERIOS_RETIRADOS = frozenset({"forjas_seladas", "contribuicoes_aceitas"})

def filtro_retired(prefixo=""):
    return (Q(**{prefixo+"classe": "marco"})
            | Q(**{prefixo+"slug__in": SLUGS_RETIRADOS})
            | (Q(**{prefixo+"criterio__has_key": "tipo"})
               & Q(**{prefixo+"criterio__tipo__in": CRITERIOS_RETIRADOS})))

def disponiveis(queryset, prefixo=""):
    return queryset.exclude(filtro_retired(prefixo))

def retirada(conquista):
    return (conquista.classe == "marco" or conquista.slug in SLUGS_RETIRADOS
            or (conquista.criterio or {}).get("tipo") in CRITERIOS_RETIRADOS)
