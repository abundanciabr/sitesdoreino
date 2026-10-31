"""Busca de páginas: resultados próprios e sugestões para a barra do admin."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import mapa_do_site
from .moldura import secoes_do_menu


def _endereco_seguro(endereco):
    if not isinstance(endereco, str) or not endereco.startswith('/'):
        return False
    if endereco.startswith('//') or any(c in endereco for c in ('\\', '<', '>', '\r', '\n')):
        return False
    partes = urlsplit(endereco)
    return not partes.netloc and not partes.scheme


def paginas():
    """Só páginas navegáveis; operações, APIs e moldes não são resultados."""
    caminho = mapa_do_site.arquivo_do_mapa()
    if caminho is None:
        raise OSError('Índice de páginas indisponível')
    entradas = json.loads(caminho.read_text(encoding='utf-8'))['enderecos']
    por_endereco = {}
    for entrada in entradas:
        if (entrada.get('gesto') or entrada.get('para_quem') == 'maquina'
                or entrada.get('alcance') != 'publico'):
            continue
        item = mapa_do_site._preparar(entrada)
        endereco = item['link']
        if not _endereco_seguro(endereco):
            continue
        por_endereco.setdefault(endereco, {
            'titulo': item['titulo'], 'descricao': item['descricao'],
            'endereco': endereco, 'termos': item['observacao'] or '',
        })
    # Os nomes do menu também encontram as páginas (CRM, Escola, Placar...).
    for secao in secoes_do_menu(''):
        endereco = secao['href']
        if not _endereco_seguro(endereco):
            continue
        existente = por_endereco.get(endereco)
        if existente:
            existente['termos'] += ' ' + existente['titulo']
            existente['titulo'] = secao['rotulo']
        else:
            por_endereco[endereco] = {
                'titulo': secao['rotulo'], 'descricao': 'Abrir ' + secao['rotulo'] + '.',
                'endereco': endereco, 'termos': '',
            }
    return list(por_endereco.values())


def pesquisar(consulta):
    consulta = mapa_do_site._sem_acento(consulta.strip())
    if not consulta:
        return []
    palavras = consulta.split()
    encontrados = []
    for pagina in paginas():
        titulo = mapa_do_site._sem_acento(pagina['titulo'])
        endereco = mapa_do_site._sem_acento(pagina['endereco'])
        texto = ' '.join((titulo, endereco, mapa_do_site._sem_acento(pagina['descricao']),
                         mapa_do_site._sem_acento(pagina['termos'])))
        if not all(palavra in texto for palavra in palavras):
            continue
        peso = (100 if consulta == titulo else 0) + (80 if consulta == endereco else 0)
        peso += 40 if titulo.startswith(consulta) else 0
        peso += 25 if consulta in titulo else 0
        peso += sum(5 for palavra in palavras if palavra in titulo)
        encontrados.append((peso, pagina))
    encontrados.sort(key=lambda item: (-item[0], item[1]['titulo'].casefold(), item[1]['endereco']))
    return [{chave: pagina[chave] for chave in ('titulo', 'descricao', 'endereco')}
            for _, pagina in encontrados]


def _consulta(request):
    return request.GET.get('q', '').strip()[:200]


@require_GET
def busca_paginas(request):
    consulta = _consulta(request)
    try:
        resultados = pesquisar(consulta)
    except (OSError, ValueError, KeyError, TypeError):
        return render(request, 'admin/busca_paginas.html', {
            'admin': request.admin, 'busca_consulta': consulta, 'busca_indisponivel': True,
        }, status=503)
    pagina = Paginator(resultados, 20).get_page(request.GET.get('pagina'))
    return render(request, 'admin/busca_paginas.html', {
        'admin': request.admin, 'busca_consulta': consulta,
        'resultados': pagina, 'total_resultados': len(resultados),
    })


@require_GET
def busca_sugestoes(request):
    consulta = _consulta(request)
    try:
        resultados = pesquisar(consulta)
    except (OSError, ValueError, KeyError, TypeError):
        return JsonResponse({'erro': 'Não foi possível carregar as sugestões.'}, status=503)
    return JsonResponse({'consulta': consulta, 'total': len(resultados), 'resultados': resultados[:7]})


@require_GET
def busca_script(request):
    caminho = Path(__file__).with_name('busca_paginas.js')
    return HttpResponse(caminho.read_text(encoding='utf-8'), content_type='text/javascript; charset=utf-8')
