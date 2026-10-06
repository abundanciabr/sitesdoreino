"""Trabalhos reais da equipe técnica, lidos da mesma fila de execução."""
from django.db.models import Sum

from apps.agentes.models import Consumo, Execucao


def resumo_da_super_equipe(site_id):
    trabalhos = Execucao.objects.filter(tipo=Execucao.Tipo.SUPER_EQUIPE,
                                       estado__site_id=str(site_id))
    return {
        "total": trabalhos.count(),
        "concluidos": trabalhos.filter(situacao=Execucao.Situacao.CONCLUIDA).count(),
        "em_andamento": trabalhos.filter(situacao__in=[Execucao.Situacao.NA_FILA,
                                                      Execucao.Situacao.EXECUTANDO]).count(),
        "custo": Consumo.objects.filter(execucao__in=trabalhos).aggregate(
            total=Sum("custo_estimado_usd"))["total"] or 0,
        "recentes": list(trabalhos.prefetch_related("entregas")[:5]),
    }
