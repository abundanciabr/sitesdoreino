"""Operação do WhatsApp pelo painel autenticado, sempre no site do host."""
import base64
import hashlib
import re
import uuid
from urllib.parse import quote

import httpx
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .clients import CatalogoClient, MensageriaClient, http
from .porta import PortaAdministrativa


ESTADOS = {
    'pendente': 'Aguardando envio', 'enviando': 'Enviando',
    'aceito': 'Aceita pelo provedor — entrega ainda não confirmada',
    'enviado': 'Enviada — entrega ainda não confirmada',
    'entregue': 'Entrega confirmada', 'lido': 'Leitura confirmada',
    'falhou': 'Falhou', 'desconhecido': 'Resultado desconhecido — não reenviar às cegas',
}

CONEXOES = {'open': 'Conectado', 'connecting': 'Aguardando leitura do QR',
    'close': 'Desconectado', 'nao_configurado': 'Não configurado',
    'aguardando_conexao': 'Aguardando leitura do QR', 'aguardando_qr': 'Preparando um novo QR',
    'indisponivel': 'Conexão indisponível'}


def _pedir(site_id, acao='', payload=None):
    config = MensageriaClient()._configuracao()
    if config is None:
        return None, 'A comunicação com a mensageria ainda não está configurada.'
    base, token = config
    url = base + '/whatsapp/' + quote(str(site_id), safe='')
    if acao:
        url += '/' + acao
    try:
        resposta = http().request('POST' if acao else 'GET', url,
            json=payload if acao else None,
            headers={'Authorization': 'Bearer ' + token}, timeout=30.0)
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return None, 'A mensageria não respondeu. Consulte o estado antes de repetir um envio.'
    if resposta.status_code != 200 or not isinstance(dados, dict):
        return None, 'A operação foi recusada ou não pôde ser concluída. Confira a conexão e tente consultar novamente.'
    return dados, ''


@require_http_methods(['GET', 'POST'])
def whatsapp(request):
    site = CatalogoClient().site_por_host(request.get_host().split(':')[0].lower())
    contexto = {'admin': request.admin, 'referencia': str(uuid.uuid4())}
    if not site:
        contexto['erro'] = 'Não consegui identificar este site. A conexão não foi alterada.'
        return render(request, 'admin/whatsapp.html', contexto)
    site_id = site['id']
    contexto['site'] = site
    if request.method == 'POST':
        acao = request.POST.get('acao', '')
        payload = None
        if acao == 'config':
            payload = {'instancia': request.POST.get('instancia', '').strip(),
                'transporte': 'WHATSAPP-BAILEYS', 'ativo': request.POST.get('ativo') == 'sim'}
        elif acao == 'connect':
            payload = {'renovar': request.POST.get('renovar') == 'sim'}
        elif acao == 'send':
            if request.POST.get('autorizado') != 'sim':
                contexto['erro'] = 'Confirme que este destinatário autorizou a mensagem de teste.'
            elif not request.POST.get('referencia'):
                contexto['erro'] = 'Reabra a tela para preparar o teste.'
            else:
                payload = {'destinatario': request.POST.get('destinatario', '').strip(),
                    'corpo': request.POST.get('corpo', '').strip(),
                    'referencia': request.POST['referencia']}
                contexto['referencia'] = request.POST['referencia']
        if payload is not None:
            resultado, erro = _pedir(site_id, acao, payload)
            contexto['erro'] = erro
            if resultado is not None:
                if acao == 'connect':
                    contexto['pareamento'] = resultado
                    contexto['erro'] = resultado.get('erro') or erro
                    qr = resultado.get('qr') or ''
                    if qr.startswith('data:image/png;base64,'):
                        contexto['qr'] = qr
                contexto['resultado'] = ('Configuração salva.' if acao == 'config' else
                    'Conexão consultada. Siga as instruções abaixo.' if acao == 'connect' else
                    ESTADOS.get(resultado.get('status'), 'Pedido registrado. Consulte o estado abaixo.'))
            if acao == 'connect' and request.headers.get('Accept') == 'application/json':
                resultado = resultado or {}
                estado = resultado.get('estado', '')
                resposta = JsonResponse({'qr': contexto.get('qr', ''), 'estado': estado,
                    'estado_visivel': CONEXOES.get(estado, estado or 'Não foi possível consultar'),
                    'erro': contexto.get('erro') or '',
                    'numero_mascarado': resultado.get('numero_mascarado') or ''})
                resposta['Cache-Control'] = 'no-store'
                return resposta
    dados, erro = _pedir(site_id)
    if dados is None:
        contexto['erro'] = contexto.get('erro') or erro
    else:
        contexto.update(dados)
        conexao = contexto.get('conexao') or {}
        contexto['estado_visivel'] = CONEXOES.get(conexao.get('estado'), conexao.get('estado'))
        for mensagem in contexto.get('mensagens', []):
            mensagem['status_visivel'] = ESTADOS.get(mensagem.get('status'), mensagem.get('status', ''))
    resposta = render(request, 'admin/whatsapp.html', contexto)
    scripts = ''.join(" 'sha256-" + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode() + "'"
        for m in re.finditer(rb'<script>(.*?)</script>', resposta.content, re.DOTALL))
    resposta['Content-Security-Policy'] = (
        f"default-src 'self'; script-src 'self'{scripts}; "
        f"style-src 'self'{PortaAdministrativa.hashes_de_estilo(resposta)}; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'")
    resposta['Cache-Control'] = 'no-store'
    return resposta
