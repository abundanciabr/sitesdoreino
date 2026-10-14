import json
import os
import re
import uuid
from datetime import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from django.utils import timezone
from django.core import signing
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.http import JsonResponse, Http404, HttpResponseRedirect, FileResponse
from django.middleware.csrf import get_token
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from apps.core.clients import CatalogoClient, IdentidadeClient, IdentidadeIndisponivel
from apps.core.whatsapp import _pedir as pedir_whatsapp
from apps.core.templatetags.nomes_admin import primeiro_nome
from apps.agentes import modelo
from .models import Configuracao, Assunto, Conhecimento, Conversa, Mensagem, Responsavel, Aviso, PreviaForum, AgendaDoProduto, MODOS
from . import service
from . import escala
from .expediente import disponibilidade


def site(request):
    s=CatalogoClient().site_por_host(request.get_host().split(':')[0].lower())
    if not s:
        raise Http404
    return str(s['id'])


def admin(request, somente_admin=False):
    if not getattr(request,'admin',None) or (somente_admin and request.admin.get('equipe_apenas')):
        raise Http404


def resposta(d,status=200):
    r=JsonResponse(d,status=status)
    r['Cache-Control']='no-store'
    r['X-Content-Type-Options']='nosniff'
    return r


def serializar(conversa, depois=0, antes=0):
    msgs=conversa.mensagens.all()
    if depois: msgs=msgs.filter(pk__gt=depois)
    if antes: msgs=msgs.filter(pk__lt=antes)
    lista=list(msgs.order_by('-id')[:100])[::-1]
    return {'id':str(conversa.pk),'estado':conversa.estado,'assunto':conversa.assunto.nome,
      'atendente':conversa.atendente_nome,'atendente_id':conversa.atendente_id,'avaliacao':conversa.avaliacao,
      'prioridade':conversa.prioridade,'estado_nome':__import__('apps.atendimento.gestao',fromlist=['ESTADOS']).ESTADOS.get(conversa.estado,conversa.estado),
      'mostrar_avaliacao':service.avaliacao_disponivel(conversa),
      'resolvida':conversa.resolucao == 'confirmada',
      'mensagens':[{'id':m.pk,'autor':m.autor,'nome':primeiro_nome(m.nome) if m.autor == 'aluno' else m.nome,'texto':m.texto,'fontes':m.fontes,
                   'em':m.criada_em.isoformat()} for m in lista],
      'tem_anteriores':bool(lista and conversa.mensagens.filter(pk__lt=lista[0].pk).exists())}


@require_http_methods(['GET','POST'])
def aluno(request):
    try:
        identidade=IdentidadeClient().sessao_completa(request.META.get('HTTP_COOKIE',''))
    except IdentidadeIndisponivel:
        return resposta({'erro':'Não foi possível conferir sua sessão. Tente novamente.'},503)
    visitante = None
    if not identidade.get('autenticado') or not identidade.get('id'):
        try:
            visitante = request.get_signed_cookie('meshcraft_suporte', salt='suporte-visitante', max_age=31536000)
            uuid.UUID(visitante)
        except (KeyError, ValueError, signing.BadSignature):
            visitante = str(uuid.uuid4())
        identidade = {'autenticado': True, 'id': 'visitante-' + visitante, 'nome_exibido': 'Visitante'}
    resultado = _conversar(request, identidade)
    if visitante:
        resultado.set_signed_cookie('meshcraft_suporte', visitante, salt='suporte-visitante',
            max_age=31536000, secure=True, httponly=True, samesite='Lax', path='/admin/')
    return resultado


@require_http_methods(['GET','POST'])
def chat_equipe(request):
    admin(request)
    from apps.core.equipe import _membro_da_sessao
    membro = _membro_da_sessao(request)
    dono = 'equipe-membro-' + str(membro.pk) if membro else 'equipe-admin-' + str(request.admin['id'])
    return _conversar(request, {'autenticado': True, 'id': dono,
        'nome_exibido': request.admin.get('nome') or 'Equipe'})


@require_http_methods(['GET'])
def chat_arquivo(request, nome):
    admin(request)
    tipos = {'suporte.js': 'text/javascript', 'suporte.css': 'text/css', 'gerenciamento.js':'text/javascript', 'gerenciamento.css':'text/css'}
    if nome not in tipos:
        raise Http404
    caminho = Path(__file__).resolve().parent / 'static' / 'atendimento' / nome
    r = FileResponse(caminho.open('rb'), content_type=tipos[nome])
    r['Cache-Control'] = 'private, max-age=3600'
    r['X-Content-Type-Options'] = 'nosniff'
    return r


