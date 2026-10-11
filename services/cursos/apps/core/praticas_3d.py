"""Interação nativa com autoria de sessão, gravação atômica e revisão otimista."""
import hashlib,importlib,json,math,re,uuid
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

def _situacao_faixas(pessoa, site_id):
    runtime=importlib.import_module('config.runtime')
    with runtime.serving('gamificacao'):
        jornada=importlib.import_module('modules.gamificacao.apps.gamificacao.jornada')
        return jornada.situacao(pessoa.id_da_plataforma,site_id)

def _passo_curto(pessoa,site_id):
    situacao=_situacao_faixas(pessoa,site_id)
    proxima=situacao.get('proxima') or {}
    ordem=proxima.get('ordem')
    return (situacao.get('caminho'),ordem) if situacao.get('caminho') in ('ugc','jogo','aprender') and ordem in (5,6,7) else (None,None)

def _registro_alteracoes(p):
    """Fatos de revisões gravadas pelo servidor, sem aproveitar declaração livre do POST."""
    fatos=[];vistas=set();base=f'{p.base.chave}@{p.base.versao}'
    padrao={'cores':{k:v['cor'] for k,v in p.base.dados['partes'].items()},'proporcao':1}
    for tentativa in Tentativa3D.objects.filter(pessoa=p.pessoa,projeto=p).order_by('pk'):
        for registro in (tentativa.estado or {}).get('historico',[]):
            if (registro.get('projeto_id')!=str(p.id) or registro.get('base')!=base or
                    type(registro.get('revisao')) is not int or registro['revisao']>p.revisao):continue
            revisao=registro['revisao'];chave=(str(tentativa.pk),revisao)
            if chave in vistas:continue
            vistas.add(chave)
            antes=registro.get('antes') or padrao;depois=registro.get('depois') or {}
            fonte=f'tentativa:{tentativa.pk}:projeto:{p.id}:revisao:{revisao}'
            anteriores=antes.get('cores') or {};atuais=depois.get('cores') or {}
            for parte,definicao in p.base.dados['partes'].items():
                cor_antes=anteriores.get(parte);cor_depois=atuais.get(parte)
                if isinstance(cor_antes,str) and isinstance(cor_depois,str) and cor_antes.lower()!=cor_depois.lower():
                    fatos.append({'tipo':'cor','parte':definicao['nome'],'antes':cor_antes,
                                  'depois':cor_depois,'fonte':fonte})
            proporcao_antes=antes.get('proporcao');proporcao_depois=depois.get('proporcao')
            if (type(proporcao_antes) in (int,float) and type(proporcao_depois) in (int,float)
                    and proporcao_antes!=proporcao_depois):
                parte=p.base.dados['forma']['parte']
                fatos.append({'tipo':'proporcao','parte':p.base.dados['partes'][parte]['nome'],
                              'antes':proporcao_antes,'depois':proporcao_depois,'fonte':fonte})
    return fatos

