"""Ferramenta privada por pessoa; envios independentes do Sandbox e das faixas."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
from urllib.parse import quote, urlsplit

from django.core import signing
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from . import sessao, telas_marketplace

PUBLICO='/ferramentas/diagnostico-de-texturas/'
SALT='diagnostico-texturas-upload-v1'
MAX_FILE=64*1024*1024
SINTOMAS={'repetida':'A pintura aparece em mais de um lugar','sumiu':'A textura não aparece',
          'posicao':'A imagem ficou fora do lugar','duplicada':'Pode haver peças duplicadas','nao_sei':'Não sei o que aconteceu'}


def privada(response):
    response['Cache-Control']='private, no-store'
    response['X-Robots-Tag']='noindex, nofollow'
    response['Vary']='Cookie'
    response['X-Content-Type-Options']='nosniff'
    return response


def root():
    path=telas_marketplace._pasta_privada()/'diagnosticos-texturas'
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    return path


def identity(request):
    person=sessao.quem_e(request)
    return (sessao.site_desta_instalacao(),person) if person else (None,None)


def salvar(path,data):
    temp=path.with_suffix('.parcial')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    temp.replace(path)


def owned(ident,site,person):
    if not person or not re.fullmatch(r'[a-f0-9]{32}',str(ident)):
        raise Http404
    directory=root()/str(ident)
    try:
        meta=json.loads((directory/'meta.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):
        raise Http404
    if meta.get('pessoa')!=person or meta.get('site')!=site:
        raise Http404
    return directory,meta


@require_GET
def pagina(request):
    site,person=identity(request)
    current=request.GET.get('analise','')
    if current:
        owned(current,site,person)
    token=signing.dumps({'site':site,'pessoa':person},salt=SALT) if person else ''
    return privada(render(request,'texturas/diagnostico.html',{
        'autenticado':bool(person),'token':token,'atual':current,'prefixo':PUBLICO,
        'login':'/login?next='+quote(PUBLICO,safe=''),'sintomas':SINTOMAS.items()}))


def post_authorized(request,site,person):
    if not person:
        return False
    origin=request.META.get('HTTP_ORIGIN','')
    referer=request.META.get('HTTP_REFERER','')
    if origin and origin.rstrip('/')!='https://meshcraft.top':
        return False
    if referer:
        parsed=urlsplit(referer)
        if parsed.scheme!='https' or parsed.netloc!='meshcraft.top':
            return False
    try:
        signed=signing.loads(request.POST.get('token',''),salt=SALT,max_age=86400)
    except signing.BadSignature:
        return False
    return signed=={'site':site,'pessoa':person}


@csrf_exempt  # token assinado por pessoa e site; o cookie de /encomendas não viaja à URL pública
@require_POST
def enviar(request):
    site,person=identity(request)
    if not post_authorized(request,site,person):
        return privada(JsonResponse({'erro':'Entre na sua conta e atualize a página antes de enviar.'},status=403))
    file=request.FILES.get('projeto')
    if not file or not file.size or file.size>MAX_FILE:
        return privada(JsonResponse({'erro':'Escolha um projeto .blend de até 64 MB.'},status=400))
    name=file.name.replace('\\','/').rsplit('/',1)[-1][:160]
    if Path(name).suffix.lower()!='.blend':
        return privada(JsonResponse({'erro':'Nesta versão, envie o projeto do Blender no formato .blend.'},status=400))
    previous=request.POST.get('anterior','')
    if previous:
        owned(previous,site,person)
    ident=uuid.uuid4().hex
    directory=root()/ident
    directory.mkdir(mode=0o700)
    digest=hashlib.sha256()
    total=0
    with (directory/'entrada.blend').open('xb') as stream:
        for chunk in file.chunks():
            total+=len(chunk)
            if total>MAX_FILE:
                salvar(directory/'estado.json',{'estado':'falha','falha':'O envio ultrapassou 64 MB. Envie uma cópia menor.'})
                return privada(JsonResponse({'erro':'O envio ultrapassou 64 MB.'},status=413))
            digest.update(chunk)
            stream.write(chunk)
    symptom=request.POST.get('sintoma','nao_sei')
    if symptom not in SINTOMAS:symptom='nao_sei'
    meta={'id':ident,'pessoa':person,'site':site,'nome':name,'sha256':digest.hexdigest(),
          'criada_em':datetime.now(timezone.utc).isoformat(),'sintoma':symptom,
          'desejo':request.POST.get('desejo','').strip()[:1500],'anterior':previous}
    salvar(directory/'meta.json',meta)
    salvar(directory/'estado.json',{'estado':'aguardando'})
    salvar(directory/'pedido.json',{'sha256':digest.hexdigest(),'id':ident})
    return privada(JsonResponse({'id':ident,'url':PUBLICO+'?analise='+ident},status=201))


@require_GET
def resultado(request,ident):
    site,person=identity(request)
    directory,meta=owned(ident,site,person)
    try:
        state=json.loads((directory/'estado.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):
        state={'estado':'aguardando'}
    data={'id':str(ident),'nome':meta['nome'],'desejo':meta['desejo'],'sintoma':SINTOMAS.get(meta['sintoma'],''),**state}
    if state['estado']=='concluida':
        try:
            report=json.loads((directory/'saida'/'resultado.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):
            data.update(estado='falha',falha='Não consegui ler o resultado. O projeto original continua guardado.')
        else:
            data['relatorio']=report
            previous=meta.get('anterior')
            if previous:
                old_dir,old_meta=owned(previous,site,person)
                try:
                    old=json.loads((old_dir/'saida'/'resultado.json').read_text(encoding='utf-8'))
                except (OSError,ValueError):pass
                else:
                    if old.get('estado')=='concluida':
                        def counts(r):
                            return {code:sum(a['codigo']==code for a in r.get('achados',[]))
                                    for code in ('uv_compartilhada','uv_sem_area','sem_uv','imagem_indisponivel','geometria_sobreposta','faces_sem_material','mapa_uv_ausente')}
                        data['comparacao']={'anterior':previous,'antes':counts(old),'agora':counts(report),
                                            'mesmo_conteudo':old_meta['sha256']==meta['sha256'],
                                            'leitura_parcial':bool(old.get('limites') or report.get('limites'))}
    return privada(JsonResponse(data))


@require_GET
def imagem(request,ident,nome):
    site,person=identity(request)
    directory,_=owned(ident,site,person)
    if not re.fullmatch(r'(frontal|perspectiva)\.png|uv-[0-9]{1,6}\.svg',nome):
        raise Http404
    file=directory/'saida'/nome
    if not file.is_file() or file.is_symlink() or file.stat().st_size>8*1024*1024:
        raise Http404
    response=FileResponse(file.open('rb'),content_type='image/svg+xml' if nome.endswith('.svg') else 'image/png')
    response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return privada(response)
