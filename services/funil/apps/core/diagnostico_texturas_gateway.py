"""Endereço público da ferramenta; a aplicação confere sessão e dono do arquivo."""
import re
import httpx
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

ROOT='/ferramentas/diagnostico-de-texturas/'
UPSTREAM='https://meshcraft.top/encomendas/diagnostico-texturas/'
LIMIT=66*1024*1024


def response(text,status):
    result=HttpResponse(text,status=status,content_type='text/plain; charset=utf-8')
    result['Cache-Control']='private, no-store'
    return result


@csrf_exempt  # a ferramenta confere seu token assinado; não usa cookie de outra célula
def diagnostico_texturas_gateway(request,resto=''):
    if request.get_host().split(':')[0].lower()!='meshcraft.top':
        return response('Página indisponível.',404)
    if request.method not in ('GET','HEAD','POST'):
        return response('Método indisponível.',405)
    if not re.fullmatch(r'|enviar/|analises/[a-f0-9]{32}/|imagens/[a-f0-9]{32}/(?:(?:frontal|perspectiva)\.png|uv-[0-9]{1,6}\.svg)',resto):
        return response('Página indisponível.',404)
    try:
        size=int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:return response('Envio inválido.',400)
    if size>LIMIT:return response('Escolha um arquivo de até 64 MB.',413)
    body=request.read(LIMIT+1) if request.method=='POST' else b''
    if len(body)>LIMIT:return response('Escolha um arquivo de até 64 MB.',413)
    headers={'Host':'meshcraft.top','X-Forwarded-Proto':'https','Accept':request.META.get('HTTP_ACCEPT','*/*')}
    for key,meta in [('Cookie','HTTP_COOKIE'),('Origin','HTTP_ORIGIN'),('Referer','HTTP_REFERER'),('Content-Type','CONTENT_TYPE')]:
        if request.META.get(meta):headers[key]=request.META[meta]
    query=request.META.get('QUERY_STRING','')
    url=UPSTREAM+resto+('?' + query if query else '')
    try:
        with httpx.stream(request.method,url,headers=headers,content=body,timeout=httpx.Timeout(45,connect=5),follow_redirects=False,trust_env=False) as upstream:
            chunks,total=[],0
            for chunk in upstream.iter_bytes():
                total+=len(chunk)
                if total>10*1024*1024:return response('Não foi possível carregar esta resposta.',502)
                chunks.append(chunk)
            result=HttpResponse(b''.join(chunks),status=upstream.status_code)
            for key in ('content-type','cache-control','content-security-policy','x-content-type-options','x-robots-tag','vary'):
                if upstream.headers.get(key):result[key]=upstream.headers[key]
            return result
    except (httpx.HTTPError,OSError,ValueError):
        return response('A ferramenta está indisponível agora. Tente novamente em instantes.',503)
