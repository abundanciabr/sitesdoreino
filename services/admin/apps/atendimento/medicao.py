"""Métricas com amostra e origem explícitas, preservando rodadas reabertas."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from bisect import bisect_right
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .escala import TIPOS, retrato
from .models import Configuracao, Conversa, Mensagem, Reabertura, ConsumoDoAtendimento


def alunos_ativos(sid, curso=''):
    from apps.core.clients import AlunosClient
    itens = AlunosClient().alunos(status='ativa')
    if itens is None:
        return None
    # Pessoas distintas; uma pessoa com duas matrículas conta uma vez.
    return len({str(i.get('email')).casefold() for i in itens if str(i.get('site_id')) == sid
        and i.get('status') == 'ativa' and i.get('email')
        and (not curso or str(i.get('product_id')) == curso)})


def media(valores):
    return round(sum(valores)/len(valores), 2) if valores else None


def calcular(sid, inicio, curso=''):
    agora = timezone.now()
    consulta = Conversa.objects.filter(site_id=sid)
    if curso:
        consulta = consulta.filter(curso=curso)
    todas = list(consulta.filter(Q(criada_em__gte=inicio)|Q(rodada_iniciada_em__gte=inicio)))
    chegadas = defaultdict(list)
    for c in todas:
        chegadas[(c.pessoa_id, c.tipo)].append(c.criada_em)
    for datas in chegadas.values():
        datas.sort()
    linhas = []
    for c in todas:
        linhas.append((c, retrato(c), None))
    for r in Reabertura.objects.filter(conversa__in=consulta,quando__gte=inicio).select_related('conversa'):
        linhas.append((r.conversa, r.anterior, r.quando))
    grupos = defaultdict(lambda: {'total': 0, 'resolvidas': 0, 'humanos': [], 'respostas': [],
        'resolucoes': [], 'notas': []})
    confirmadas = inferidas = reaberturas = maduras = retornos = 0
    for c, d, retorno in linhas:
        comeco = parse_datetime(d.get('inicio') or '')
        if not comeco or comeco < inicio:
            continue
        tipo = int(d.get('tipo') or 0)
        g = grupos[tipo]
        g['total'] += 1
        resposta = parse_datetime(d.get('primeira_resposta_em') or '')
        resolvida = parse_datetime(d.get('resolvida_em') or '')
        encerrada = parse_datetime(d.get('encerrada_em') or '')
        if resposta and resposta >= comeco:
            g['respostas'].append((resposta-comeco).total_seconds()/60)
        if resolvida and resolvida >= comeco:
            g['resolvidas'] += 1
            g['resolucoes'].append((resolvida-comeco).total_seconds()/60)
            confirmadas += d.get('resolucao') == 'confirmada'
            inferidas += d.get('resolucao') == 'sem_retorno_7d'
        if d.get('avaliacao') in (1, 2, 3, 4, 5):
            g['notas'].append(d['avaliacao'])
        if retorno:
            reaberturas += 1
        if encerrada and encerrada <= agora-timedelta(days=7):
            maduras += 1
            voltou = retorno and retorno <= encerrada+timedelta(days=7)
            if not voltou:
                datas = chegadas[(c.pessoa_id, tipo)]
                voltou = bisect_right(datas, encerrada+timedelta(days=7)) > bisect_right(datas, encerrada)
            retornos += bool(voltou)
    # Soma as intervenções da pessoa na mesma rodada antes de calcular a média.
    # Duas respostas de 2 min no mesmo pedido representam 4 min por pedido.
    tempos = defaultdict(float)
    for m in Mensagem.objects.filter(conversa__in=consulta, autor='equipe', criada_em__gte=inicio, tempo_humano_seg__isnull=False):
        tempos[(m.conversa_id, m.rodada, m.tipo)] += m.tempo_humano_seg / 60
    for (_, _, tipo), minutos in tempos.items():
        grupos[tipo]['humanos'].append(minutos)
    total = sum(g['total'] for g in grupos.values())
    consumos = ConsumoDoAtendimento.objects.filter(conversa__in=consulta, consumo__criado_em__gte=inicio).select_related('consumo')
    custo = sum((c.consumo.custo_estimado_usd for c in consumos), Decimal('0'))
    inicio_medicao = Configuracao.objects.filter(site_id=sid).values_list('medicao_iniciada_em',flat=True).first()
    ativos = alunos_ativos(sid, curso)
    por_tipo = [{'tipo': TIPOS.get(n, TIPOS[0]), 'total': g['total'],
        'fatia': round(100*g['total']/total, 1) if total else 0, 'resolvidas': g['resolvidas'],
        'tempo_humano_min': media(g['humanos']), 'tempo_humano_amostra': len(g['humanos']),
        'primeira_resposta_min': media(g['respostas']), 'resolucao_min': media(g['resolucoes']),
        'satisfacao': media(g['notas']), 'satisfacao_amostra': len(g['notas'])}
        for n, g in sorted(grupos.items())]
    return {'por_tipo': por_tipo, 'total': total, 'confirmadas': confirmadas, 'inferidas': inferidas,
        'reaberturas': reaberturas, 'retornos_7d': retornos, 'amostra_7d': maduras,
        'taxa_retorno': round(100*retornos/maduras, 1) if maduras else None,
        'custo_usd': custo, 'custo_por_pedido': custo/total if total else None,
        'chamadas': len(consumos), 'custos_desconhecidos': sum(c.consumo.desconhecido for c in consumos),
        'ativos': ativos, 'pedidos_por_100': round(total*100/ativos, 2) if ativos else None,
        'inicio': inicio_medicao, 'revisao_em': inicio_medicao+timedelta(days=14) if inicio_medicao else None}
