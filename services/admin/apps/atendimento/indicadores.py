"""Indicadores do suporte calculados apenas com registros deste site."""

from datetime import datetime, time, timedelta

from django.db.models import Avg, Case, Count, DateTimeField, DurationField, ExpressionWrapper, F, Max, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Conhecimento, Conversa, Mensagem


def _escopo(request):
    # O import local evita o ciclo com views, que publica estas páginas nas rotas.
    from . import views

    views.admin(request)
    sid = views.site(request)
    return sid, views.contexto(request, sid)


def _periodo(request):
    try:
        dias = int(request.GET.get('periodo', '7'))
    except (TypeError, ValueError):
        dias = 7
    dias = dias if dias in (7, 30, 90) else 7
    hoje = timezone.localdate()
    inicio = timezone.make_aware(datetime.combine(hoje - timedelta(days=dias - 1), time.min))
    return dias, inicio, hoje


def _minutos(duracao):
    return round(duracao.total_seconds() / 60, 1) if duracao is not None else None


@require_GET
def desempenho(request):
    sid, ctx = _escopo(request)
    dias, inicio, hoje = _periodo(request)
    curso = request.GET.get('curso', '').strip()[:200]
    todas = Conversa.objects.filter(site_id=sid)
    cursos = list(todas.exclude(curso='').order_by('curso').values_list('curso', flat=True).distinct()[:100])
    if curso:
        todas = todas.filter(curso=curso)
    todas = todas.annotate(_inicio=Case(
        When(rodada=1, then=Coalesce('rodada_iniciada_em', 'criada_em')),
        default=F('rodada_iniciada_em'), output_field=DateTimeField()))
    recebidas = todas.filter(_inicio__gte=inicio)
    concluidas = todas.filter(estado='encerrado', encerrada_em__gte=inicio)

    # O registro explícito cobre a rodada atual. Mensagens antigas só permitem
    # inferir a primeira resposta da conversa que nunca foi reaberta.
    resposta_antiga = Mensagem.objects.filter(conversa_id=OuterRef('pk'), autor='equipe').order_by('criada_em', 'pk').values('criada_em')[:1]
    respondidas = recebidas.annotate(
        _resposta=Coalesce('primeira_resposta_em', Case(When(rodada=1, then=Subquery(resposta_antiga)))))
    respondidas = respondidas.filter(_resposta__gte=F('_inicio')).annotate(
        _tempo=ExpressionWrapper(F('_resposta') - F('_inicio'), output_field=DurationField()))
    resolvidas = concluidas.filter(_inicio__isnull=False, encerrada_em__gte=F('_inicio')).annotate(
        _tempo=ExpressionWrapper(F('encerrada_em') - F('_inicio'), output_field=DurationField()))
    resposta_media = respondidas.aggregate(valor=Avg('_tempo'))['valor']
    resolucao_media = resolvidas.aggregate(valor=Avg('_tempo'))['valor']
    ultima_equipe = Mensagem.objects.filter(conversa_id=OuterRef('pk'), autor='equipe').order_by('-pk').values('pk')[:1]
    aluno_pendente = Mensagem.objects.filter(conversa_id=OuterRef('pk'), autor='aluno',
                                              pk__gt=OuterRef('_ultima_equipe')).order_by('pk').values('criada_em')[:1]
    espera = recebidas.filter(estado='aguardando').annotate(_ultima_equipe=Coalesce(Subquery(ultima_equipe), Value(0))).annotate(
        _desde=Subquery(aluno_pendente)).filter(_desde__isnull=False).annotate(
        _tempo=ExpressionWrapper(Value(timezone.now()) - F('_desde'), output_field=DurationField()))
    espera_media = espera.aggregate(valor=Avg('_tempo'))['valor']
    # A avaliação não tem data própria; em conversas reabertas não há como
    # atribuir a nota com segurança à rodada atual.
    nota = recebidas.filter(rodada=1, avaliacao__gte=1, avaliacao__lte=5).aggregate(valor=Avg('avaliacao'), total=Count('pk'))
    metricas = {
        'recebidos': recebidas.count(), 'concluidos': concluidas.count(),
        'primeira_resposta_min': _minutos(resposta_media),
        'primeira_resposta_amostra': respondidas.count(),
        'resolucao_min': _minutos(resolucao_media),
        'resolucao_amostra': resolvidas.count(),
        'espera_min': _minutos(espera_media), 'espera_amostra': espera.count(),
        'satisfacao': round(nota['valor'], 1) if nota['valor'] is not None else None,
        'satisfacao_amostra': nota['total'],
    }
    recebidos_dia = {r['dia']: r['total'] for r in recebidas.annotate(dia=TruncDate('_inicio')).values('dia').annotate(total=Count('pk'))}
    concluidos_dia = {r['dia']: r['total'] for r in concluidas.annotate(dia=TruncDate('encerrada_em')).values('dia').annotate(total=Count('pk'))}
    respostas_dia = {r['dia']: _minutos(r['media']) for r in respondidas.annotate(dia=TruncDate('_inicio')).values('dia').annotate(media=Avg('_tempo'))}
    serie = []
    for n in range(dias):
        dia = hoje - timedelta(days=dias - 1 - n)
        serie.append({'dia': dia, 'rotulo': dia.strftime('%d/%m'), 'recebidos': recebidos_dia.get(dia, 0),
                      'concluidos': concluidos_dia.get(dia, 0), 'primeira_resposta_min': respostas_dia.get(dia)})
    assuntos = list(recebidas.values('assunto__nome').annotate(total=Count('pk')).order_by('-total', 'assunto__nome')[:8])
    por_pessoa = {}
    for item in concluidas.exclude(atendente_id='').values('atendente_id').annotate(
            atendente_nome=Max('atendente_nome'), concluidos=Count('pk')):
        por_pessoa[item['atendente_id']] = {**item, 'primeira_resposta_min': None, 'satisfacao': None}
    for item in respondidas.exclude(atendente_id='').values('atendente_id').annotate(
            atendente_nome=Max('atendente_nome'), media=Avg('_tempo')):
        linha = por_pessoa.setdefault(item['atendente_id'], {
            'atendente_id': item['atendente_id'], 'concluidos': 0, 'satisfacao': None})
        linha['atendente_nome'] = item['atendente_nome']
        linha['primeira_resposta_min'] = _minutos(item['media'])
    for item in recebidas.exclude(atendente_id='').filter(
            rodada=1, avaliacao__gte=1, avaliacao__lte=5).values('atendente_id').annotate(
            atendente_nome=Max('atendente_nome'), nota=Avg('avaliacao')):
        linha = por_pessoa.setdefault(item['atendente_id'], {
            'atendente_id': item['atendente_id'], 'concluidos': 0, 'primeira_resposta_min': None})
        linha['atendente_nome'] = item['atendente_nome']
        linha['satisfacao'] = round(item['nota'], 1)
    equipe = sorted(por_pessoa.values(), key=lambda item: (-item['concluidos'], item.get('atendente_nome') or ''))[:30]
    ctx.update(periodo=dias, periodos=(7, 30, 90), curso=curso, cursos=cursos,
               metricas=metricas, serie=serie, assuntos=assuntos, equipe=equipe,
               max_volume=max([1]+[max(i['recebidos'],i['concluidos']) for i in serie]),
               max_resposta=max([1]+[i['primeira_resposta_min'] for i in serie if i['primeira_resposta_min'] is not None]),
               nps_estado='Sem dados consolidados para este período',
               indicadores_ressalva='Recebidos e tempos usam o início da rodada no período; conclusões usam a data registrada de encerramento. A espera atual começa na primeira mensagem do aluno ainda sem resposta humana. Notas sem data própria contam só na primeira rodada. Respostas antigas só entram quando a conversa não foi reaberta.')
    return render(request, 'admin/atendimento_desempenho.html', ctx)


