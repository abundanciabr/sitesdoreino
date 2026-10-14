"""Consultas da área privada de suporte, sempre limitadas ao site da sessão."""
import hashlib
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max, Case, When, Value, OuterRef, Subquery, DateTimeField
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from apps.core.models import MembroDaEquipe
from .models import Conversa, Mensagem
from .escala import TIPOS
from datetime import timedelta

ESTADOS = {'aguardando':'Aguardando', 'andamento':'Em atendimento',
           'aguardando_aluno':'Aguardando aluno', 'encerrado':'Encerrado', 'robo':'Com o robô'}
PRIORIDADES = {'baixa':'Baixa', 'normal':'Normal', 'alta':'Alta'}

def identidade_atendente(request):
    from apps.core.equipe import _membro_da_sessao
    membro = _membro_da_sessao(request)
    return ('membro-'+str(membro.pk), membro.nome) if membro else (str(request.admin['id']), request.admin.get('nome') or 'Equipe')

def responsaveis(request, sid):
    registros = {i['atendente_id']:i['atendente_nome'] for i in Conversa.objects.filter(site_id=sid).exclude(atendente_id='').values('atendente_id','atendente_nome')}
    for m in MembroDaEquipe.objects.filter(ativo=True,email_a_conferir=False).exclude(email=''):
        registros['membro-'+str(m.pk)] = m.nome
    chave,nome = identidade_atendente(request)
    registros[chave] = nome
    return [{'id':k,'nome':v or 'Equipe'} for k,v in sorted(registros.items(), key=lambda item:item[1])]

def preparar_linhas(consultas):
    linhas = list(consultas)
    agora = timezone.now()
    for c in linhas:
        mensagens = list(c.mensagens.all())
        ultima = mensagens[-1] if mensagens else None
        c.ultima_mensagem = ultima.texto if ultima else ''
        # A espera começa na primeira mensagem do aluno ainda sem resposta humana.
        equipe = max((m.pk for m in mensagens if m.autor=='equipe'), default=0)
        pendentes = [m for m in mensagens if m.autor=='aluno' and m.pk>equipe and (not c.rodada_iniciada_em or m.criada_em>=c.rodada_iniciada_em)]
        c.espera_desde = pendentes[0].criada_em if pendentes else None
        minutos = max(0,int((agora-c.espera_desde).total_seconds()/60)) if c.espera_desde else 0
        c.espera = ('%dh %02dmin'%divmod(minutos,60) if minutos>=60 else str(minutos)+' min') if c.espera_desde and c.estado!='encerrado' else '—'
        c.estado_nome = ESTADOS.get(c.estado,c.estado)
        c.prioridade_nome = PRIORIDADES.get(c.prioridade,'Normal')
        c.tipo_nome = TIPOS.get(c.tipo, TIPOS[0])
        c.vencido = bool(c.espera_desde and c.estado != 'encerrado' and minutos >= 24*60)
        c.passo_vencido = bool(c.proximo_passo and c.passo_prazo and c.passo_prazo <= agora and c.estado != 'encerrado')
    return linhas