def _conversar(request, identidade):
    if not identidade.get('autenticado') or not identidade.get('id'):
        return resposta({'erro':'Entre na sua conta para conversar com o suporte.','entrar':'/entrar/google'},401)
    sid=site(request)
    c=service.config(sid)
    expediente=disponibilidade(c)
    dono=str(identidade['id'])
    try:
        d=json.loads(request.body) if request.method=='POST' else request.GET
        if not isinstance(d,dict) and request.method=='POST': raise ValueError
        id_bruto=d.get('conversa')
        conversa=None
        if id_bruto:
            cid=uuid.UUID(str(id_bruto))
            conversa=Conversa.objects.filter(pk=cid,site_id=sid,pessoa_id=dono).first()
            if not conversa and Conversa.objects.filter(pk=cid).exists(): raise Http404
        if request.method=='POST':
            acao=d.get('acao','mensagem')
            if acao=='novo':
                conversa=service.novo_atendimento(sid,dono,identidade.get('nome_exibido'),
                    d['nova_conversa'],d.get('pagina',''),d.get('curso',''),d.get('aula',''))
            elif acao=='mensagem':
                texto=str(d.get('texto','')).strip()
                ref=str(d.get('referencia',''))
                if not texto or len(texto)>6000 or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',ref):
                    return resposta({'erro':'Escreva uma mensagem com até 6000 caracteres.'},422)
                if not conversa:
                    conversa=service.conversa_atual(sid,dono)
                assunto=(get_object_or_404(Assunto,site_id=sid,pk=d['assunto']) if d.get('assunto')
                         else service.assunto_da_mensagem(sid,texto,conversa))
                with transaction.atomic():
                    if not conversa:
                        conversa,_=Conversa.objects.get_or_create(pk=cid if id_bruto else uuid.uuid5(uuid.NAMESPACE_URL,'meshcraft-suporte:'+sid+':'+dono),defaults={
                            'site_id':sid,'pessoa_id':dono,'nome':str(identidade.get('nome_exibido') or 'Aluno')[:160],
                            'assunto':assunto,'pagina':urlsplit(str(d.get('pagina',''))).path[:500],
                            'curso':str(d.get('curso',''))[:200],'aula':str(d.get('aula',''))[:200],
                            'estado':'aguardando' if assunto.modo=='assistido' else 'robo'})
                    conversa=Conversa.objects.select_for_update().get(pk=conversa.pk,site_id=sid,pessoa_id=dono)
                    if conversa.mensagens.filter(referencia=ref).exists():
                        return resposta({'conversa':serializar(conversa),'csrf':get_token(request),
                            'disponibilidade':expediente,'aviso_horario':not expediente['respostas_abertas']})
                    if conversa.arquivada_em:
                        conversa.arquivada_em = None
                        conversa.save(update_fields=['arquivada_em'])
                    if not d.get('assunto'):
                        conversa.assunto=assunto
                    if d.get('pagina'):
                        conversa.pagina=urlsplit(str(d['pagina'])).path[:500]
                    if d.get('curso'):
                        conversa.curso=str(d['curso'])[:200]
                        conversa.aula=str(d.get('aula',''))[:200]
                    reabriu=conversa.estado=='encerrado'
                    if reabriu:
                        escala.reabrir(conversa, 'nova mensagem', dono)
                        conversa.atendente_id=''
                        conversa.atendente_nome=''
                        conversa.estado='robo' if conversa.assunto.modo!='assistido' else 'aguardando'
                        conversa.resolvida_robo=False
                        conversa.solicitou_pessoa=False
                    ja_respondeu=not reabriu and conversa.mensagens.filter(referencia__startswith='auto-').exists()
                    escala.classificar(conversa, texto)
                    Mensagem.objects.create(conversa=conversa,referencia=ref,autor='aluno',nome=conversa.nome,texto=texto,
                        tipo=conversa.tipo, rodada=conversa.rodada)
                    conversa.resolvida_em=None; conversa.resolucao=''
                    conversa.sugestao={}
                    if conversa.estado=='aguardando_aluno': conversa.estado='andamento' if conversa.atendente_id else 'aguardando'
                    if conversa.assunto.modo=='conversa':
                        if not conversa.atendente_id and not conversa.solicitou_pessoa:
                            conversa.estado='robo'
                        conversa.processar=not conversa.solicitou_pessoa or bool(conversa.atendente_id)
                        conversa.save()
                    elif not conversa.atendente_id and (conversa.assunto.modo=='assistido' or
                            (conversa.assunto.modo=='base' and ja_respondeu) or
                            re.search(r'\b(humano|atendente|pessoa|não resolveu|nao resolveu)\b',texto,re.I)):
                        service.encaminhar(conversa)
                        conversa.processar=True
                        conversa.save(update_fields=['processar'])
                    else:
                        if not conversa.atendente_id: conversa.estado='robo'
                        conversa.processar=True
                        conversa.save()
            else:
                if not conversa: raise Http404
                with transaction.atomic():
                    conversa=Conversa.objects.select_for_update().get(pk=conversa.pk,site_id=sid,pessoa_id=dono)
                    if acao=='pessoa':
                        escala.reabrir(conversa, 'pedido de pessoa', dono)
                        if not conversa.atendente_id:
                            conversa.solicitou_pessoa=True
                            service.encaminhar(conversa)
                    elif acao=='resolvido':
                        if not service.avaliacao_disponivel(conversa):
                            return resposta({'erro':'Aguarde uma resposta antes de confirmar a resolução.'},422)
                        ultima=conversa.mensagens.last()
                        if conversa.estado=='robo' and ultima and ultima.referencia.startswith('auto-'):
                            conversa.resolvida_robo=True
                        escala.encerrar(conversa, 'aluno', resolvido=True); conversa.save()
                    elif acao=='nao_resolvido':
                        if not service.avaliacao_disponivel(conversa):
                            return resposta({'erro':'Aguarde uma resposta antes de avaliar a resolução.'},422)
                        if conversa.estado != 'encerrado':
                            escala.encerrar(conversa, 'aluno')
                        escala.reabrir(conversa, 'aluno informou que não resolveu', dono)
                        conversa.estado='aguardando'; conversa.processar=True; conversa.solicitou_pessoa=True
                        conversa.save()
                    elif acao=='avaliar':
                        nota=int(d.get('nota',0))
                        if nota not in range(1,6): raise ValueError
                        conversa.avaliacao=nota;conversa.save(update_fields=['avaliacao'])
                    else: raise ValueError
        elif not conversa and not id_bruto:
            conversa=service.conversa_atual(sid,dono)
        return resposta({'csrf':get_token(request),'pessoa':dono,'horario':expediente['horario'],
            'disponibilidade':expediente,
            'aviso_horario':request.method == 'POST' and d.get('acao','mensagem') == 'mensagem' and not expediente['respostas_abertas'],
            'mensagem':c.mensagem,'assuntos':list(Assunto.objects.filter(site_id=sid).values('id','nome')),
            'historico':[{'id':str(i.pk),'assunto':i.assunto.nome,'estado':i.estado,'em':i.atualizada_em.isoformat()}
                        for i in Conversa.objects.filter(site_id=sid,pessoa_id=dono).select_related('assunto')[:50]],
            'conversa':serializar(conversa,int(d.get('depois',0)),int(d.get('antes',0))) if conversa else None})
    except PermissionError:
        raise Http404 from None
    except (ValueError,TypeError,KeyError):
        return resposta({'erro':'Confira a mensagem e tente novamente.'},422)


