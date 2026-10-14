import re
from datetime import timedelta
from django.db.models import Sum, Q
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import RotinaProcedimentos, AgrupamentoProcedimento, Consumo


@require_http_methods(['GET', 'POST'])
def painel(request):
    if not getattr(request, 'admin', None) or request.admin.get('equipe_apenas'):
        return HttpResponseForbidden('Somente a administração revisa os rascunhos e as evidências privadas.')
    rotina, _ = RotinaProcedimentos.objects.get_or_create(host='meshcraft.top')
    erro = ''
    if request.method == 'POST':
        if request.POST.get('acao') == 'idiomas':
            idiomas = [request.POST.get('idioma'+str(i), '').strip() for i in range(1, 4)]
            preenchidos = [i for i in idiomas if i]
            if len(preenchidos) not in (0, 3) or len({i.lower() for i in preenchidos}) != len(preenchidos) or any(
                not re.fullmatch(r'[\w À-ÿ()\-]{2,40}', i) for i in preenchidos):
                erro = 'Preencha os três idiomas diferentes ou deixe os três vazios.'
            else:
                rotina.idiomas = preenchidos
                rotina.save(update_fields=['idiomas'])
                return HttpResponseRedirect(reverse('procedimentos_painel'))
        elif request.POST.get('acao') == 'editar':
            from .procedimentos_texto import limpar
            grupo = AgrupamentoProcedimento.objects.filter(rotina=rotina, pk=request.POST.get('grupo', '')).first()
            if grupo:
                grupo.rascunho = limpar(request.POST.get('rascunho', ''))
                grupo.revisao += 1
                grupo.save(update_fields=['rascunho', 'revisao', 'atualizada_em'])
                return HttpResponseRedirect(reverse('procedimentos_painel')+'#grupo-'+str(grupo.pk))
            erro = 'Agrupamento não encontrado.'
        else:
            erro = 'Ação não disponível.'
    inicio = timezone.now()-timedelta(days=14)
    grupos = []
    for g in AgrupamentoProcedimento.objects.filter(rotina=rotina).order_by('-elegivel', '-atualizada_em'):
        casos = list(g.casos.filter(ativa=True, ocorrida_em__gte=inicio).order_by('-ocorrida_em'))
        if not casos and not g.rascunho:
            continue
        redacoes = list(g.redacoes.select_related('execucao').order_by('-pk'))
        custos = Consumo.objects.filter(execucao__redacaoprocedimento__grupo=g).aggregate(
            calculado=Sum('custo_estimado_usd', filter=Q(desconhecido=False)),
            reserva=Sum('custo_estimado_usd', filter=Q(desconhecido=True)))
        g.casos_tela, g.redacoes_tela, g.custos = casos, redacoes, custos
        g.contagem_atual = len({c.independente for c in casos})
        g.tem_solucao = any(c.confirmada and c.solucao for c in casos)
        grupos.append(g)
    consumos = Consumo.objects.filter(origem='procedimentos')
    totais = consumos.aggregate(calculado=Sum('custo_estimado_usd', filter=Q(desconhecido=False)),
                               reserva=Sum('custo_estimado_usd', filter=Q(desconhecido=True)))
    from . import modelo
    autorizacao = modelo.autorizacao_ativa()
    resposta = render(request, 'admin/procedimentos.html', {'admin': request.admin, 'rotina': rotina,
        'grupos': grupos, 'erro': erro, 'totais': totais, 'chamadas': consumos.count(),
        'teto': autorizacao.teto_mensal_usd if autorizacao else None,
        'gasto_compartilhado': modelo.gasto_do_mes(autorizacao.pk) if autorizacao else None,
        'idioma1': (rotina.idiomas+['','',''])[0], 'idioma2': (rotina.idiomas+['','',''])[1],
        'idioma3': (rotina.idiomas+['','',''])[2]})
    resposta['Cache-Control'] = 'private, no-store'
    return resposta
