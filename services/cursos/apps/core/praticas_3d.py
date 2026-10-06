"""Interação nativa com autoria de sessão, gravação atômica e revisão otimista."""
import json,math,re,uuid
from datetime import timedelta
from pathlib import Path
from io import BytesIO
from django.conf import settings
from django.db import transaction
from django.db.models import Sum,Count
from django.http import JsonResponse,HttpResponse,Http404
from django.shortcuts import get_object_or_404,render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_http_methods,require_POST
from django.utils import timezone
from apps.cursos.models import Base3D,Atividade3D,Projeto3D,Tentativa3D,Jornada3D,Evento3D,Progresso,Aula
from .sessao import quem_e,site_atual

DESAFIO='desafio-como-ganhar-em-dolar-com-roblox'
EVENTOS={'inicio','escolha','primeira_mudanca','salvar','recuperar','concluir','abandono','falha_salvar','compreensao'}

def atividade_de(aula):
    return Atividade3D.objects.filter(aula=aula,ativa=True).first()

def preparar_jornada(pessoa,curso):
    if curso.slug!=DESAFIO or not Atividade3D.objects.filter(aula__curso=curso,ativa=True).exists():return None
    with transaction.atomic():
        Jornada3D.objects.get_or_create(pessoa=pessoa,curso=curso,defaults={'inicio':timezone.now()})
        jornada=Jornada3D.objects.select_for_update().get(pessoa=pessoa,curso=curso)
        for atividade in Atividade3D.objects.filter(aula__curso=curso,ativa=True).select_related('aula'):
            Progresso.objects.get_or_create(pessoa=pessoa,aula=atividade.aula,defaults={'estado':'trancada'})
            data=None if jornada.legado else jornada.inicio+timedelta(hours=24*(atividade.dia-1))
            if data is None or data<=timezone.now():
                p,_=Progresso.objects.get_or_create(pessoa=pessoa,aula=atividade.aula,defaults={'estado':'disponivel'})
                if p.estado=='trancada':Progresso.objects.filter(pk=p.pk,estado='trancada').update(estado='disponivel')
        return jornada

def liberacao(aula,pessoa):
    atividade=atividade_de(aula)
    if not atividade or aula.curso.slug!=DESAFIO:return None
    j=Jornada3D.objects.filter(pessoa=pessoa,curso=aula.curso).first()
    if not j or j.legado:return None
    data=j.inicio+timedelta(hours=24*(atividade.dia-1))
    return data if data>timezone.now() else None

def personalizacao(p):
    return {'id':str(p.id),'revisao':p.revisao,'titulo':p.titulo,'modelo':p.base.chave,'versao':p.base.versao,'receita':p.receita,'imagem':reverse('imagem-item-3d',args=[p.id]),'atualizado':p.atualizado_em.isoformat()}

def contexto(aula,pessoa,request,atividade=None):
    a=atividade or atividade_de(aula)
    if not a:return None
    bases=[b for b in Base3D.objects.all() if f'{b.chave}@{b.versao}' in a.configuracao.get('modelos',[])]
    modelos=[]
    for b in bases:
        pasta=f'praticas-3d/modelos/{b.chave}/v{b.versao}/'
        modelos.append({**b.dados,'id':b.chave,'versao':b.versao,'url':reverse('estatico',args=[pasta+'base.glb']),'miniatura':reverse('estatico',args=[pasta+'miniatura.png'])})
    projetos=Projeto3D.objects.filter(pessoa=pessoa,curso=aula.curso,grupo=a.grupo).select_related('base').order_by('-atualizado_em')
    escolhido=projetos.filter(id=request.GET.get('projeto')).first() if re.fullmatch(r'[0-9a-f-]{36}',request.GET.get('projeto','')) else projetos.first()
    # Include the exact old base version when continuing an existing project.
    if escolhido and not any(m['id']==escolhido.base.chave and m['versao']==escolhido.base.versao for m in modelos):
        b=escolhido.base;pasta=f'praticas-3d/modelos/{b.chave}/v{b.versao}/'
        modelos.append({**b.dados,'id':b.chave,'versao':b.versao,'url':reverse('estatico',args=[pasta+'base.glb']),'miniatura':reverse('estatico',args=[pasta+'miniatura.png'])})
    projeto=personalizacao(escolhido) if escolhido else None
    if projeto:
        tentativa=Tentativa3D.objects.filter(pessoa=pessoa,atividade=a,projeto=escolhido).first()
        projeto['receita']={**projeto['receita'],'etapa':tentativa.estado.get('etapa',0) if tentativa else 0}
    return {'atividade':str(a.id),'dia':a.dia,'pitch':a.dia in (4,5,6) or a.configuracao.get('complementar',False),'configuracao':a.configuracao,'modelos':modelos,'projeto':projeto,'salvar':reverse('salvar-item-3d',args=[a.id]),'eventos':reverse('evento-item-3d',args=[a.id]),'meus_itens':reverse('meus-itens-3d')}

