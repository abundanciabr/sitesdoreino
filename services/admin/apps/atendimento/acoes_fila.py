"""Arquivamento reversível e exclusão confirmada do pedido de suporte."""
import uuid
from django.core import signing
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from .models import Conversa, Mensagem, Reabertura, ConsumoDoAtendimento, Aviso, PreviaForum, HistoricoDoPasso


def executar(request, sid):
    from .views import contexto, prefixo, resposta
    try:
        cid = uuid.UUID(request.POST.get('conversa', ''))
    except ValueError:
        raise Http404
    acao = request.POST.get('acao')
    destino = prefixo(request) + '/'
    with transaction.atomic():
        c = get_object_or_404(Conversa.objects.select_for_update(), pk=cid, site_id=sid)
        if acao == 'arquivar':
            if c.arquivada_em is None:
                c.arquivada_em = timezone.now()
                c.save(update_fields=['arquivada_em'])
            return HttpResponseRedirect(destino + '?arquivada=' + str(c.pk))
        if acao == 'desarquivar':
            c.arquivada_em = None
            c.save(update_fields=['arquivada_em'])
            return HttpResponseRedirect(destino + '?selecionada=' + str(c.pk))
        if acao not in ('apagar', 'confirmar_apagar', 'apagar_definitivamente'):
            return resposta({'erro': 'Ação desconhecida.'}, 400)
        # As duas confirmações são vinculadas ao pedido, ao administrador e ao
        # conteúdo visto. Uma mensagem nova exige conferir novamente o pedido.
        vinculo = {'conversa': str(c.pk), 'site': sid, 'admin': str(request.admin['id']),
                   'atualizada': c.atualizada_em.isoformat(),
                   'mensagem': c.mensagens.order_by('-pk').values_list('pk', flat=True).first()}
        if acao != 'apagar':
            try:
                recebido = signing.loads(request.POST.get('confirmacao', ''), salt='suporte-apagar', max_age=600)
                etapa = 1 if acao == 'confirmar_apagar' else 2
                if recebido != dict(vinculo, etapa=etapa):
                    raise signing.BadSignature()
            except signing.BadSignature:
                return resposta({'erro': 'A confirmação expirou ou o pedido mudou. Volte à fila e confirme novamente.'}, 409)
        if acao == 'apagar_definitivamente':
            if c.trabalhando_ate and c.trabalhando_ate > timezone.now():
                return resposta({'erro': 'O suporte está processando este pedido. Aguarde terminar e tente novamente.'}, 409)
            for model in (Aviso, PreviaForum, Reabertura, ConsumoDoAtendimento, Mensagem, HistoricoDoPasso):
                model.objects.filter(conversa=c).delete()
            c.delete()
            return HttpResponseRedirect(destino + '?apagada=1')
        etapa = 1 if acao == 'apagar' else 2
        ctx = contexto(request, sid)
        ctx.update(conversa=c, etapa=etapa,
                   confirmacao=signing.dumps(dict(vinculo, etapa=etapa), salt='suporte-apagar'))
        return render(request, 'admin/atendimento_apagar.html', ctx)