def prefixo(request):
    return '/admin/equipe/atendimento' if request.path_info.startswith('/equipe/') else '/admin/atendimento'


def contexto(request,sid):
    config = service.config(sid)
    return {'admin':request.admin,'suporte_prefixo':prefixo(request),'assuntos':Assunto.objects.filter(site_id=sid),'config':config,'modos':MODOS,'expediente':disponibilidade(config)}


@require_http_methods(['GET','POST'])
def fila(request):
    from .gestao import contexto_fila,identidade_atendente
    admin(request);sid=site(request)
    if request.method == 'POST':
        from .acoes_fila import executar
        return executar(request, sid)
    ctx=contexto_fila(request,sid)
    if request.GET.get('arquivada'):
        try:
            ctx['arquivada'] = Conversa.objects.filter(site_id=sid, pk=uuid.UUID(request.GET['arquivada']), arquivada_em__isnull=False).first()
        except ValueError:
            pass
    if request.path_info.endswith('/conversas/'):
        abertas=Conversa.objects.filter(site_id=sid,arquivada_em__isnull=True).exclude(estado='encerrado')
        selecionada=abertas.filter(atendente_id__in=[identidade_atendente(request)[0],str(request.admin['id'])]).first() or abertas.first() or Conversa.objects.filter(site_id=sid,arquivada_em__isnull=True).first()
        if selecionada: return HttpResponseRedirect(prefixo(request)+'/'+str(selecionada.pk)+'/')
        ctx['entrada_conversas']=True
    return render(request,'admin/atendimento_fila.html',ctx)


