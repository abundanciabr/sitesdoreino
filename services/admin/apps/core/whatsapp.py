"""Operação do WhatsApp pelo painel autenticado, sempre no site do host."""
import uuid
from urllib.parse import quote

import httpx
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .clients import CatalogoClient, MensageriaClient, http


ESTADOS = {
    'pendente': 'Aguardando envio', 'enviando': 'Enviando',
    'aceito': 'Aceita pelo provedor — entrega ainda não confirmada',
    'enviado': 'Enviada — entrega ainda não confirmada',
    'entregue': 'Entrega confirmada', 'lido': 'Leitura confirmada',
    'falhou': 'Falhou', 'desconhecido': 'Resultado desconhecido — não reenviar às cegas',
}


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
            payload = {}
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
                    qr = resultado.get('qr') or ''
                    if qr.startswith('data:image/png;base64,'):
                        contexto['qr'] = qr
                contexto['resultado'] = ('Configuração salva.' if acao == 'config' else
                    'Conexão consultada. Siga as instruções abaixo.' if acao == 'connect' else
                    ESTADOS.get(resultado.get('status'), 'Pedido registrado. Consulte o estado abaixo.'))
    dados, erro = _pedir(site_id)
    if dados is None:
        contexto['erro'] = contexto.get('erro') or erro
    else:
        contexto.update(dados)
        for mensagem in contexto.get('mensagens', []):
            mensagem['status_visivel'] = ESTADOS.get(mensagem.get('status'), mensagem.get('status', ''))
    resposta = render(request, 'admin/whatsapp.html', contexto)
    resposta['Cache-Control'] = 'no-store'
    return resposta
