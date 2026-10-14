"""Restricted machine endpoint using this cell's existing vault and spend ledger."""
import hmac
import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import modelo
from .revisor_contract import validate, validate_output, INSTRUCTIONS, FORMAT


@csrf_exempt
def explicar(request):
    def reply(data,status=200):
        response=JsonResponse(data,status=status)
        response['Cache-Control']='no-store'
        return response
    if request.method!='POST': return reply({'error':'method_denied'},405)
    # REMOTE_ADDR is the socket peer. Never trust forwarded source headers.
    if request.META.get('REMOTE_ADDR')!='172.16.1.251':
        return reply({'error':'peer_denied'},403)
    token=os.environ.get('REVISOR_AI_TOKEN','')
    if not token or not hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+token):
        return reply({'error':'unauthorized'},401)
    try:
        if int(request.META.get('CONTENT_LENGTH','0')) not in range(1,8193):
            return reply({'error':'body_limit'},413)
        if request.content_type!='application/json': raise ValueError('type')
        data=validate(json.loads(request.body))
    except (ValueError,TypeError,KeyError):
        return reply({'error':'invalid_report'},400)
    try:
        result=modelo.responder(modelo='gpt-6-luna',instrucoes=INSTRUCTIONS,
            itens=[{'role':'user','content':json.dumps(data,ensure_ascii=False)}],
            ferramentas=None,max_saida=2000,esforco='none',formato=FORMAT,
            origem='revisor',revisor=True)
    except (modelo.ProblemaDoModelo, ValueError, TypeError, KeyError):
        # No provider error or credential reaches the consuming cell.
        return reply({'error':'narrative_unavailable','fallback':True},503)
    usage={'input_tokens':result.consumo.tokens_entrada,'output_tokens':result.consumo.tokens_saida,
           'estimated_usd_upper':str(result.consumo.custo_estimado_usd)}
    try:
        if not result.completa or result.chamadas: raise ValueError('incomplete')
        narrative=validate_output(result.texto,data)
    except (ValueError,TypeError,KeyError):
        return reply({'fallback':True,'usage':usage,'reason':'invalid_narrative'})
    return reply({'fallback':False,'narrative':narrative,'usage':usage,'pedagogy':'pending_livia'})