@require_http_methods(['GET','POST'])
def conversa_admin(request,conversa_id):
    admin(request);sid=site(request);ctx=contexto(request,sid)
    conversa=get_object_or_404(Conversa.objects.select_related('assunto').prefetch_related('mensagens'),pk=conversa_id,site_id=sid)
    from .gestao import contexto_conversa,identidade_atendente,ESTADOS,PRIORIDADES,responsaveis
    contexto_conversa(request,sid,conversa,ctx)
    recado=''
    if request.method=='POST':
        acao=request.POST.get('acao','')
        if conversa.origem_conversa and acao in ('responder', 'robo', 'sugerir', 'avisar'):
            return resposta({'erro':'Este histórico pertence ao canal original. Confira e responda pela caixa do CRM.'},409)
        if acao=='proximo_passo':
            from datetime import datetime
            from .models import HistoricoDoPasso
            texto=request.POST.get('proximo_passo','').strip()
            escolhido=request.POST.get('passo_responsavel','')
            permitidos={r['id']:r['nome'] for r in responsaveis(request,sid)}
            try:
                prazo=datetime.fromisoformat(request.POST['passo_prazo']) if request.POST.get('passo_prazo') else None
                if prazo and timezone.is_naive(prazo): prazo=timezone.make_aware(prazo)
                if len(texto)>2000 or (texto and (not prazo or escolhido not in permitidos)): raise ValueError
                if not texto: prazo=None;escolhido=''
            except (ValueError, KeyError):
                return resposta({'erro':'Informe o próximo passo, responsável e prazo interno.'},422)
            with transaction.atomic():
                c=Conversa.objects.select_for_update().get(pk=conversa.pk,site_id=sid)
                if request.POST.get('passo_versao') != str(c.passos.count()):
                    return resposta({'erro':'O acompanhamento mudou. Reabra a conversa antes de salvar.'},409)
                c.proximo_passo=texto;c.passo_prazo=prazo;c.passo_responsavel=escolhido
                c.passo_responsavel_nome=permitidos.get(escolhido,'');c.save()
                HistoricoDoPasso.objects.create(conversa=c,texto=texto,prazo=prazo,responsavel=escolhido,
                    responsavel_nome=c.passo_responsavel_nome,por=identidade_atendente(request)[0])
            return HttpResponseRedirect(prefixo(request)+'/'+str(c.pk)+'/')
        elif acao=='sugerir':
            if conversa.assunto.modo == 'assistido':
                from .contexto import preparar
                sug=preparar(conversa)
            else:
                sug=service.sugerir(conversa)
            Conversa.objects.filter(pk=conversa.pk).update(sugestao=sug)
        elif acao=='guardar_base':
            return HttpResponseRedirect(prefixo(request)+'/base/?conversa='+str(conversa.pk)+'&mensagem='+request.POST.get('mensagem',''))
        elif acao=='interesse':
            from .contexto import salvar_interesse
            try:
                salvar_interesse(conversa,request.POST.get('produto_id',''),identidade_atendente(request)[1])
            except ValueError:
                ctx.update(erro='Escolha um produto do catálogo.',conversa=conversa)
                return render(request,'admin/atendimento_conversa.html',ctx,status=422)
            return HttpResponseRedirect(prefixo(request)+'/'+str(conversa.pk)+'/')
        else:
            with transaction.atomic():
                conversa=Conversa.objects.select_for_update().get(pk=conversa.pk,site_id=sid)
                quem,nome_atendente=identidade_atendente(request)
                if acao!='organizar' and conversa.atendente_id and conversa.atendente_id not in (quem,str(request.admin['id'])):
                    ctx.update(erro='Este atendimento já está com outra pessoa. Peça que ela devolva o atendimento ao robô.',conversa=conversa)
                    return render(request,'admin/atendimento_conversa.html',ctx,status=409)
                if acao in ('assumir','responder'):
                    if acao == 'responder':
                        texto=request.POST.get('texto','').strip()
                        ref=request.POST.get('referencia','')
                        if not texto or len(texto)>6000 or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',ref):
                            return resposta({'erro':'Escreva uma resposta com até 6000 caracteres.'},422)
                        if conversa.mensagens.filter(referencia=ref).exists():
                            return HttpResponseRedirect(prefixo(request)+'/'+str(conversa.pk)+'/?enviado=1')
                        expediente = disponibilidade(service.config(sid))
                        if not expediente['respostas_abertas']:
                            return resposta({'erro':expediente['mensagem'], 'disponibilidade':expediente}, 409)
                    if conversa.estado=='encerrado':
                        escala.reabrir(conversa, 'retomada pela equipe', quem)
                    conversa.encerrada_em=None
                    conversa.estado='andamento';conversa.atendente_id=quem;conversa.atendente_nome=nome_atendente[:160]
                    # Não envia respostas automáticas depois da tomada humana.
                    conversa.processar=False
                    if acao=='responder':
                        texto=request.POST.get('texto','').strip()
                        ref=request.POST.get('referencia','')
                        if not texto or len(texto)>6000 or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',ref):
                            ctx.update(erro='Escreva uma resposta com até 6000 caracteres.',conversa=conversa)
                            return render(request,'admin/atendimento_conversa.html',ctx,status=422)
                        mensagem,criada=Mensagem.objects.get_or_create(conversa=conversa,referencia=ref,
                            defaults={'autor':'equipe','nome':conversa.atendente_nome,'texto':texto,
                                'tipo':conversa.tipo,'rodada':conversa.rodada,
                                'tempo_humano_seg':escala.tempo_decorrido(request.POST.get('tempo_token',''),quem,sid,conversa.pk)})
                        if criada and conversa.primeira_resposta_em is None: conversa.primeira_resposta_em=mensagem.criada_em
                        if criada:
                            conversa.resolvida_em=None;conversa.resolucao='';conversa.sugestao={}
                elif acao=='encerrar':
                    escala.encerrar(conversa)
                elif acao=='organizar':
                    estado=request.POST.get('estado',conversa.estado)
                    prioridade=request.POST.get('prioridade',conversa.prioridade)
                    escolhido=request.POST.get('responsavel',conversa.atendente_id)
                    permitidos={r['id']:r['nome'] for r in responsaveis(request,sid)}
                    if estado not in ESTADOS or prioridade not in PRIORIDADES or (escolhido and escolhido not in permitidos):
                        return resposta({'erro':'Confira o status, a prioridade e o responsável.'},422)
                    if conversa.estado=='encerrado' and estado!='encerrado':
                        escala.reabrir(conversa, 'organização pela equipe', quem)
                    if estado=='encerrado' and conversa.estado!='encerrado': escala.encerrar(conversa)
                    elif estado!='encerrado': conversa.encerrada_em=None
                    conversa.estado=estado;conversa.prioridade=prioridade
                    conversa.atendente_id=escolhido;conversa.atendente_nome=permitidos.get(escolhido,'')
                    conversa.processar=estado!='encerrado' and conversa.assunto.modo=='assistido' and bool(conversa.mensagens.filter(autor='aluno').exists())
                elif acao=='robo':
                    conversa.atendente_id='';conversa.atendente_nome=''
                    conversa.solicitou_pessoa=False
                    if conversa.assunto.modo=='assistido':
                        conversa.estado='aguardando';conversa.processar=False
                    else:
                        conversa.estado='robo'
                        ultima=conversa.mensagens.last()
                        conversa.processar=bool(ultima and ultima.autor=='aluno')
                elif acao=='avisar':
                    pass
                else:raise Http404
                conversa.save()
            if acao=='avisar':service.avisar(conversa)
        return HttpResponseRedirect(prefixo(request)+'/'+str(conversa.pk)+'/'+('?enviado=1' if acao=='responder' else ''))
    conversa.refresh_from_db()
    if conversa.sugestao and not service.fontes_atuais(conversa.sugestao.get('fontes',[])):
        conversa.sugestao={'contexto':conversa.sugestao.get('contexto'),
            'demanda':conversa.sugestao.get('demanda'), 'roteiro':conversa.sugestao.get('roteiro'),
            'estado':'A base foi corrigida. Atualize o contexto para usar a versão atual.'}
    if request.GET.get('formato') == 'json':
        try:
            depois=int(request.GET.get('depois','0'))
            if not 0 <= depois <= 2**63-1: raise ValueError
        except ValueError:
            return resposta({'erro':'Confira a última mensagem informada.'},422)
        ctx['conversa']=conversa
        return resposta({'conversa':serializar(conversa,depois),
            'disponibilidade':ctx['expediente'],
            'rascunho':conversa.sugestao.get('resposta',''),
            'contexto_em':conversa.sugestao.get('contexto',{}).get('atualizado_em','') if conversa.sugestao.get('contexto') else '',
            'contexto_html':render_to_string('admin/atendimento_contexto.html',ctx)})
    ctx.update(conversa=conversa,mensagens=conversa.mensagens.all(),referencia=uuid.uuid4().hex,
      tempo_token=escala.token_tempo(identidade_atendente(request)[0],sid,conversa.pk),
      avisos=Aviso.objects.filter(conversa=conversa).select_related('responsavel'),
      sem_responsaveis=not Responsavel.objects.filter(site_id=sid,ativo=True).exists(),
      previas=PreviaForum.objects.filter(conversa=conversa),recado=recado)
    from .contexto import catalogo
    escolhido=conversa.interesse.get('produto_id','')
    ctx.update(produtos=catalogo(),
      produto_marcado=escolhido or ((conversa.sugestao or {}).get('produto_sugerido') or {}).get('id',''),
      agenda_do_interesse=AgendaDoProduto.objects.filter(site_id=sid,produto_id=escolhido).first() if escolhido else None)
    from .contexto import _jornada_sandbox
    ctx['jornada_sandbox'] = _jornada_sandbox(conversa) if conversa.canal == 'site' else None
    from .operacao import origem_atual, piloto
    ctx.update(origem=origem_atual(conversa), piloto=piloto(conversa), passos=conversa.passos.order_by('-pk')[:30],
        passo_versao=conversa.passos.count(),
        passo_prazo_local=timezone.localtime(conversa.passo_prazo).strftime('%Y-%m-%dT%H:%M') if conversa.passo_prazo else '')
    ctx['outros_canais'] = Conversa.objects.filter(site_id=sid,origem_lead=conversa.origem_lead).exclude(pk=conversa.pk) if conversa.origem_lead else []
    return render(request,'admin/atendimento_conversa.html',ctx)


