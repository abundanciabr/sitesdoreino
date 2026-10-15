"""Avisa somente um avanço real reconhecido na jornada sequencial."""
from django.db import transaction
from .bonus_faixas import SLUGS
from .cartas import ASSUNTO_CONQUISTA, carta_de_celebracao

def avisar(jornada, antes, depois):
    anterior, atual = antes["atual"]["ordem"], depois["atual"]["ordem"]
    avisadas = set((jornada.declaracoes or {}).get("faixas_avisadas", []))
    novas = set(range(anterior + 1, atual + 1)) - avisadas
    if not novas:
        return
    carta_de_celebracao(
        site_id=jornada.site_id, destinatario_id=jornada.pessoa_id,
        assunto=ASSUNTO_CONQUISTA,
        parametros={"conquista_slug": "trilha-faixa-" + SLUGS[max(novas)], "familia": "carreira"},
    )
    jornada.declaracoes = {**jornada.declaracoes, "faixas_avisadas": sorted(avisadas | set(range(2, atual + 1)))}
    jornada.save(update_fields=["declaracoes", "atualizada_em"])
    from .motor import relay_apos_commit
    transaction.on_commit(relay_apos_commit)
