"""Envia o ensaio administrativo pelo transporte e histórico já existentes."""
import hmac
import json
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables

from apps.core.auth import tokens_de_publicacao
from apps.whatsapp.models import MensagemWhatsApp
from apps.whatsapp.service import normalizar_telefone
from .models import EnvioRegistrado
from .tasks import enviar_notificacao

TIPO = 'hotmart_acesso_teste'


def autorizado(request):
    esquema, _, token = request.headers.get('Authorization', '').partition(' ')
    return esquema.lower() == 'bearer' and bool(token) and any(
        hmac.compare_digest(token, esperado) for esperado in tokens_de_publicacao())


def resultado(site_id, chave):
    linhas = EnvioRegistrado.objects.filter(site_id=site_id, order_id='hotmart-teste:' + chave, tipo=TIPO)
    itens = []
    for linha in linhas.order_by('canal'):
        estado = linha.status
        if linha.canal == 'whatsapp':
            mensagem = MensagemWhatsApp.objects.filter(site_id=site_id, origem='transacional', referencia=str(linha.pk)).first()
            if mensagem:
                estado = mensagem.status
        itens.append({'canal': linha.canal, 'estado': estado, 'id': linha.pk})
    return {'envios': itens}


@csrf_exempt
@sensitive_variables()
def testes(request, chave=None):
    if not autorizado(request):
        return JsonResponse({'erro': 'nao_autorizado'}, status=401)
    if chave is not None:
        if request.method != 'GET':
            return JsonResponse({'erro': 'metodo_nao_permitido'}, status=405)
        r = JsonResponse(resultado(request.GET.get('site_id', ''), str(chave)))
        r['Cache-Control'] = 'no-store'
        return r
    if request.method != 'POST':
        return JsonResponse({'erro': 'metodo_nao_permitido'}, status=405)
    try:
        dados = json.loads(request.body)
        if dados.get('modo') != 'teste_administrativo':
            raise ValueError()
        chave = str(uuid.UUID(dados['chave']))
        for campo, limite in (('site_id', 64), ('email', 254), ('assunto', 255), ('corpo', 10000)):
            if not isinstance(dados.get(campo), str) or not 0 < len(dados[campo].strip()) <= limite:
                raise ValueError()
        validate_email(dados['email'])
        canais = dados.get('canais')
        if not isinstance(canais, list) or not canais or len(set(canais)) != len(canais) or not set(canais) <= {'email', 'whatsapp'}:
            raise ValueError()
        if not dados['assunto'].startswith('[TESTE ADMINISTRATIVO]'):
            raise ValueError()
        telefone = ''
        if 'whatsapp' in canais:
            if not isinstance(dados.get('telefone'), str) or not dados['telefone'].startswith('+'):
                raise ValueError()
            telefone = '+' + normalizar_telefone(dados['telefone'])
    except (ValueError, KeyError, TypeError, AttributeError, ValidationError):
        return JsonResponse({'erro': 'teste_invalido'}, status=422)
    with transaction.atomic():
        for canal in canais:
            destino = dados['email'].strip().lower() if canal == 'email' else telefone
            linha, criada = EnvioRegistrado.objects.get_or_create(
                site_id=dados['site_id'], order_id='hotmart-teste:' + chave, tipo=TIPO, canal=canal,
                defaults={'event': 'hotmart.teste.acesso', 'destinatario': destino,
                          'assunto': dados['assunto'], 'corpo': dados['corpo']})
            if linha.destinatario != destino or linha.corpo != dados['corpo'] or linha.assunto != dados['assunto']:
                transaction.set_rollback(True)
                return JsonResponse({'erro': 'referencia_com_outros_dados'}, status=409)
            if criada or linha.status == 'pendente':
                transaction.on_commit(lambda pk=linha.pk: enviar_notificacao(pk))
    return JsonResponse(resultado(dados['site_id'], chave))