@require_http_methods(['GET','POST'])
def agenda(request):
    from datetime import datetime
    from .contexto import catalogo
    from .gestao import identidade_atendente
    admin(request);sid=site(request);ctx=contexto(request,sid)
    produtos=catalogo()
    if request.method=='POST':
        nomes={p['id']:p['nome'] for p in produtos or []}
        produto_id=request.POST.get('produto_id','');bruto=request.POST.get('inicio','').strip();detalhes=request.POST.get('detalhes','').strip()
        try:
            if produto_id not in nomes or len(detalhes)>2000: raise ValueError
            inicio=datetime.fromisoformat(bruto) if bruto else None
            if inicio and timezone.is_naive(inicio): inicio=timezone.make_aware(inicio)
        except ValueError:
            ctx['erro']='Confira o produto, a data e as informações (até 2000 caracteres).'
        else:
            AgendaDoProduto.objects.update_or_create(site_id=sid,produto_id=produto_id,defaults={'produto_nome':nomes[produto_id],
                'inicio':inicio,'detalhes':detalhes,'atualizado_por':identidade_atendente(request)[1][:160]})
            return HttpResponseRedirect(prefixo(request)+'/agenda/?salvo=1#produto-'+produto_id)
    salvas={a.produto_id:a for a in AgendaDoProduto.objects.filter(site_id=sid)}
    ctx.update(salvo=request.GET.get('salvo')=='1',catalogo_fora=produtos is None,
      produtos=[dict(p,agenda=salvas.get(p['id']),inicio_local=timezone.localtime(salvas[p['id']].inicio).strftime('%Y-%m-%dT%H:%M')
        if p['id'] in salvas and salvas[p['id']].inicio else '') for p in produtos or []])
    return render(request,'admin/atendimento_agenda.html',ctx,status=422 if ctx.get('erro') else 200)


