"""Operação administrativa. Consulta canais existentes; nenhum envio ou publicação."""
import uuid
import re
from collections import defaultdict
from datetime import timedelta
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods
from apps.core.clients import MensageriaClient
from apps.core.crm_conversas import ConversasClient, OK
from . import escala, service
from .models import Conversa, Configuracao, Conhecimento, AgendaDoProduto


def vincular(sid, origem_id, dados=None):
    """Referência à conversa original, sem copiar histórico nem criar identidade de aluno."""
    origem_id = str(uuid.UUID(str(origem_id)))
    estado, dados = (OK, dados) if dados else ConversasClient().mensagens(sid, origem_id)
    if estado != OK or not dados:
        raise ValueError('A caixa não respondeu. Nenhum atendimento foi criado.')
    origem = dados['conversa']
    if origem.get('site_id') != sid or origem.get('id') != origem_id or origem.get('canal') not in ('whatsapp', 'email'):
        raise ValueError('Conversa fora deste site ou canal indisponível.')
    entradas = [m for m in dados['mensagens'] if m.get('direcao') == 'entrada' and not m.get('descadastro')]
    if not entradas:
        raise ValueError('Esta conversa ainda não tem um pedido recebido.')
    service.config(sid)
    cid = uuid.uuid5(uuid.NAMESPACE_URL, 'suporte-canal:' + sid + ':' + origem_id)
    with transaction.atomic():
        c, nova = Conversa.objects.get_or_create(pk=cid, defaults={
            'site_id': sid, 'pessoa_id': 'canal-' + origem_id,
            'nome': origem.get('endereco_mascarado') or 'Contato do canal',
            'assunto': service.assunto_da_mensagem(sid, entradas[-1].get('texto') or ''),
            'canal': origem['canal'], 'origem_conversa': origem_id,
            'origem_lead': origem.get('lead_id') or '',
            'estado': 'aguardando', 'processar': False,
        })
        c=Conversa.objects.select_for_update().get(pk=c.pk)
        mensagem_id=str(entradas[-1].get('id') or '')[:100]
        if nova or (mensagem_id and c.origem_ultima_mensagem != mensagem_id):
            if not nova:
                escala.reabrir(c,'nova entrada no canal','mensageria')
            c.origem_ultima_mensagem=mensagem_id
            c.arquivada_em=None
            escala.classificar(c, entradas[-1].get('texto') or '')
            c.processar=False
            c.save()
    return c


def receber_canais(sid):
    """Encaminha entradas novas de suporte. Não assume nem responde no canal comercial."""
    conf = Configuracao.objects.filter(site_id=sid).first()
    if not conf:
        return
    if not conf.canais_entrada_em:
        Configuracao.objects.filter(pk=conf.pk,canais_entrada_em__isnull=True).update(canais_entrada_em=timezone.now())
        return
    for pagina in range(1, 11):
        estado, dados = ConversasClient().listar(sid, ligacao='todas', pagina=pagina, por_pagina=100)
        if estado != OK or not dados:
            return
        for item in dados['itens']:
            em = parse_datetime(item.get('ultima_entrada_em') or '')
            if (not em or not timezone.is_aware(em) or em < conf.canais_entrada_em
                    or em > timezone.now() or item.get('site_id') != sid
                    or item.get('descadastrado')):
                continue
            situacao, original = ConversasClient().mensagens(sid,item['id'])
            if situacao != OK or not original:
                continue
            m = next((m for m in reversed(original['mensagens']) if m.get('direcao') == 'entrada'),{})
            if m.get('descadastro'): continue
            texto = m.get('texto') or ''
            if Conversa.objects.filter(site_id=sid,origem_conversa=item['id']).exists():
                vincular(sid,item['id'],original)
                continue
            if not re.search(r'\b(como|onde|cade|nao|sem|erro|falha|travando|esqueci|ajuda|duvida)\b', escala.normalizar(texto)):
                continue
            candidato = Conversa(site_id=sid)
            escala.classificar(candidato, texto)
            # Demandas de conta, aula, acesso, prática e falha do site são suporte.
            # Compras, cumprimentos e dúvidas sem contexto continuam na triagem dos canais.
            if candidato.tipo not in (2, 3, 4, 8, 9, 10, 12):
                continue
            try:
                vincular(sid, item['id'], original)
            except (ValueError, KeyError, TypeError):
                continue
        if not dados.get('tem_mais'):
            return


