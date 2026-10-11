"""Revisão explícita de grupos: o POST envia exatamente o texto conferido."""
import hashlib
import json
from collections import defaultdict

from django.core import signing
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from . import escala, textos_fixos
from .models import Conversa, Mensagem


def impressao(c, texto):
    mensagens = list(c.mensagens.values_list('pk', flat=True))
    return hashlib.sha256(json.dumps([str(c.pk), c.rodada, c.estado, c.atendente_id,
        c.tipo, c.cor, c.curso, c.interesse, mensagens[-1:] or [], texto],
        sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def candidato(c, quem):
    if c.estado == 'encerrado' or c.assunto.modo != 'assistido' or c.cor == 'vermelho':
        return None
    if c.atendente_id and c.atendente_id != quem:
        return None
    ultima = c.mensagens.filter(autor='aluno').last()
    if not ultima or c.mensagens.filter(pk__gt=ultima.pk, autor__in=['equipe','robo']).exclude(referencia__startswith='recepcao-').exists():
        return None
    fixo = textos_fixos.preparar(c)
    if not fixo.get('lote') or not fixo.get('resposta'):
        return None
    return fixo, ultima


def consulta_aberta(sid):
    return Conversa.objects.filter(site_id=sid).exclude(estado='encerrado').filter(assunto__modo='assistido')


def grupos(sid, quem, pagina=1):
    encontrados = defaultdict(list)
    consulta = consulta_aberta(sid).select_related('assunto').prefetch_related('mensagens').order_by('criada_em','pk')[(pagina-1)*200:pagina*200]
    for c in consulta:
        preparado = candidato(c, quem)
        if not preparado:
            continue
        fixo, ultima = preparado
        chave = json.dumps([c.tipo, c.curso, fixo.get('produto_id'), escala.normalizar(ultima.texto),
            fixo['modelo'], fixo['fontes']], sort_keys=True, ensure_ascii=False)
        encontrados[chave].append((c, fixo))
    resultado = []
    for itens in encontrados.values():
        # Lotes limitados ao conjunto mostrado, sem incluir chegadas posteriores.
        for inicio in range(0, len(itens), 30):
            parte = itens[inicio:inicio+30]
            c, fixo = parte[0]
            linhas = [{'id': str(x.pk), 'hash': impressao(x, f)} for x, f in parte]
            token = signing.dumps({'site': sid, 'quem': quem, 'itens': linhas}, salt='suporte-lote', compress=True)
            resultado.append({'tipo': escala.TIPOS[c.tipo], 'produto': c.interesse.get('nome') or c.curso,
                'texto': fixo['modelo'], 'conversas': [x for x, _ in parte], 'token': token,
                'destinatarios': [{'conversa': x, 'texto': f['resposta']} for x, f in parte],
                'tempo_token': escala.token_tempo(quem, sid, hashlib.sha256(token.encode()).hexdigest())})
    return resultado


def aprovar(sid, quem, nome, token, tempo_token):
    try:
        dados = signing.loads(token, salt='suporte-lote', max_age=1200)
        itens = dados['itens']
        if dados['site'] != sid or dados['quem'] != quem or not 1 <= len(itens) <= 30:
            raise ValueError
        ids = [i['id'] for i in itens]
        if len(set(ids)) != len(ids):
            raise ValueError
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValueError('A revisão expirou. Abra novamente a caixa para conferir os textos.') from None
    referencia = 'lote-' + hashlib.sha256(token.encode()).hexdigest()
    with transaction.atomic():
        conversas = list(Conversa.objects.select_for_update().filter(site_id=sid, pk__in=ids).select_related('assunto').order_by('pk'))
        if len(conversas) != len(itens):
            raise ValueError('O grupo mudou. Confira novamente antes de enviar.')
        ja = Mensagem.objects.filter(conversa__in=conversas, referencia=referencia).count()
        if ja == len(itens):
            return 0
        if ja:
            raise ValueError('O grupo mudou. Confira novamente antes de enviar.')
        esperados = {i['id']: i['hash'] for i in itens}
        preparados = []
        for c in conversas:
            candidato_atual = candidato(c, quem)
            if not candidato_atual or impressao(c, candidato_atual[0]) != esperados[str(c.pk)]:
                raise ValueError('Chegou uma mensagem ou os dados do grupo mudaram. Revise novamente; nada foi enviado.')
            preparados.append((c, candidato_atual[0]))
        tempo = escala.tempo_decorrido(tempo_token, quem, sid, hashlib.sha256(token.encode()).hexdigest())
        for c, fixo in preparados:
            mensagem = Mensagem.objects.create(conversa=c, referencia=referencia, autor='equipe', nome=nome[:160],
                texto=fixo['resposta'], fontes=fixo['fontes'], tipo=c.tipo, rodada=c.rodada,
                tempo_humano_seg=tempo/len(itens) if tempo is not None else None)
            c.atendente_id, c.atendente_nome = quem, nome[:160]
            c.estado, c.processar, c.sugestao = 'andamento', False, {}
            c.primeira_resposta_em = c.primeira_resposta_em or mensagem.criada_em
            c.resolvida_em, c.resolucao = None, ''
            c.save()
    return len(itens)


@require_http_methods(['GET', 'POST'])
def caixa(request):
    from .views import admin, site, contexto, prefixo
    from .gestao import identidade_atendente
    admin(request)
    sid = site(request)
    quem, nome = identidade_atendente(request)
    ctx = contexto(request, sid)
    status = 200
    if request.method == 'POST':
        try:
            total = aprovar(sid, quem, nome, request.POST.get('lote', ''), request.POST.get('tempo_token', ''))
            return HttpResponseRedirect(prefixo(request) + '/decisoes/?enviados=' + str(total))
        except ValueError as ex:
            ctx['erro'] = str(ex)
            status = 409
    pagina = Paginator(consulta_aberta(sid).order_by('criada_em','pk'), 200).get_page(request.GET.get('pagina'))
    ctx.update(grupos=grupos(sid, quem, pagina.number), pagina_obj=pagina, enviados=request.GET.get('enviados'))
    return render(request, 'admin/atendimento_decisoes.html', ctx, status=status)