PERGUNTAS={'Site':['Como o aluno entra e recupera o acesso à conta?','O que fazer quando uma página ou recurso do site não funciona?','Como o aluno acompanha o atendimento e recebe a resposta?'],
 'Cursos':['Como o aluno encontra a aula e continua de onde parou?','Como entregar uma prática e pedir ajuda ao professor?','O que fazer quando o vídeo ou arquivo da aula não abre?'],
 'Comunidade':['Como o aluno encontra seu grupo na comunidade?','Como publicar uma dúvida no fórum e acompanhar as respostas?','Quais cuidados o aluno deve ter ao compartilhar seu trabalho?']}


@require_http_methods(['GET','POST'])
def base(request):
    admin(request);sid=site(request);ctx=contexto(request,sid)
    item=None;erro=''
    edit=request.GET.get('editar') or request.POST.get('id')
    if edit:
        item=get_object_or_404(Conhecimento,pk=edit,site_id=sid)
    conversa=None;pergunta='';texto='';curso=''
    cid=request.GET.get('conversa') or request.POST.get('conversa')
    if cid:
        conversa=get_object_or_404(Conversa,site_id=sid,pk=cid)
        if request.GET.get('mensagem_canal') and conversa.origem_conversa:
            from .operacao import origem_atual
            original=origem_atual(conversa) or {}
            historico=original.get('mensagens',[])
            msg=next((m for m in historico if str(m.get('id')) == request.GET['mensagem_canal']
                and m.get('autor') == 'pessoa' and m.get('direcao') == 'saida'
                and m.get('estado_envio') in ('aceito','enviado','entregue','lido')),None)
            if not msg: raise Http404
            anteriores=historico[:historico.index(msg)]
            p=next((m for m in reversed(anteriores) if m.get('direcao')=='entrada'),None)
            pergunta=service.publico((p or {}).get('texto',''),conversa)[:500]
            texto=service.publico(msg.get('texto',''),conversa);curso=conversa.curso
        if request.GET.get('mensagem'):
            msg=get_object_or_404(Mensagem,conversa=conversa,pk=request.GET['mensagem'],autor='equipe')
            pergunta=service.publico((conversa.mensagens.filter(autor='aluno',pk__lt=msg.pk).last() or msg).texto,conversa)[:500]
            texto=service.publico(msg.texto,conversa);curso=conversa.curso
    if request.method=='POST':
        assunto=get_object_or_404(Assunto,site_id=sid,pk=request.POST.get('assunto'))
        pergunta=service.publico(request.POST.get('pergunta'),conversa)[:500]
        texto=service.publico(request.POST.get('resposta'),conversa)[:12000]
        curso=request.POST.get('curso','').strip()[:200]
        if not pergunta or not texto or request.POST.get('reutilizavel')!='sim':
            erro='Confira a pergunta, a resposta e confirme que o texto é reutilizável e não contém dados pessoais.'
        else:
            with transaction.atomic():
                if item:
                    item=Conhecimento.objects.select_for_update().get(pk=item.pk,site_id=sid)
                    if int(request.POST.get('revisao','0')) != item.revisao:
                        ctx.update(erro='Esta resposta mudou em outra tela. Reabra para conferir a versão atual.',item=item)
                        return render(request,'admin/atendimento_base.html',ctx,status=409)
                    item.revisao+=1
                else:item=Conhecimento(site_id=sid)
                item.assunto=assunto;item.pergunta=pergunta;item.resposta=texto;item.curso=curso;item.save()
            return HttpResponseRedirect(prefixo(request)+'/base/?salvo=1')
    q=request.GET.get('q','').strip()[:120]
    consulta=Conhecimento.objects.filter(site_id=sid).select_related('assunto').order_by('-atualizado_em')
    if q:consulta=consulta.filter(Q(pergunta__icontains=q)|Q(resposta__icontains=q)|Q(assunto__nome__icontains=q))
    guiado=request.GET.get('construir')
    assunto_guiado=None
    if guiado:
        assunto_guiado=get_object_or_404(Assunto,site_id=sid,pk=guiado)
        conhecidas=set(Conhecimento.objects.filter(site_id=sid,assunto=assunto_guiado).values_list('pergunta',flat=True))
        roteiro=PERGUNTAS.get(assunto_guiado.nome,[f'Como o aluno começa em {assunto_guiado.nome}?',f'Qual é a dúvida mais comum sobre {assunto_guiado.nome}?',f'O que o aluno deve fazer quando precisa de ajuda sobre {assunto_guiado.nome}?'])
        pergunta=next((p for p in roteiro if p not in conhecidas),f'Que outra dúvida sobre {assunto_guiado.nome} merece uma resposta reutilizável?')
    ctx.update(item=item,itens=consulta[:100],q=q,erro=erro,pergunta=pergunta,resposta_texto=texto,curso=curso,
      conversa=conversa,assunto_guiado=assunto_guiado,salvo=request.GET.get('salvo'))
    candidatas=[]
    for m in Mensagem.objects.filter(conversa__site_id=sid,autor='equipe').select_related('conversa').order_by('-pk')[:100]:
        p=m.conversa.mensagens.filter(autor='aluno',pk__lt=m.pk).last()
        if p and not Conhecimento.objects.filter(site_id=sid,pergunta=service.publico(p.texto,m.conversa)[:500],curso=m.conversa.curso).exists():
            candidatas.append({'mensagem':m,'pergunta':service.publico(p.texto,m.conversa)[:500],
                'resposta':service.publico(m.texto,m.conversa)})
    ctx['candidatas']=candidatas[:20]
    return render(request,'admin/atendimento_base.html',ctx,status=422 if erro else 200)