def _porta(request,atividade):
    from .views import _porta_aberta
    a=get_object_or_404(Atividade3D.objects.select_related('aula__curso','aula__bloco'),pk=atividade,ativa=True,aula__curso__site_id=site_atual())
    pessoa,curso,_,_,recusa=_porta_aberta(request,a.aula.numero,slug=a.aula.curso.slug,parte=a.aula.bloco.parte)
    if recusa is not None:return a,None,JsonResponse({'erro':'Entre com sua conta e confira a liberação desta aula.'},status=403)
    return a,pessoa,None

def _receita(raw,base):
    if not isinstance(raw,dict):raise ValueError('Não foi possível ler as escolhas.')
    cores=raw.get('cores',{})
    if not isinstance(cores,dict) or set(cores)!=set(base.dados['partes']):raise ValueError('Escolha as cores das partes deste modelo.')
    if any(not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in cores.values()):raise ValueError('Escolha uma cor válida.')
    vista=raw.get('vista',{})
    if not isinstance(vista,dict):raise ValueError('Enquadramento inválido.')
    for key in ['posicao','alvo']:
        v=vista.get(key)
        if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>100 for x in v):raise ValueError('Recupere a vista e tente salvar novamente.')
    largura=raw.get('proporcao',1)
    if type(largura) not in (int,float) or not math.isfinite(largura) or not .65<=largura<=1.4:raise ValueError('Proporção inválida.')
    etapa=raw.get('etapa',0)
    if type(etapa)!=int or not 0<=etapa<=10:raise ValueError('Etapa inválida.')
    return {'cores':cores,'vista':vista,'proporcao':largura,'etapa':etapa,'conferencia':bool(raw.get('conferencia',False)),'explicacao':str(raw.get('explicacao',''))[:500]}

def _normalizar(arquivo):
    try:
        from modules.pages.apps.portfolio.normalizacao import _normalizar as normalizar
    except ModuleNotFoundError:
        import importlib.util
        path=Path(__file__).resolve().parents[3]/'pages/apps/portfolio/normalizacao.py'
        spec=importlib.util.spec_from_file_location('normalizacao_portfolio',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);normalizar=m._normalizar
    return normalizar(arquivo)[0]

@never_cache
@require_POST
def salvar(request,atividade):
    a,pessoa,recusa=_porta(request,atividade)
    if recusa is not None:return recusa
    try:
        body=json.loads(request.POST.get('dados','{}'))
        if not isinstance(body,dict):raise ValueError('Escolhas inválidas.')
        chave=f"{body.get('modelo')}@{body.get('versao')}"
        projeto_id=uuid.UUID(body.get('id',''));revisao=int(body.get('revisao',0))
        base=get_object_or_404(Base3D,chave=body.get('modelo'),versao=body.get('versao'))
        existente=Projeto3D.objects.filter(pk=projeto_id,pessoa=pessoa,curso=a.aula.curso,grupo=a.grupo).first()
        if chave not in a.configuracao.get('modelos',[]) and not (existente and existente.base_id==base.pk):raise Http404
        receita=_receita(body.get('receita'),base)
        titulo=str(body.get('titulo','Meu item')).strip()[:120] or 'Meu item'
        imagem=_normalizar(request.FILES.get('imagem'))
        with transaction.atomic():
            # Owner lock serializes quota checks and retries for newly generated UUIDs.
            type(pessoa).objects.select_for_update().get(pk=pessoa.pk)
            existente=Projeto3D.objects.select_for_update().filter(pk=projeto_id,pessoa=pessoa,curso=a.aula.curso,grupo=a.grupo).first()
            if not existente and Projeto3D.objects.filter(pk=projeto_id).exists():raise Http404
            if existente and existente.revisao!=revisao:
                if existente.base_id==base.pk and existente.receita==receita and existente.titulo==titulo:
                    return JsonResponse({'projeto':personalizacao(existente)})
                return JsonResponse({'erro':'Este item foi salvo em outra aba. Suas escolhas continuam aqui. Reabra a versão salva ou guarde suas escolhas como outro item.','conflito':True},status=409)
            if not existente and revisao!=0:raise ValueError('Reabra o projeto antes de salvar.')
            uso=Projeto3D.objects.filter(pessoa=pessoa,curso__site_id=site_atual()).aggregate(n=Sum('tamanho_imagem'))['n'] or 0
            if uso-(existente.tamanho_imagem if existente else 0)+len(imagem)>50*1024*1024:raise ValueError('Sua coleção atingiu o limite de 50 MiB em imagens.')
            p=existente or Projeto3D(id=projeto_id,pessoa=pessoa,curso=a.aula.curso,grupo=a.grupo)
            p.base=base;p.titulo=titulo;p.receita=receita;p.imagem=imagem;p.tamanho_imagem=len(imagem);p.revisao=revisao+1;p.save()
            Tentativa3D.objects.update_or_create(pessoa=pessoa,atividade=a,defaults={'projeto':p,'estado':{'etapa':receita['etapa'],'conferencia':receita['conferencia']}})
            Evento3D.objects.create(pessoa=pessoa,atividade=a,tipo='salvar',etapa=receita['etapa'])
        return JsonResponse({'projeto':personalizacao(p)})
    except (ValueError,TypeError,json.JSONDecodeError,OverflowError) as e:
        return JsonResponse({'erro':str(e) if isinstance(e,ValueError) else 'Não foi possível guardar o item. Tente novamente.'},status=400)