@require_GET
def supervisor(request):
    sid, ctx = _escopo(request)
    agora = timezone.now()
    todas = Conversa.objects.filter(site_id=sid)
    abertas = todas.exclude(estado='encerrado')
    aguardando = abertas.filter(estado='aguardando')
    andamento = abertas.filter(estado='andamento')
    resumo = {'aguardando': aguardando.count(), 'andamento': andamento.count(),
              'robo': abertas.filter(estado='robo').count(),
              'sem_responsavel': abertas.filter(atendente_id='').count(),
              'aguardando_aluno': abertas.filter(estado='aguardando_aluno').count()}
    prioridades = dict(abertas.values('prioridade').annotate(total=Count('pk')).values_list('prioridade', 'total'))
    # Apenas pessoas realmente atribuídas: o sistema não registra presença.
    carga = list(abertas.exclude(atendente_id='').values('atendente_id').annotate(
        atendente_nome=Max('atendente_nome'), total=Count('pk'), aguardando=Count('pk', filter=Q(estado='aguardando')),
        andamento=Count('pk', filter=Q(estado='andamento')),
        aguardando_aluno=Count('pk', filter=Q(estado='aguardando_aluno'))).order_by('-total', 'atendente_nome')[:50])
    atencao_q = abertas.filter(Q(prioridade='alta') | Q(atendente_id='')).select_related('assunto').prefetch_related('mensagens').annotate(
        _ordem=Case(When(prioridade='alta', then=0), default=1)).order_by('_ordem', 'atualizada_em')[:12]
    from .gestao import preparar_linhas
    linhas = preparar_linhas(atencao_q)
    atencao = [{
        'id': c.pk, 'nome': c.nome or 'Aluno', 'assunto': c.assunto.nome,
        'prioridade': c.prioridade, 'estado': c.estado,
        'atendente': c.atendente_nome or 'Sem atribuição',
        'espera_min': max(0, round((agora - c.espera_desde).total_seconds() / 60)) if c.espera_desde else None,
        'desde': c.espera_desde, 'espera': c.espera,
    } for c in linhas]
    atividade = list(Mensagem.objects.filter(conversa__site_id=sid, autor='equipe').select_related(
        'conversa', 'conversa__assunto').order_by('-criada_em', '-pk')[:8])
    base = list(Conhecimento.objects.filter(site_id=sid).values('assunto__nome').annotate(
        total=Count('pk')).order_by('-total', 'assunto__nome')[:5])
    from .contexto import ROTEIRO
    ctx.update(resumo=resumo, prioridades=prioridades, carga=carga, atencao=atencao,
               atividade=atividade, roteiro=ROTEIRO, base=base,
               base_url=ctx['suporte_prefixo'] + '/base/',
               presenca_estado='Presença em tempo real não disponível',
               espera_ressalva='Espera desde a primeira mensagem do aluno ainda sem resposta humana; sem mensagem pendente aparece —.')
    return render(request, 'admin/atendimento_supervisor.html', ctx)