@require_http_methods(['GET','POST'])
def configuracao(request):
    admin(request,somente_admin=True);sid=site(request);ctx=contexto(request,sid);c=ctx['config'];erro=''
    if request.method=='POST':
        acao=request.POST.get('acao')
        if acao=='geral':
            try:
                inicio=time.fromisoformat(request.POST.get('expediente_inicio') or str(c.expediente_inicio))
                fim=time.fromisoformat(request.POST.get('expediente_fim') or str(c.expediente_fim))
                if inicio >= fim: raise ValueError
            except ValueError:
                erro='Informe o início e o fim do atendimento; o início deve ser antes do fim.'
            if not erro:
                c.expediente_ativo=request.POST.get('expediente_ativo')=='sim'
                c.expediente_inicio=inicio;c.expediente_fim=fim
                c.horario=request.POST.get('horario','').strip()[:200]
                if c.expediente_ativo:c.horario=disponibilidade(c)['horario']
                c.mensagem=request.POST.get('mensagem','').strip()[:2000] or Configuracao._meta.get_field('mensagem').default
                c.ia_ativa=request.POST.get('ia_ativa')=='sim';c.save()
        elif acao=='assunto':
            modo=request.POST.get('modo')
            if modo not in dict(MODOS):raise Http404
            id=request.POST.get('assunto')
            if id:
                a=get_object_or_404(Assunto,site_id=sid,pk=id);a.modo=modo;a.save()
            else:
                nome=request.POST.get('nome','').strip()[:100]
                if not nome:erro='Informe o assunto.'
                else:Assunto.objects.get_or_create(site_id=sid,nome=nome,defaults={'modo':modo})
        elif acao=='responsavel':
            telefone=re.sub(r'\D','',request.POST.get('telefone',''))
            nome=request.POST.get('nome','').strip()[:160]
            if not nome or not 10<=len(telefone)<=15:erro='Informe o nome e o WhatsApp completo do responsável, com o código do país.'
            else:Responsavel.objects.update_or_create(site_id=sid,telefone=telefone,defaults={'nome':nome,'ativo':True})
        elif acao=='desativar_responsavel':
            r=get_object_or_404(Responsavel,site_id=sid,pk=request.POST.get('id'));r.ativo=False;r.save()
        elif acao=='reaproveitar':
            total=service.reaproveitar_responsaveis(sid)
            if not total:erro='Não encontrei telefone cadastrado dos responsáveis da equipe neste site.'
        else:raise Http404
        if not erro:return HttpResponseRedirect(prefixo(request)+'/configuracao/?salvo=1')
    a=service.orcamento(c)
    dados,erro_whatsapp=pedir_whatsapp(sid)
    ctx.update(erro=erro,expediente=disponibilidade(c),salvo=request.GET.get('salvo'),
      responsaveis=Responsavel.objects.filter(site_id=sid,ativo=True),
      whatsapp_estado=(dados or {}).get('conexao',{}).get('estado','indisponivel'),
      whatsapp_erro=erro_whatsapp,orcamento=a,consumo=modelo.gasto_do_mes(a.pk) if a else None)
    return render(request,'admin/atendimento_configuracao.html',ctx,status=422 if erro else 200)


