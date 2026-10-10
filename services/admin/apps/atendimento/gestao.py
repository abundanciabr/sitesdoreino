"""Consultas da área privada de suporte, sempre limitadas ao site da sessão."""
import hashlib
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from apps.core.models import MembroDaEquipe
from .models import Conversa

ESTADOS = {'aguardando':'Aguardando', 'andamento':'Em atendimento',
           'aguardando_aluno':'Aguardando aluno', 'encerrado':'Concluído', 'robo':'Com o robô'}
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
    return linhas

def contexto_fila(request, sid):
    from .views import contexto
    ctx = contexto(request,sid)
    todas = Conversa.objects.filter(site_id=sid)
    consulta = todas.select_related('assunto').prefetch_related('mensagens')
    q = request.GET.get('q','').strip()[:120]
    filtro = request.GET.get('estado','todos')
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
    consulta = consulta.order_by('criada_em')
    pagina = Paginator(consulta,25).get_page(request.GET.get('pagina'))
    numeros = {e:0 for e in ESTADOS}
    numeros.update({i['estado']:i['total'] for i in todas.values('estado').annotate(total=Count('id'))})
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
