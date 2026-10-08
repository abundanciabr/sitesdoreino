"""O menu das quatro áreas do CRM, igual em todas as telas que o incluem.

    {% load crm_menu %}{% menu_do_crm %}

Cada área é achada pelo NOME da rota. Página que ainda não existe neste site
aparece apagada e sem link ("em construção"), em vez de derrubar a tela com
erro de rota. A área atual é a que tem o endereço mais longo que começa o
endereço aberto: /crm/conversas/<id>/ fica em Conversas; /crm/<id>/ fica em
Oportunidades.
"""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()

AREAS = (
    ("Alunos", ("acompanhamento_alunos",)),
    ("Oportunidades", ("crm",)),
    ("Conversas", ("crm_conversas",)),
    ("Agentes", ("crm_agentes", "agentes_comerciais")),
    ("Resultados", ("crm_resultados",)),
    ("Satisfação", ("crm_satisfacao",)),
    ("Quem respondeu", ("crm_satisfacao_respondentes",)),
)


def _endereco(nomes):
    for nome in nomes:
        try:
            return reverse(nome)
        except NoReverseMatch:
            continue
    return ""


def areas_do_crm(caminho=""):
    areas = [{"nome": nome, "endereco": _endereco(nomes), "ativa": False} for nome, nomes in AREAS]
    candidatas = [a for a in areas if a["endereco"] and caminho.startswith(a["endereco"])]
    if candidatas:
        max(candidatas, key=lambda a: len(a["endereco"]))["ativa"] = True
    return areas


@register.inclusion_tag("admin/_crm_menu.html", takes_context=True)
def menu_do_crm(context):
    request = context.get("request")
    return {"areas": areas_do_crm(getattr(request, "path", "") or "")}
