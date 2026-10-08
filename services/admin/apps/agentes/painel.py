"""O que o painel da equipe mostra dos robôs: o trabalho e as entregas de
cada tarefa. Lido pelas telas de `apps/core/equipe.py` numa consulta só por
tela, não uma por cartão."""

from __future__ import annotations

from .models import Entrega, Execucao


def trabalhos_das_tarefas(ids) -> dict[int, Execucao]:
    """O trabalho mais recente do robô em cada tarefa (a conversa não conta)."""
    ultimos: dict[int, Execucao] = {}
    for execucao in (
        Execucao.objects.filter(tarefa_id__in=list(ids))
        .exclude(tipo__in=[Execucao.Tipo.CONVERSA, Execucao.Tipo.SATISFACAO])
        .order_by("tarefa_id", "-criada_em")
    ):
        ultimos.setdefault(execucao.tarefa_id, execucao)
    return ultimos


def entregas_das_tarefas(ids) -> dict[int, list[Entrega]]:
    por_tarefa: dict[int, list[Entrega]] = {}
    for entrega in Entrega.objects.filter(tarefa_id__in=list(ids)).exclude(tipo__in=["satisfacao", "satisfacao_padroes"]).order_by("-criada_em"):
        por_tarefa.setdefault(entrega.tarefa_id, []).append(entrega)
    return por_tarefa
