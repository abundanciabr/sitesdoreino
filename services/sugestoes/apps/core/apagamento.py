# apps/core/apagamento.py
"""Apagamento definitivo de uma ideia, num lugar só (API do Admin e `esvaziar_caixa`).
Texto, votos, comentários e avisos somem; a linha fica para o histórico."""

from django.utils import timezone

from apps.sugestoes.models import Aviso, Comentario, Sugestao, Voto

CAMPOS_GRAVADOS = [
    "titulo",
    "problema",
    "solucao_proposta",
    "resposta_da_equipe",
    "apagada_em",
    "apagada_por",
    "arquivada_em",
    "arquivada_por",
]


def apagar_definitivamente(sugestao: Sugestao, quem=None, agora=None) -> bool:
    """Destrói o conteúdo legível da ideia; devolve `False` se já estava apagada.
    `quem` é opcional: o pipeline não é uma pessoa."""
    if sugestao.apagada_em is not None:
        return False

    agora = agora or timezone.now()
    Voto.objects.filter(sugestao=sugestao).delete()
    Comentario.objects.filter(sugestao=sugestao).delete()
    # Remove a cópia local do aviso; quem lê é a página `/notificacoes` do `funil`.
    Aviso.objects.filter(sugestao=sugestao).delete()
    sugestao.titulo = ""
    sugestao.problema = ""
    sugestao.solucao_proposta = ""
    sugestao.resposta_da_equipe = ""
    sugestao.apagada_em = agora
    sugestao.apagada_por = quem
    # Apagada é sempre arquivada, para nenhuma tela precisar de um segundo carimbo.
    sugestao.arquivada_em = sugestao.arquivada_em or agora
    sugestao.arquivada_por = sugestao.arquivada_por or quem
    sugestao.save(update_fields=CAMPOS_GRAVADOS)
    return True
