"""Fotografia operacional agregada; nunca inclui pedidos ou dados de alunos."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Execucao, RotinaSuperEquipe


def coletar():
    agora = timezone.now()
    fila = Execucao.objects.all()
    return {
        "estado": "medido", "consultado_em": agora.isoformat(),
        "na_fila": fila.filter(situacao="na_fila").count(),
        "executando": fila.filter(situacao="executando").count(),
        "posses_vencidas": fila.filter(situacao="executando", ocupada_ate__lt=agora).count(),
        "fila_atrasada": fila.filter(situacao="na_fila", criada_em__lt=agora-timedelta(minutes=20),
                                     ).filter(Q(nao_antes_de__isnull=True) | Q(nao_antes_de__lt=agora-timedelta(minutes=20))).count(),
        "falhas_24h": fila.filter(situacao="falhou", atualizada_em__gte=agora-timedelta(days=1)).count(),
        "tipos_com_falhas": list(fila.filter(situacao="falhou", atualizada_em__gte=agora-timedelta(days=1))
                                  .values("tipo").annotate(total=Count("id")).order_by("tipo")),
        "limite": "Contagens da fila administrativa; não incluem conteúdo de conversas nem dados pessoais.",
    }


def situacao_executor(rotina):
    if not rotina or not rotina.executor_consultado_em:
        return "Aguardando contato do executor"
    if timezone.now()-rotina.executor_consultado_em > timedelta(minutes=20):
        return "Sem contato recente; trabalhos preservados na fila"
    return "Executor conectado" if rotina.ativa else "Executor conectado; acompanhamento pausado"


def operacao_recente(dados):
    try:
        instante = parse_datetime(dados.get("coletada_em", ""))
        return instante is not None and timedelta(seconds=-60) <= timezone.now()-instante < timedelta(minutes=5)
    except (TypeError, ValueError):
        return False


def receber(dados):
    """Recebe apenas totais e estados técnicos, sem armazenar log bruto."""
    saida = {"recebida_em": timezone.now().isoformat()}
    instante = parse_datetime(dados.get("coletada_em", ""))
    if instante is None or timezone.is_naive(instante):
        raise ValueError("instante inválido")
    saida["coletada_em"] = instante.isoformat()
    for nome in ("http_5xx_15m", "http_404_15m", "disco_livre_mb"):
        valor = dados.get(nome)
        if valor is not None and (type(valor) is not int or valor < 0):
            raise ValueError("medição inválida")
        saida[nome] = valor
    for nome in ("aplicacao", "funil", "coletor"):
        valor = dados.get(nome, "indisponivel")
        if valor not in ("ativo", "inativo", "indisponivel"):
            raise ValueError("estado inválido")
        saida[nome] = valor
    return saida


def servidor():
    rotina = RotinaSuperEquipe.objects.filter(host="meshcraft.top").first()
    dados = rotina.operacao if rotina else {}
    return {**dados, "estado": "medido" if operacao_recente(dados) else "indisponivel"}
