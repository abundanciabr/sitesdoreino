"""Comprovação privada e somente de leitura da limpeza solicitada."""
import hashlib

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.gamificacao.models import (
    AnexoDaJornada, BackupDoReinicioDasFaixas, FaixaDoAluno, HistoricoDaFaixa,
    JornadaPessoal, LancamentoDeXP, RecebimentoDeclarado, RegistroDaJornada,
)
from .acesso import e_admin
from .sessao import quem_e, site_atual


@never_cache
@require_GET
def relatorio_reinicio(request):
    site, pessoa = site_atual(), quem_e(request)
    if not site or not pessoa or not e_admin(request, pessoa):
        return JsonResponse({'erro': 'Acesso restrito ao administrador.'}, status=403)
    copia = BackupDoReinicioDasFaixas.objects.filter(
        site_id=site, chave='reinicio-autorizado-20261011', aplicado_em__isnull=False,
    ).first()
    if not copia:
        return JsonResponse({'aplicado': False}, status=409)
    atuais = {
        'jornadas_com_requisitos': JornadaPessoal.objects.filter(site_id=site).exclude(
            inicio={}, declaracoes={}, confirmacoes_sequenciais={}, meta_cents=None,
            proposito='', celebracao_pendente={},
        ).count(),
        'arquivos_das_faixas': AnexoDaJornada.objects.filter(site_id=site).count(),
        'historicos_das_faixas': HistoricoDaFaixa.objects.filter(site_id=site).count(),
        'historicos_da_jornada': RegistroDaJornada.objects.filter(site_id=site).count(),
        'registros_de_faixas_superiores': FaixaDoAluno.objects.filter(site_id=site, ordem__gt=1).count(),
        'recebimentos_na_progressao': RecebimentoDeclarado.objects.filter(site_id=site, fora_da_progressao=False).count(),
        'lancamentos_de_xp_das_faixas': LancamentoDeXP.objects.filter(site_id=site).filter(
            Q(regra_slug__startswith='bonus-inicio-etapa-') | Q(regra_slug__startswith='bonus-faixa-')
        ).count(),
    }
    resposta = JsonResponse({
        'aplicado': True, 'aplicado_em': copia.aplicado_em,
        'backup_conferido': hashlib.sha256(bytes(copia.conteudo)).hexdigest() == copia.sha256,
        'backup_sha256': copia.sha256, 'contagens_antes': copia.contagens,
        'contagens_agora': atuais, 'todos_com_inicio_limpo': not any(atuais.values()),
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    resposta['X-Robots-Tag'] = 'noindex, nofollow'
    resposta['Cache-Control'] = 'private, no-store'
    return resposta