def forum_pedir(metodo,caminho,dados=None):
    base=(os.environ.get('FORUM_API_URL') or '').rstrip('/')
    token=os.environ.get('TOKEN_FORUM') or ''
    if not base or not token:raise ValueError('A conexão administrativa com o fórum não está configurada.')
    if not base.endswith('/interno'):base+='/interno'
    try:
        r=httpx.request(metodo,base+'/suporte'+caminho,json=dados,headers={'Authorization':'Bearer '+token},timeout=15)
        d=r.json()
        if r.status_code!=200 or not isinstance(d,dict):raise ValueError('O fórum recusou a operação. Confira a área e tente consultar novamente.')
        return d
    except (httpx.HTTPError,json.JSONDecodeError):
        raise ValueError('Não foi possível confirmar a operação no fórum. A mesma prévia pode ser consultada novamente sem duplicar a publicação.') from None


@require_http_methods(['GET','POST'])
def previa_forum(request,conversa_id):
    admin(request);sid=site(request);ctx=contexto(request,sid)
    from apps.core.publicacao_manual_docs import admin_humano
    pode_publicar=admin_humano(request)
    conversa=get_object_or_404(Conversa,pk=conversa_id,site_id=sid)
    previa=None;erro='';semelhantes=[];areas=[]
    pid=request.GET.get('previa') or request.POST.get('previa')
    if pid:previa=get_object_or_404(PreviaForum,pk=pid,conversa=conversa)
    if request.method=='POST':
        acao=request.POST.get('acao')
        if acao=='preparar':
            pergunta=service.publico(request.POST.get('pergunta'),conversa)[:12000]
            resp=service.publico(request.POST.get('resposta'),conversa)[:12000]
            titulo=service.publico(request.POST.get('titulo'),conversa)[:180]
            if len(titulo)<5 or not pergunta or not resp:
                erro='Escreva título, pergunta e resposta para preparar a prévia.'
            elif previa and previa.publicada_url:
                erro='Esta prévia já foi publicada.'
            else:
                if not previa:previa=PreviaForum(conversa=conversa)
                previa.titulo=titulo;previa.pergunta=pergunta;previa.resposta=resp
                previa.area=request.POST.get('area','')[:60]
                tid=request.POST.get('topico_existente','')
                previa.topico_existente=int(tid) if tid.isdigit() else None
                previa.save()
                return HttpResponseRedirect(prefixo(request)+'/'+str(conversa.pk)+'/forum/?previa='+str(previa.pk))
        elif acao=='publicar' and previa:
            if not pode_publicar:erro='A publicação exige a confirmação expressa do mantenedor. A equipe pode preparar e guardar a prévia.'
            elif request.POST.get('confirmado')!='sim':erro='Confira a prévia e confirme a publicação em nome da escola.'
            else:
                try:
                    d=forum_pedir('POST','/publicar',{'referencia':str(previa.pk),'area_slug':previa.area,'titulo':previa.titulo,
                      'pergunta':previa.pergunta,'resposta':previa.resposta,'topico_id':previa.topico_existente})
                    previa.publicada_url=d['url'];previa.save(update_fields=['publicada_url'])
                except (ValueError,KeyError) as e:erro=str(e)
    try:
        d=forum_pedir('POST','/buscar',{'q':previa.titulo if previa else service.publico((conversa.mensagens.filter(autor='aluno').last() or conversa).texto if hasattr((conversa.mensagens.filter(autor='aluno').last() or conversa),'texto') else '',conversa)})
        areas=d['areas'];semelhantes=d['topicos']
    except (ValueError,KeyError) as e:erro=erro or str(e)
    ultima=conversa.mensagens.filter(autor='equipe').last()
    pergunta=conversa.mensagens.filter(autor='aluno').last()
    ctx.update(conversa=conversa,previa=previa,erro=erro,areas=areas,semelhantes=semelhantes,pode_publicar=pode_publicar,
      pergunta=service.publico(pergunta.texto,conversa) if pergunta else '',
      resposta_texto=service.publico(ultima.texto,conversa) if ultima else '')
    return render(request,'admin/atendimento_forum.html',ctx,status=422 if erro and request.method=='POST' else 200)
