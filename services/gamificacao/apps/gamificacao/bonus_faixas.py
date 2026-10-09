"""Bônus definidos pelo mantenedor: um crédito por aluno e conquista."""

import uuid

from django.utils import timezone

PONTOS = {1: 0, 2: 5000, 3: 10000, 4: 15000, 5: 20000, 6: 25000,
          7: 30000, 8: 40000, 9: 50000, 10: 75000, 11: 100000, 12: 150000, 13: 200000}
SLUGS = {1: "branca", 2: "amarela", 3: "azul", 4: "vermelha", 5: "verde", 6: "marrom",
         **{ordem: f"preta-grau-{ordem-6}" for ordem in range(7, 14)}}


def configurar(site_id):
    """Grava a tabela autorizada na economia existente; não reescreve ajustes posteriores."""
    from .models import RegraDePontuacao

    for ordem, pontos in PONTOS.items():
        if not pontos:
            continue
        slug = SLUGS[ordem]
        RegraDePontuacao.objects.get_or_create(site_id=site_id, slug="bonus-faixa-" + slug, defaults={
            "evento_gatilho": "gamificacao.faixa-" + slug + "-conquistada.v1",
            "beneficiario": "ator", "pontos": pontos, "ativa": True,
            "vigente_desde": timezone.now(), "quarentena_horas": 0, "acoes_cheias_por_dia": 0,
        })


def conceder(pessoa_id, site_id, ordens):
    from .motor import aplicar

    creditados = []
    for ordem in sorted(set(ordens)):
        if not PONTOS.get(ordem):
            continue
        slug = SLUGS[ordem]
        # Não depende da tarefa, da revisão do print ou da meta: a mesma faixa tem a mesma origem.
        origem = uuid.uuid5(uuid.NAMESPACE_URL, f"meshcraft:bonus-faixa:{site_id}:{ordem}")
        creditados.extend(aplicar({
            "event": "gamificacao.faixa-" + slug + "-conquistada", "version": 1,
            "event_id": str(origem), "occurred_at": timezone.now().isoformat(), "ator_id": pessoa_id,
            "data": {"site_id": site_id, "ordem": ordem},
        }, site_id))
    return sum(l.pontos for l in creditados)