def origem_atual(c):
    if not c.origem_conversa:
        return None
    estado, dados = ConversasClient().mensagens(c.site_id, c.origem_conversa)
    if estado != OK or not dados or dados['conversa'].get('site_id') != c.site_id:
        return {'erro': 'Histórico do canal indisponível agora. A referência foi preservada.'}
    lead = dados['conversa'].get('lead_id') if dados['conversa'].get('ligacao') == 'ligada' else ''
    if c.origem_lead != (lead or ''):
        Conversa.objects.filter(pk=c.pk).update(origem_lead=lead or '')
        c.origem_lead=lead or ''
    return dados


def piloto(c):
    """Avalia o escopo planejado sem ligar autonomia, mudar modos ou gerar mensagens."""
    agenda = AgendaDoProduto.objects.filter(site_id=c.site_id,
        produto_id=(c.interesse or {}).get('produto_id'), inicio__isnull=False).first()
    elegivel = (c.canal == 'site' and c.tipo in (1, 16) and c.cor == 'verde'
        and c.degrau != 'cobrar' and not c.atendente_id and not c.solicitou_pessoa
        and (c.tipo == 16 or bool(agenda)))
    return {'elegivel': bool(elegivel), 'ativo': False,
        'motivo': 'Dentro do escopo planejado; envio continua assistido.' if elegivel
            else 'Fora do escopo ou sem fonte confirmada; revisão individual.'}


def prevencao(sid):
    grupos = defaultdict(list)
    agora = timezone.now()
    for c in Conversa.objects.filter(site_id=sid, canal='site', criada_em__gte=agora-timedelta(days=14)).order_by('-criada_em')[:1000]:
        grupos[(c.tipo, c.curso)].append(c)
    return [{'tipo': escala.TIPOS.get(tipo, escala.TIPOS[0]), 'total': len(itens),
        'curso': curso, 'conversa': itens[0],
        'concentrado': sum(c.criada_em >= agora-timedelta(minutes=15) for c in itens) >= 10,
        'base': Conhecimento.objects.filter(site_id=sid, assunto=itens[0].assunto, curso=curso)[:5]}
        for (tipo, curso), itens in sorted(grupos.items(), key=lambda par: -len(par[1]))]


@require_http_methods(['GET', 'POST'])
def painel(request):
    from .views import admin, site, contexto, prefixo
    admin(request); sid = site(request); ctx = contexto(request, sid)
    if request.method == 'POST':
        try:
            if request.POST.get('acao') != 'vincular':
                raise ValueError('Escolha uma conversa recebida para encaminhar ao suporte.')
            c = vincular(sid, request.POST.get('origem'))
            return HttpResponseRedirect(prefixo(request) + '/' + str(c.pk) + '/')
        except (ValueError, TypeError, KeyError):
            ctx['erro'] = 'Não foi possível encaminhar. Confira o canal e se existe um pedido recebido.'
    estado, dados = ConversasClient().listar(sid, ligacao='todas', pagina=max(1, min(100, _pagina(request))), por_pagina=50)
    ctx.update(canais=(dados or {}).get('itens', []), canais_erro=estado != OK,
        tem_mais=(dados or {}).get('tem_mais'), pagina=_pagina(request),
        prontidao=MensageriaClient().prontidao_comercial(sid),
        entrada_em=ctx['config'].canais_entrada_em,
        externos=Conversa.objects.filter(site_id=sid).exclude(canal='site'),
        proximos=Conversa.objects.filter(site_id=sid, arquivada_em__isnull=True).exclude(proximo_passo='').exclude(estado='encerrado').order_by('passo_prazo')[:100],
        prevencao=prevencao(sid), agora=timezone.now())
    return render(request, 'admin/atendimento_operacao.html', ctx, status=422 if ctx.get('erro') else 200)


def _pagina(request):
    try: return max(1, min(100, int(request.GET.get('pagina', '1'))))
    except ValueError: return 1
