"""Ensaio de matrícula solicitado pelo painel; sempre marcado como teste."""
import json
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables

from apps.matriculas.editor_turmas import _authorized
from apps.matriculas.services import matricular


@csrf_exempt
@sensitive_variables()
def teste(request):
    if not _authorized(request):
        return JsonResponse({'erro': 'nao_autorizado'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'erro': 'metodo_nao_permitido'}, status=405)
    try:
        dados = json.loads(request.body)
        if dados.get('modo') != 'teste_administrativo':
            raise ValueError()
        chave = str(uuid.UUID(dados['chave']))
        for campo, limite in (('site_id', 64), ('product_id', 100), ('nome', 200), ('email', 254)):
            if not isinstance(dados.get(campo), str) or not 0 < len(dados[campo].strip()) <= limite:
                raise ValueError()
        email = dados['email'].strip().lower()
        validate_email(email)
    except (ValueError, KeyError, TypeError, AttributeError, ValidationError):
        return JsonResponse({'erro': 'teste_invalido'}, status=422)
    linha, criada = matricular(site_id=dados['site_id'], order_id='hotmart-teste:' + chave,
        product_id=dados['product_id'], email=email, name=dados['nome'],
        provider='hotmart_teste', provider_reference_id=chave, em_teste=True)
    if (linha.site_id != dados['site_id'] or linha.email != email or linha.product_id != dados['product_id']
            or not linha.em_teste or linha.provider != 'hotmart_teste'):
        return JsonResponse({'erro': 'referencia_com_outros_dados'}, status=409)
    return JsonResponse({'id': str(linha.pk), 'status': linha.status, 'em_teste': linha.em_teste,
                         'criada': criada}, status=201 if criada else 200)
