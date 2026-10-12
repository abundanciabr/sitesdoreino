"""Encaminhamento no mesmo site, sem abrir a rede da célula pública."""
import re
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

ROOT='/ferramentas/diagnostico-de-texturas/'
UPSTREAM='https://meshcraft.top/encomendas/diagnostico-texturas/'
LIMIT=66*1024*1024


def response(text,status):
    result=HttpResponse(text,status=status,content_type='text/plain; charset=utf-8')
    result['Cache-Control']='private, no-store'
    return result


@csrf_exempt  # o destino confere o token assinado e a sessão do dono
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
    query=request.META.get('QUERY_STRING','')
    result=response('',307)
    # 307 mantém o método e o arquivo. O navegador leva a sessão diretamente
    # ao destino HTTPS fixo, onde cada resultado é conferido pelo dono.
    result['Location']=UPSTREAM+resto+('?' + query if query else '')
    return result
