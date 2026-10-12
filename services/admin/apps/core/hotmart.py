"""Recepção persistente da Hotmart. Não libera acesso nem envia mensagens."""
import hashlib
import hmac
import json
import uuid

from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from apps.hotmart.models import ConfiguracaoHotmart, EventoHotmart, ProdutoHotmart, TesteHotmart
from apps.hotmart.dados import extrair
from apps.hotmart import operacao

LIMITE = 1024 * 1024


def resposta(dados, status=200):
    r = JsonResponse(dados, status=status)
    r['Cache-Control'] = 'no-store'
    return r


def impressao(valor):
    return hashlib.sha256(valor.encode('utf-8')).hexdigest()


def sem_segredos(valor):
    if isinstance(valor, dict):
        return {k: sem_segredos(v) for k, v in valor.items()
                if k.lower().replace('-', '_') not in ('hottok', 'x_hotmart_hottok', 'authorization', 'access_token')}
    if isinstance(valor, list):
        return [sem_segredos(v) for v in valor]
    return valor


@csrf_exempt
@require_POST
@sensitive_variables()
def webhook(request):
    token = request.headers.get('X-Hotmart-Hottok', '')
    if not token or len(token) > 512:
        return resposta({'erro': 'nao_autorizado'}, 401)
    try:
        config = ConfiguracaoHotmart.objects.filter(pk=1).first()
        if not config or not config.hottok_sha256:
            return resposta({'erro': 'hotmart_nao_configurada'}, 503)
        if not hmac.compare_digest(impressao(token), config.hottok_sha256):
            return resposta({'erro': 'nao_autorizado'}, 401)
        if request.content_type != 'application/json':
            return resposta({'erro': 'envie_json'}, 415)
        if int(request.META.get('CONTENT_LENGTH') or 0) > LIMITE:
            return resposta({'erro': 'corpo_muito_grande'}, 413)
        corpo = request.body
        if len(corpo) > LIMITE:
            return resposta({'erro': 'corpo_muito_grande'}, 413)
        dados = json.loads(corpo, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(dados, dict):
            raise ValueError()
        evento = dados.get('event')
        identificador = dados.get('id')
        if not isinstance(evento, str) or not evento or len(evento) > 100:
            raise ValueError()
        if not isinstance(identificador, str) or not identificador or len(identificador) > 200:
            raise ValueError()
        if not isinstance(dados.get('data'), dict):
            raise ValueError()
        dados = sem_segredos(dados)
        # A unicidade é do evento: aprovação e reembolso da mesma transação
        # são acontecimentos diferentes e ambos precisam ser preservados.
        with transaction.atomic():
            registro, criado = EventoHotmart.objects.get_or_create(
                evento_id=identificador,
                defaults={'evento': evento, 'dados': dados},
            )
            if not criado:
                EventoHotmart.objects.filter(pk=registro.pk).update(
                    recebimentos=F('recebimentos') + 1, ultimo_recebimento=timezone.now())
        return resposta({'recebido': True, 'duplicado': not criado})
    except RequestDataTooBig:
        return resposta({'erro': 'corpo_muito_grande'}, 413)
    except (ValueError, UnicodeError, RecursionError):
        return resposta({'erro': 'evento_invalido'}, 400)
    except DatabaseError:
        # Não confirma recebimento se a gravação falhou; a Hotmart pode repetir.
        return resposta({'erro': 'armazenamento_indisponivel'}, 503)


def resumo(registro):
    return extrair(registro)


@sensitive_post_parameters('hottok')
@sensitive_variables('token')
@require_http_methods(['GET', 'POST'])
def painel(request):
    erro = ''
    site_id, cursos, erro_catalogo = '', [], ''
    try:
        site_id, cursos = operacao.contexto_do_site()
    except ValueError as exc:
        erro_catalogo = str(exc)
    acao = request.POST.get('acao', 'hottok')
    if request.method == 'POST' and acao == 'hottok':
        token = request.POST.get('hottok', '').strip()
        if not token or len(token) > 512:
            erro = 'Cole o Hottok da sua conta Hotmart.'
        else:
            ConfiguracaoHotmart.objects.update_or_create(pk=1, defaults={'hottok_sha256': impressao(token)})
            return redirect('hotmart_painel')
    elif request.method == 'POST':
        try:
            if not site_id:
                raise ValueError(erro_catalogo)
            if acao == 'produto':
                operacao.salvar_produto(site_id, cursos, request.POST)
                return redirect('hotmart_painel')
            elif acao == 'preparar':
                registro = get_object_or_404(EventoHotmart, pk=request.POST.get('evento'))
                teste = operacao.preparar_teste(site_id=site_id, cursos=cursos, registro=registro,
                    dados=request.POST, admin=request.admin)
                return redirect('hotmart_teste', teste_id=teste.pk)
            else:
                raise ValueError('Ação desconhecida. Nenhuma automação foi ativada.')
        except ValueError as exc:
            erro = str(exc)
    contexto = {'admin': request.admin, 'erro': erro,
                'cursos': cursos, 'erro_catalogo': erro_catalogo, 'chave_teste': str(uuid.uuid4()),
                'produtos': ProdutoHotmart.objects.filter(site_id=site_id).order_by('nome'),
                'aprovacoes': EventoHotmart.objects.filter(evento='PURCHASE_APPROVED').order_by('-recebido_em')[:100],
                'testes': TesteHotmart.objects.filter(site_id=site_id).order_by('-criado_em')[:20],
                'configurada': ConfiguracaoHotmart.objects.filter(pk=1).exclude(hottok_sha256='').exists(),
                'total': EventoHotmart.objects.count(),
                'eventos': [resumo(e) for e in EventoHotmart.objects.order_by('-ultimo_recebimento')[:100]]}
    return render(request, 'admin/hotmart.html', contexto)


@require_http_methods(['GET', 'POST'])
def teste_administrativo(request, teste_id):
    teste = get_object_or_404(TesteHotmart, pk=teste_id)
    erro, mensagens = '', None
    if request.method == 'POST':
        try:
            if request.POST.get('acao') != 'executar':
                raise ValueError('Ação desconhecida.')
            teste = operacao.executar_teste(teste, request.admin)
            return redirect('hotmart_teste', teste_id=teste.pk)
        except ValueError as exc:
            erro = str(exc)
    try:
        mensagens = operacao.consultar_mensagens(teste)
    except ValueError as exc:
        erro = str(exc)
    estados = {'pendente': 'Aguardando envio', 'enviado': 'Aceito pelo serviço de envio',
               'aceito': 'Aceito pelo WhatsApp', 'entregue': 'Entrega confirmada', 'lido': 'Leitura confirmada',
               'falhou': 'Falha no envio', 'desconhecido': 'Resultado ainda não confirmado'}
    itens = (mensagens or teste.resultado.get('mensagens') or {}).get('envios', [])
    for item in itens:
        item['rotulo'] = estados.get(item.get('estado'), 'Aguardando confirmação')
    return render(request, 'admin/hotmart_teste.html', {'admin': request.admin, 'teste': teste,
        'erro': erro, 'envios': itens, 'pode_executar': not request.admin.get('robo') and
        str(request.admin.get('email') or '').lower() == teste.administrador})