def contexto_fila(request, sid):
    from .views import contexto
    ctx = contexto(request,sid)
    todas = Conversa.objects.filter(site_id=sid)
    consulta = todas.select_related('assunto').prefetch_related('mensagens')
    q = request.GET.get('q','').strip()[:120]
    filtro = request.GET.get('estado','todos')
    consulta = consulta.filter(arquivada_em__isnull=filtro != 'arquivadas')
    responsavel = request.GET.get('responsavel','')
    prioridade = request.GET.get('prioridade','')
    curso = request.GET.get('curso','')
    if filtro in ESTADOS: consulta = consulta.filter(estado=filtro)
    if q: consulta = consulta.filter(Q(nome__icontains=q)|Q(assunto__nome__icontains=q)|Q(mensagens__texto__icontains=q)|Q(curso__icontains=q)).distinct()
    if responsavel=='sem': consulta = consulta.filter(atendente_id='')
    elif responsavel=='meus': consulta = consulta.filter(atendente_id__in=[identidade_atendente(request)[0],str(request.admin['id'])])
    elif responsavel: consulta = consulta.filter(atendente_id=responsavel)
    if prioridade in PRIORIDADES: consulta = consulta.filter(prioridade=prioridade)
    if curso: consulta = consulta.filter(curso=curso)
    ultima_equipe = Mensagem.objects.filter(conversa_id=OuterRef('pk'),autor='equipe').order_by('-pk').values('pk')[:1]
    from django.db.models.functions import Coalesce
    consulta = consulta.annotate(_equipe=Coalesce(Subquery(ultima_equipe),Value(0)))
    pendente = Mensagem.objects.filter(conversa_id=OuterRef('pk'),autor='aluno',pk__gt=OuterRef('_equipe')).order_by('pk').values('criada_em')[:1]
    consulta = consulta.annotate(_espera=Subquery(pendente,output_field=DateTimeField())).annotate(
        _ordem=Case(When(cor='vermelho',then=Value(0)),
            When(~Q(estado='encerrado') & Q(_espera__lt=timezone.now()-timedelta(hours=24)),then=Value(1)),
            When(prioridade='alta',then=Value(2)),default=Value(3))).order_by('_ordem','criada_em')
    pagina = Paginator(consulta,25).get_page(request.GET.get('pagina'))
    numeros = {e:0 for e in ESTADOS}
    numeros.update({i['estado']:i['total'] for i in todas.filter(arquivada_em__isnull=True).values('estado').annotate(total=Count('id'))})
    ctx.update(conversas=preparar_linhas(pagina.object_list),consulta=consulta,pagina_obj=pagina,
        numeros=numeros,filtro=filtro,q=q,responsavel=responsavel,prioridade=prioridade,curso=curso,
        responsaveis=responsaveis(request,sid),cursos=list(todas.exclude(curso='').order_by('curso').values_list('curso',flat=True).distinct()),
        estados=ESTADOS,prioridades=PRIORIDADES,selecionada=None)
    selecionada=request.GET.get('selecionada')
    if selecionada:
        import uuid
        try: uuid.UUID(selecionada)
        except ValueError: return ctx
        ctx['selecionada']=preparar_linhas([get_object_or_404(consulta,pk=selecionada)])[0]
    return ctx

@require_GET
def triagem(request):
    from .views import admin,site
    admin(request);sid=site(request);ctx=contexto_fila(request,sid)
    ctx['modo']='lista' if request.GET.get('modo')=='lista' else 'quadro'
    # A lista é paginada; o quadro usa os mesmos filtros, com contagem completa por etapa.
    ctx['colunas']=[{'estado':e,'nome':ESTADOS[e], 'total':ctx['consulta'].filter(estado=e).count(),
        'conversas':preparar_linhas(ctx['consulta'].filter(estado=e)[:50])} for e in ('aguardando','andamento','aguardando_aluno','encerrado')]
    return render(request,'admin/atendimento_triagem.html',ctx)

@require_GET
def alunos(request):
    from .views import admin,site
    admin(request);sid=site(request);ctx=contexto_fila(request,sid)
    # Uma ficha por pessoa, com a demanda mais recente deste site.
    ids=ctx['consulta'].order_by().values('pessoa_id').annotate(ultima=Max('criada_em'))
    pares=Q(pk__in=[])
    for i in ids: pares |= Q(pessoa_id=i['pessoa_id'],criada_em=i['ultima'])
    consulta=ctx['consulta'].filter(pares).order_by('-criada_em')
    pagina=Paginator(consulta,25).get_page(request.GET.get('pagina'))
    ctx.update(conversas=preparar_linhas(pagina.object_list),pagina_obj=pagina)
    return render(request,'admin/atendimento_alunos.html',ctx)

@require_GET
def aluno(request,conversa_id):
    from .views import admin,site,contexto
    from .contexto import consultar,ROTEIRO
    admin(request);sid=site(request);ctx=contexto(request,sid)
    c=get_object_or_404(Conversa.objects.select_related('assunto').prefetch_related('mensagens'),site_id=sid,pk=conversa_id)
    ctx.update(conversa=preparar_linhas([c])[0],ficha=consultar(c),roteiro=ROTEIRO,
        historico=preparar_linhas(Conversa.objects.filter(site_id=sid,pessoa_id=c.pessoa_id).exclude(pk=c.pk).select_related('assunto').prefetch_related('mensagens')[:50]))
    return render(request,'admin/atendimento_aluno.html',ctx)

def contexto_conversa(request,sid,c,ctx):
    ctx.update(conversa=preparar_linhas([c])[0],
        conversas=preparar_linhas(Conversa.objects.filter(site_id=sid).select_related('assunto').prefetch_related('mensagens')[:50]),
        responsaveis=responsaveis(request,sid),estados=ESTADOS,prioridades=PRIORIDADES,
        rascunho_chave=hashlib.sha256((str(request.admin['id'])+'|'+sid+'|'+str(c.pk)).encode()).hexdigest())
    return ctx