@never_cache
@require_POST
def evento(request,atividade):
    a,pessoa,recusa=_porta(request,atividade)
    if recusa is not None:return recusa
    tipo=request.POST.get('tipo');etapa=request.POST.get('etapa','0')
    if tipo not in EVENTOS or not etapa.isdigit() or int(etapa)>10:return JsonResponse({'erro':'Evento inválido.'},status=400)
    Evento3D.objects.create(pessoa=pessoa,atividade=a,tipo=tipo,etapa=int(etapa))
    return JsonResponse({'ok':True})

@never_cache
@require_GET
def imagem(request,projeto):
    ator=quem_e(request)
    if not ator.autenticado:raise Http404
    p=get_object_or_404(Projeto3D,pk=projeto,pessoa=ator.pessoa,curso__site_id=site_atual())
    r=HttpResponse(bytes(p.imagem),content_type='image/webp');r['Content-Disposition']='inline';return r

@never_cache
@require_GET
def meus_itens(request):
    from .views import _de_fora,_recusar
    ator=quem_e(request)
    if not ator.autenticado:return _recusar(request,'entrar',status=200)
    itens=Projeto3D.objects.filter(pessoa=ator.pessoa,curso__site_id=site_atual()).select_related('curso','base').order_by('-atualizado_em')
    lista=[]
    for p in itens:
        a=Atividade3D.objects.filter(aula__curso=p.curso,grupo=p.grupo,ativa=True).select_related('aula__bloco').order_by('dia').first()
        lista.append({'titulo':p.titulo,'imagem':reverse('imagem-item-3d',args=[p.id]),'data':p.atualizado_em,'url':reverse('aula-do-curso',args=[p.curso.slug,a.aula.bloco.parte,a.aula.numero])+f'?projeto={p.id}' if a else ''})
    return render(request,'cursos/meus_itens_3d.html',{**_de_fora(),'itens':lista})

@never_cache
@require_http_methods(['GET','POST'])
def producao(request):
    from .views import _professor,_de_fora
    _,recusa=_professor(request)
    if recusa is not None:return recusa
    erro='';previa=None
    if request.method=='POST':
        a=get_object_or_404(Atividade3D,pk=request.POST.get('atividade'),aula__curso__site_id=site_atual())
        try:
            config=json.loads(request.POST.get('configuracao','{}'))
            if not isinstance(config,dict) or not config.get('modelos'):raise ValueError('Informe os modelos e as instruções.')
            validos={f'{b.chave}@{b.versao}' for b in Base3D.objects.all()}
            if any(k not in validos for k in config['modelos']):raise ValueError('Modelo não encontrado no catálogo.')
            a.configuracao=config
            if request.POST.get('acao')=='previa':
                previa=contexto(a.aula,quem_e(request).pessoa,request,atividade=a)
                previa['preview']=True;previa['projeto']=None
            else:a.save(update_fields=['configuracao'])
        except (ValueError,TypeError):erro='Confira a configuração e tente novamente.'
    atividades=Atividade3D.objects.filter(aula__curso__site_id=site_atual()).select_related('aula__curso')
    lista=[{'atividade':a,'configuracao':json.dumps(a.configuracao,ensure_ascii=False,indent=2)} for a in atividades]
    indicadores=list(Evento3D.objects.filter(atividade__aula__curso__site_id=site_atual()).values('atividade__aula__numero','tipo','etapa').annotate(eventos=Count('id'),alunos=Count('pessoa',distinct=True)))
    return render(request,'cursos/producao_praticas_3d.html',{**_de_fora(),'atividades':lista,'indicadores':indicadores,'erro':erro,'pratica3d':previa})
