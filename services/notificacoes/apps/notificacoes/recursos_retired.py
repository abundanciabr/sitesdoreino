"""Oculta avisos dos recursos desativados, preservando o registro original."""
from django.db.models import Q

SLUGS = ["dez-forjas", "primeira-contribuicao", "portfolio-publicado", "primeiro-cliente", "primeiros-dolares"]

def filtro():
    return (Q(assunto__in=["gamificacao.marco-validado", "gamificacao.nivel-alcancado"])
            | (Q(assunto="gamificacao.conquista-concedida", parametros__has_key="conquista_slug")
               & Q(parametros__conquista_slug__in=SLUGS)))

def retirado(assunto, parametros):
    return (assunto in {"gamificacao.marco-validado", "gamificacao.nivel-alcancado"}
            or (assunto == "gamificacao.conquista-concedida" and (parametros or {}).get("conquista_slug") in SLUGS))
