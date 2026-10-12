"""Fotografia operacional agregada; nunca inclui pedidos ou dados de alunos."""
from datetime import timedelta
import math

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
    for nome in ("http_5xx_15m", "http_404_15m", "disco_livre_mb", "disco_total_mb", "disco_usado_mb", "janela_segundos"):
        valor = dados.get(nome)
        if valor is not None and (type(valor) is not int or valor < 0):
            raise ValueError("medição inválida")
        saida[nome] = valor
    for nome in ("crescimento_mb_h", "horas_ate_esgotar", "pico_entre_coletas_mb"):
        valor = dados.get(nome)
        if valor is not None and (type(valor) not in (int, float) or not math.isfinite(valor)
                                   or (nome != "crescimento_mb_h" and valor < 0)):
            raise ValueError("medição inválida")
        saida[nome] = valor
    for nome, campos in (("integrador", ("conflitos", "repeticoes_identicas", "conflitos_protegidos", "entregas_concluidas")),
                         ("imagens_manutencao", ("exportacoes", "reutilizacoes", "novos_bytes", "bytes_evitados"))):
        origem = dados.get(nome) or {}
        if not isinstance(origem, dict):
            raise ValueError("medição inválida")
        bloco = {}
        for campo in campos:
            valor = origem.get(campo)
            if valor is not None and (type(valor) is not int or valor < 0):
                raise ValueError("medição inválida")
            bloco[campo] = valor
        for campo in ("coletada_em", "ultima_ativacao_em"):
            valor = origem.get(campo)
            if valor is not None:
                data = parse_datetime(valor)
                if data is None or timezone.is_naive(data):
                    raise ValueError("instante inválido")
                bloco[campo] = data.isoformat()
        if nome == "integrador":
            for grupo in ("totais", "rodada"):
                origem_grupo = origem.get(grupo) or {}
                if not isinstance(origem_grupo, dict):
                    raise ValueError("medição inválida")
                bloco[grupo] = {}
                for campo in ("conflito_reutilizado", "espera_transitoria", "conferida", "falha_transitoria", "merge_tree", "commit_tree"):
                    valor = origem_grupo.get(campo)
                    if valor is not None and (type(valor) is not int or valor < 0):
                        raise ValueError("medição inválida")
                    bloco[grupo][campo] = valor
        saida[nome] = bloco
    for nome in ("aplicacao", "funil", "coletor"):
        valor = dados.get(nome, "indisponivel")
        if valor not in ("ativo", "inativo", "indisponivel"):
            raise ValueError("estado inválido")
        saida[nome] = valor
    return saida


def acompanhar_armazenamento(rotina, dados):
    """Acompanha a prevenção do integrador sem reativar análises ou IA paga."""
    from django.db import transaction
    from .models import MelhoriaSuperEquipe, EventoSuperEquipe
    integrador = dados.get("integrador") or {}
    if not operacao_recente(dados) or not operacao_recente(integrador):
        return
    evitadas = (integrador.get("totais") or {}).get("conflito_reutilizado")
    repetidas = integrador.get("repeticoes_identicas")
    if evitadas is None or repetidas is None:
        return
    with transaction.atomic():
        RotinaSuperEquipe.objects.select_for_update().get(pk=rotina.pk)
        item, novo = MelhoriaSuperEquipe.objects.select_for_update().get_or_create(
            rotina=rotina, chave="operacao-integrador-combinacoes", defaults={
                "titulo": "Integrador: evitar combinações repetidas e conferir entregas",
                "prioridade": 1, "situacao": "publicando", "observada_em": timezone.now(),
                "evidencia": {"operacao": "armazenamento", "inicio": dados["coletada_em"],
                              "evitadas_iniciais": evitadas, "amostras_sem_repeticao": 0}})
        evidencia = item.evidencia
        if (evidencia.get("ultima_coleta") and parse_datetime(evidencia["ultima_coleta"])
                >= parse_datetime(dados["coletada_em"])):
            return
        antes = item.situacao
        if repetidas:
            evidencia.update(inicio=dados["coletada_em"], evitadas_iniciais=evitadas, amostras_sem_repeticao=0)
            item.situacao, item.resolvida_em = "publicando", None
        else:
            evidencia["amostras_sem_repeticao"] = evidencia.get("amostras_sem_repeticao", 0) + 1
        ultima = parse_datetime(integrador.get("ultima_ativacao_em") or "")
        inicio = parse_datetime(evidencia["inicio"])
        protege_todas = integrador.get("conflitos_protegidos") == integrador.get("conflitos")
        comprovado = (not repetidas and protege_todas and evidencia["amostras_sem_repeticao"] >= 2
                       and evitadas > evidencia["evitadas_iniciais"] and ultima and ultima >= inicio
                       and dados.get("aplicacao") == "ativo" and dados.get("funil") == "ativo")
        if comprovado:
            item.situacao = "resolvida"
            item.resolvida_em = item.resolvida_em or timezone.now()
        evidencia.update(ultima_coleta=dados["coletada_em"], integrador=integrador,
                          acao="Reutilizar conflito de entradas idênticas e retomar falhas temporárias após espera.")
        item.evidencia = evidencia
        item.observada_em = timezone.now()
        item.resultado = (f"Ação no integrador: {evitadas} combinações idênticas evitadas; "
                          f"{repetidas} novas tentativas de conflitos com entradas iguais nesta coleta. "
                          + ("Nova entrega ativada e serviços ativos; efeito conferido." if comprovado else
                             "Acompanhando o efeito; a conclusão exige nova entrega ativada e repetição interrompida."))
        item.save()
        if novo or antes != item.situacao:
            EventoSuperEquipe.objects.create(melhoria=item, situacao=item.situacao, texto=item.resultado)


def servidor():
    rotina = RotinaSuperEquipe.objects.filter(host="meshcraft.top").first()
    dados = rotina.operacao if rotina else {}
    return {**dados, "estado": "medido" if operacao_recente(dados) else "indisponivel"}