def _avaliar_salvamento(p,a,anterior):
    """A receita e a imagem já foram gravadas; evento do navegador não serve de prova."""
    try:
        caminho,ordem=_passo_curto(p.pessoa,p.curso.site_id)
        if ordem is None:return None
        runtime=importlib.import_module('config.runtime')
        with runtime.serving('gamificacao'):
            models=importlib.import_module('modules.gamificacao.apps.gamificacao.models')
            j=models.JornadaPessoal.objects.filter(pessoa_id=p.pessoa_id,site_id=p.curso.site_id).first()
            inicio=(j.inicio or {}) if j else {}
        nome_inicio=re.sub(r'\s+',' ',inicio.get('item_nome','')).strip().casefold()
        nome_atual=re.sub(r'\s+',' ',p.titulo).strip().casefold()
        if not nome_inicio or nome_atual!=nome_inicio:
            return {'ordem':ordem,'resultado':'incompleta',
                    'feedback':'Use neste item o mesmo nome que você registrou no começo do ciclo.'}
        if ordem>=6 and (inicio.get('projeto_ciclo_id')!=str(p.id) or
                         inicio.get('projeto_ciclo_base')!=f'{p.base.chave}@{p.base.versao}'):
            return {'ordem':ordem,'resultado':'incompleta',
                    'feedback':'Continue no mesmo item e na mesma base usados na faixa verde.'}
        parte=p.base.dados['forma']['parte']
        nome_parte=p.base.dados['partes'][parte]['nome']
        dados={'chave':f'pratica3d:{p.id}:{p.revisao}:{ordem}','caminho':caminho,'ordem':ordem,'item_nome':p.titulo,
               'item_acao':inicio.get('item_acao',''),'explicacao':p.receita.get('explicacao',''),
               'registro_alteracoes':_registro_alteracoes(p),'parte':nome_parte}
        evidencia={'chave':f'pratica3d:{p.id}:{p.revisao}:{ordem}', 'origem':'pratica3d',
                   'projeto_id':str(p.id),'revisao':p.revisao,'base':f'{p.base.chave}@{p.base.versao}',
                   'antes':anterior,'depois':{'cores':p.receita['cores'],'proporcao':p.receita['proporcao']}}
        resultado='incompleta'
        if ordem==5:
            mudadas=[p.base.dados['partes'][k]['nome'] for k,cor in p.receita['cores'].items()
                     if cor.lower()!=p.base.dados['partes'][k]['cor'].lower()]
            resultado='reconhecida' if mudadas else 'incompleta'
            feedback=(f'Você mudou a cor de {", ".join(mudadas)} e salvou {p.titulo}.'
                      if mudadas else 'Mude a cor de uma parte do item e salve para concluir a faixa verde.')
            evidencia['partes_alteradas']=mudadas
        elif ordem==6:
            # A versão anterior deve ser do mesmo item; o pedido visível é proporção maior que 1.
            antes=anterior.get('proporcao') if anterior else None
            aumentou=type(antes) in (int,float) and p.receita['proporcao']>antes
            atendido=aumentou and p.receita['proporcao']>1
            resultado='reconhecida' if atendido else 'incompleta'
            feedback=(f'Você comparou a versão anterior ({antes:.2f}) e ampliou {nome_parte} para {p.receita["proporcao"]:.2f}, salvando o mesmo item.'
                      if atendido else 'Reabra o mesmo item e aumente a proporção indicada para um valor maior que o da versão anterior e acima de 1; depois salve.')
        else:
            runtime=importlib.import_module('config.runtime')
            with runtime.serving('gamificacao'):
                models=importlib.import_module('modules.gamificacao.apps.gamificacao.models')
                avaliador=importlib.import_module('modules.gamificacao.apps.gamificacao.avaliacao_inicio')
                conteudo=bytes(p.imagem);digest=hashlib.sha256(conteudo).hexdigest()
                anexo,_=models.AnexoDaJornada.objects.get_or_create(
                    pessoa_id=p.pessoa_id,site_id=p.curso.site_id,passo=7,sha256=digest,
                    defaults={'nome':f'{p.id}.webp','conteudo':conteudo,'tamanho':len(conteudo)})
                analise=avaliador.avaliar(p.pessoa.id_da_plataforma,p.curso.site_id,7,dados,anexos=(anexo,))
                resultado,feedback=analise['resultado'],analise['feedback']
            evidencia.update(analise.get('evidencia') or {})
        # Cada resultado da reanálise é um fato distinto; o bônus segue único na jornada.
        digest=hashlib.sha256(f'{resultado}:{feedback}'.encode()).hexdigest()[:16]
        evidencia['chave']=f'pratica3d:{p.id}:{p.revisao}:{ordem}:{digest}'
        with transaction.atomic():
            atual=Projeto3D.objects.select_for_update().filter(pk=p.pk,pessoa=p.pessoa).first()
            if not atual or atual.revisao!=p.revisao or atual.base_id!=p.base_id:
                return {'ordem':ordem,'resultado':'falha','feedback':'Outra versão do item foi salva durante a análise. Peça a análise da versão mais recente.'}
            runtime=importlib.import_module('config.runtime')
            with runtime.serving('gamificacao'):
                jornada=importlib.import_module('modules.gamificacao.apps.gamificacao.jornada')
                models=importlib.import_module('modules.gamificacao.apps.gamificacao.models')
                with transaction.atomic():
                    j=models.JornadaPessoal.objects.select_for_update().get(
                        pessoa_id=p.pessoa_id,site_id=p.curso.site_id)
                    situacao=jornada.situacao(p.pessoa.id_da_plataforma,p.curso.site_id)
                    proxima=situacao.get('proxima') or {}
                    novo_inicio=j.inicio or {}
                    if situacao.get('caminho')!=caminho or proxima.get('ordem')!=ordem:
                        return {'ordem':ordem,'resultado':'falha','feedback':'Seu caminho ou etapa mudou durante a análise. Confira a jornada atual e peça uma nova avaliação.'}
                    if re.sub(r'\s+',' ',novo_inicio.get('item_nome','')).strip().casefold()!=nome_atual:
                        return {'ordem':ordem,'resultado':'incompleta','feedback':'Use o mesmo nome de item registrado no começo do ciclo.'}
                    if ordem==7 and novo_inicio.get('item_acao','')!=inicio.get('item_acao',''):
                        return {'ordem':ordem,'resultado':'falha','feedback':'Seu relato inicial mudou durante a análise. Peça nova avaliação da versão atual.'}
                    if ordem>=6 and (novo_inicio.get('projeto_ciclo_id')!=str(p.id) or
                                     novo_inicio.get('projeto_ciclo_base')!=f'{p.base.chave}@{p.base.versao}'):
                        return {'ordem':ordem,'resultado':'incompleta','feedback':'Continue no mesmo item e na mesma base da faixa verde.'}
                    depois=jornada.registrar_avaliacao(p.pessoa.id_da_plataforma,p.curso.site_id,ordem,resultado,feedback,evidencia)
                    bonus=int(depois.get('bonus_xp') or 0)
                    alcancada=depois['atual']['ordem']>=ordem
                    if ordem==5 and resultado=='reconhecida' and alcancada:
                        j.inicio={**novo_inicio,'projeto_ciclo_id':str(p.id),
                                  'projeto_ciclo_base':f'{p.base.chave}@{p.base.versao}'}
                        j.save(update_fields=['inicio','atualizada_em'])
                    if resultado=='reconhecida' and alcancada:
                        faixas=importlib.import_module('modules.gamificacao.apps.gamificacao.bonus_faixas')
                        historico=models.LancamentoDeXP.objects.filter(
                            pessoa_id=p.pessoa_id,site_id=p.curso.site_id,pontos__gt=0,
                            regra_slug='bonus-faixa-'+faixas.SLUGS[ordem]).exclude(status='estornado').exists()
                        if bonus or historico:
                            faixa={5:'verde',6:'marrom',7:'preta'}[ordem]
                            feedback=f'{feedback.rstrip()} Conquistou a faixa {faixa}.'
                    return {'ordem':ordem,'resultado':resultado,'feedback':feedback,
                            'conquistada':bool(resultado=='reconhecida' and alcancada and (bonus or historico)),
                            'bonus_xp':bonus}
    except Exception:
        # O item permanece salvo. Uma falha de infraestrutura nunca reprova a criação.
        return {'resultado':'falha','feedback':'O item foi salvo, mas a avaliação não pôde terminar agora. Tente salvar novamente para pedir nova análise.'}

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
    try:_,ordem=_passo_curto(pessoa,a.aula.curso.site_id)
    except Exception:ordem=None
    conferencia={5:'Vou conferir se você mudou a cor de uma parte e salvou o item.',
                 6:'Vou comparar a proporção do mesmo item com a versão anterior salva.',
                 7:'A IA vai examinar a imagem salva, o nome e sua explicação do item.'}.get(ordem,'')
    return {'atividade':str(a.id),'dia':a.dia,'pitch':a.dia in (4,5,6) or a.configuracao.get('complementar',False),'configuracao':a.configuracao,'modelos':modelos,'projeto':projeto,'salvar':reverse('salvar-item-3d',args=[a.id]),'eventos':reverse('evento-item-3d',args=[a.id]),'meus_itens':reverse('meus-itens-3d'),'conferencia':conferencia,'ordem_faixa':ordem,'url_trilha':'/trilha/'}

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
        if (existente and revisao<=existente.revisao and existente.receita==receita
                and existente.titulo==titulo and bytes(existente.imagem)==imagem):
            tentativa=Tentativa3D.objects.filter(pessoa=pessoa,atividade=a,projeto=existente).first()
            entradas=(tentativa.estado or {}).get('historico',[]) if tentativa else []
            registro=next((r for r in reversed(entradas) if r.get('projeto_id')==str(existente.id)
                           and r.get('revisao')==existente.revisao),None)
            return JsonResponse({'projeto':personalizacao(existente),
                                 'avaliacao':_avaliar_salvamento(existente,a,registro.get('antes') if registro else None),
                                 'url_trilha':'/trilha/'})
        anterior=None
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
            anterior={'cores':dict(existente.receita.get('cores',{})),'proporcao':existente.receita.get('proporcao',1),'revisao':existente.revisao} if existente else None
            uso=Projeto3D.objects.filter(pessoa=pessoa,curso__site_id=site_atual()).aggregate(n=Sum('tamanho_imagem'))['n'] or 0
            if uso-(existente.tamanho_imagem if existente else 0)+len(imagem)>50*1024*1024:raise ValueError('Sua coleção atingiu o limite de 50 MiB em imagens.')
            p=existente or Projeto3D(id=projeto_id,pessoa=pessoa,curso=a.aula.curso,grupo=a.grupo)
            p.base=base;p.titulo=titulo;p.receita=receita;p.imagem=imagem;p.tamanho_imagem=len(imagem);p.revisao=revisao+1;p.save()
            if not existente:
                from apps.cursos import eventos
                eventos.emitir_item_criado(p,ocorrido_em=timezone.now())
            tentativa=Tentativa3D.objects.select_for_update().filter(pessoa=pessoa,atividade=a).first()
            historico=list((tentativa.estado or {}).get('historico',[])) if tentativa else []
            historico.append({'projeto_id':str(p.id),'base':f'{base.chave}@{base.versao}',
                             'revisao':p.revisao,'antes':anterior,
                             'depois':{'cores':dict(receita['cores']),'proporcao':receita['proporcao']}})
            Tentativa3D.objects.update_or_create(pessoa=pessoa,atividade=a,defaults={'projeto':p,'estado':{
                'etapa':receita['etapa'],'conferencia':receita['conferencia'],'historico':historico}})
            Evento3D.objects.create(pessoa=pessoa,atividade=a,tipo='salvar',etapa=receita['etapa'])
        return JsonResponse({'projeto':personalizacao(p),'avaliacao':_avaliar_salvamento(p,a,anterior),
                             'url_trilha':'/trilha/'})
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
