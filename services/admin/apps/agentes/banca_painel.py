"""Banca dentro da página de vendas administrativa já existente."""
import json
import uuid
from urllib.parse import urlencode
from django.db.models import Sum
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from apps.core.clients import CatalogoClient
from apps.core.models import RascunhoDeConfiguracao
from . import banca, banca_fontes
from .models import Execucao


def painel(request, site):
    site_id = str(site['id'])
    erro, recado = '', ''
    cliente = CatalogoClient()
    if request.method == 'POST':
        try:
            acao = request.POST.get('acao')
            if acao == 'coletar':
                corpus = banca_fontes.coletar(site_id)
                recado = f"Coleta guardada: {len(corpus.conteudo['itens'])} objeções ou perguntas distintas."
            elif acao == 'evidencia':
                if request.POST.get('real') != 'sim':
                    raise ValueError('Confirme que o trecho veio de uma pessoa real, e não de uma simulação.')
                banca_fontes.registrar(site_id, request.POST.get('fonte', ''), request.POST.get('texto', ''),
                    request.POST.get('referencia', ''), request.POST.get('data', '')[:40], request.POST.get('produto', ''))
                banca_fontes.coletar(site_id)
                recado = 'Relato minimizado guardado e coleta atualizada. As rodadas antigas mantêm suas evidências.'
            elif acao == 'perfil':
                codigo = request.POST.get('perfil', '')
                texto = request.POST.get('texto', '').strip()
                if codigo not in banca.PERFIS or not 40 <= len(texto) <= 6000:
                    raise ValueError('Escolha um perfil e escreva entre 40 e 6.000 caracteres.')
                atual = banca.perfil_atual(site_id, codigo)
                if request.POST.get('base_digest') != atual['digest']:
                    raise ValueError('O perfil mudou durante sua edição. Reabra antes de salvar.')
                revisao = {'texto': texto, 'revisada_por_livia': request.POST.get('revisada') == 'sim',
                           'por': request.admin.get('nome', 'Administração'), 'em': timezone.now().isoformat(),
                           'base_digest': atual['digest']}
                RascunhoDeConfiguracao.objects.create(tipo='banca_perfil', site_id=site_id,
                        alvo=codigo + ':' + str(uuid.uuid4()), conteudo=revisao)
                recado = 'Nova revisão guardada. Rodadas anteriores conservam o perfil anterior.'
            elif acao == 'atacar':
                trabalho = banca.pedir(site_id, request.POST.get('slug', ''), request.POST.get('origem', 'publicada'),
                    request.POST.get('experimento_id', ''), request.POST.get('variante', ''),
                    request.POST.get('chave', '')[:100] or str(uuid.uuid4()),
                    request.admin.get('nome', 'Administração'), modo_teste=request.POST.get('modo_teste') == 'sim')
                return HttpResponseRedirect(request.path + '?' + urlencode({'banca': '1', 'rodada': trabalho.pk}))
            elif acao == 'exigir':
                estado, resposta = cliente._falar('POST', f'/sites/{site_id}/banca/exigir')
                if estado != cliente.OK:
                    raise ValueError('Não foi possível confirmar a exigência no catálogo.')
                recado = 'Novas ativações de experimentos exigem a rodada completa do conteúdo exato. Testes ativos preservados.'
            elif acao == 'hipotese':
                trabalho = get_object_or_404(Execucao, pk=request.POST.get('rodada'), tipo=Execucao.Tipo.BANCA,
                                             estado__site_id=site_id)
                indice = int(request.POST.get('indice', '-1'))
                conserto = trabalho.estado['resultados']['sintese']['consertos'][indice]
                if indice < 0:
                    raise ValueError('Hipótese inválida.')
                registro, _ = RascunhoDeConfiguracao.objects.get_or_create(tipo='banca_hipotese', site_id=site_id,
                    alvo=f'{trabalho.pk}:{indice}', defaults={'conteudo': conserto,
                        'base': {'rodada': trabalho.pk, 'slug': trabalho.estado['fotografia']['conteudo']['slug'],
                                 'assinatura': trabalho.estado['fotografia']['assinatura']}})
                recado = 'Hipótese guardada para experimentação. Não iniciou tráfego nem alterou a página.'
            else:
                raise ValueError('Ação inválida.')
        except (ValueError, KeyError, IndexError, TypeError) as problema:
            erro = str(problema)
    estado, paginas = cliente._falar('GET', f'/sites/{site_id}/paginas-banca', forma=list)
    if estado != cliente.OK:
        paginas = []
        erro = erro or 'Não foi possível consultar as páginas do catálogo.'
    experimentos, outros_bracos = [], set()
    for pagina in paginas[:30]:
        situacao, lista = cliente.experimentos_da_pagina(site_id, pagina['slug'])
        if situacao == cliente.OK:
            for exp in lista:
                experimentos.append({**exp, 'slug': pagina['slug']})
                for v in exp.get('variantes', []):
                    if v['variante_id'] not in {'a', 'b'}:
                        outros_bracos.add(v['variante_id'])
    trabalho, comparacao, anterior = None, None, None
    if request.GET.get('rodada'):
        trabalho = get_object_or_404(Execucao, pk=request.GET['rodada'], tipo=Execucao.Tipo.BANCA, estado__site_id=site_id)
        if request.GET.get('comparar'):
            anterior = get_object_or_404(Execucao, pk=request.GET['comparar'], tipo=Execucao.Tipo.BANCA, estado__site_id=site_id)
            if anterior.estado['fotografia']['conteudo']['page_id'] != trabalho.estado['fotografia']['conteudo']['page_id']:
                erro = 'Escolha duas rodadas da mesma página.'
            else:
                comparacao = banca.comparar(anterior.estado, trabalho.estado)
    perfis = [banca.perfil_atual(site_id, codigo) for codigo in banca.PERFIS]
    for perfil in perfis:
        perfil['repositorio'] = 'https://github.com/abundanciabr/sitesdoreino/edit/main/services/admin/apps/agentes/banca_perfis/' + perfil['codigo'] + '.md'
    if request.GET.get('exportar') == 'perfis':
        conteudo = '\n\n'.join(f"# {p['codigo']}\n{p['texto']}" for p in perfis)
        resposta = HttpResponse(conteudo, content_type='text/plain; charset=utf-8')
        resposta['Content-Disposition'] = 'attachment; filename="banca-perfis.txt"'
    else:
        historico = list(Execucao.objects.filter(tipo=Execucao.Tipo.BANCA, estado__site_id=site_id).order_by('-pk')[:50])
        for rodada in historico:
            rodada.custo = rodada.consumos.aggregate(total=Sum('custo_estimado_usd'))['total'] or 0
        corpus = banca_fontes.ultimo(site_id)
        resposta = render(request, 'admin/banca.html', {'admin': request.admin, 'erro': erro, 'recado': recado,
            'paginas': paginas, 'experimentos': experimentos, 'outros_bracos': sorted(outros_bracos),
            'perfis': perfis, 'corpus': corpus.conteudo if corpus else None,
            'trabalho': trabalho, 'historico': historico, 'comparacao': comparacao,
            'anterior': anterior, 'chave': str(uuid.uuid4()),
            'resultados': [{'codigo': c, 'nome': banca.PERFIS[c], 'leitura': trabalho.estado['resultados'].get(c)}
                           for c in banca.PERFIS] if trabalho else [],
            'sintese': trabalho.estado.get('resultados', {}).get('sintese') if trabalho else None,
            'hipoteses': RascunhoDeConfiguracao.objects.filter(tipo='banca_hipotese', site_id=site_id).order_by('-pk')[:30]},
            status=400 if erro else 200)
    resposta['Cache-Control'] = 'private, no-store'
    return resposta
