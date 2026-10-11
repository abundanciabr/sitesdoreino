"""XP dos quatro gestos do começo, no ledger existente e uma vez por aluno."""

import uuid
import hashlib

from django.core import signing
from django.db.models import Sum
from django.utils import timezone

PONTOS_TAREFA = 100


def _slug(etapa):
    if etapa not in (1, 2, 3, 4):
        raise ValueError('Etapa inicial desconhecida.')
    return f'bonus-inicio-etapa-{etapa}'


def _origem(site_id, etapa):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'meshcraft:bonus-inicio:{site_id}:{etapa}')


def configurar(site_id):
    """Cria só regras ausentes; ajustes já existentes permanecem."""
    from .models import RegraDePontuacao

    for etapa in (1, 2, 3, 4):
        RegraDePontuacao.objects.get_or_create(
            site_id=site_id, slug=_slug(etapa), defaults={
                'evento_gatilho': f'gamificacao.inicio-etapa-{etapa}-concluida.v1',
                'beneficiario': 'ator', 'pontos': PONTOS_TAREFA, 'ativa': True,
                'vigente_desde': timezone.now(), 'quarentena_horas': 0,
                'acoes_cheias_por_dia': 0,
            },
        )


def conceder(pessoa_id, site_id, etapa):
    """Retorna apenas XP definitivamente lançado nesta chamada."""
    from .motor import aplicar

    configurar(site_id)
    creditos = aplicar({
        'event': f'gamificacao.inicio-etapa-{etapa}-concluida', 'version': 1,
        'event_id': str(_origem(site_id, etapa)),
        'occurred_at': timezone.now().isoformat(), 'ator_id': pessoa_id,
        'data': {'site_id': site_id, 'etapa': etapa},
    }, site_id)
    return sum(l.pontos for l in creditos if l.status == 'definitivo')


def recebido(pessoa_id, site_id, etapa):
    """Consulta somente o valor real e definitivo da tarefa desta pessoa."""
    from .models import LancamentoDeXP

    return LancamentoDeXP.objects.filter(
        pessoa__id_da_plataforma=pessoa_id, site_id=site_id,
        origem_event_id=str(_origem(site_id, etapa)), regra_slug=_slug(etapa),
        status=LancamentoDeXP.Status.DEFINITIVO,
    ).aggregate(soma=Sum('pontos'))['soma'] or 0


def recebido_faixa_amarela(pessoa_id, site_id):
    from .models import LancamentoDeXP

    origem = uuid.uuid5(uuid.NAMESPACE_URL, f'meshcraft:bonus-faixa:{site_id}:2')
    return LancamentoDeXP.objects.filter(
        pessoa__id_da_plataforma=pessoa_id, site_id=site_id,
        origem_event_id=str(origem), regra_slug='bonus-faixa-amarela',
        status=LancamentoDeXP.Status.DEFINITIVO,
    ).aggregate(soma=Sum('pontos'))['soma'] or 0


def comprovante(pessoa_id, site_id, etapa, xp_tarefa, xp_faixa):
    """Prova curta para a animação; os valores continuam conferidos no ledger."""
    dono = hashlib.sha256(f'{site_id}\0{pessoa_id}'.encode()).hexdigest()
    return signing.dumps((dono, etapa, xp_tarefa, xp_faixa), salt='inicio-conquista-v1')


def conferir_comprovante(token, pessoa_id, site_id, etapa):
    try:
        dono, etapa_token, tarefa, faixa = signing.loads(
            token, salt='inicio-conquista-v1', max_age=300,
        )
    except (signing.BadSignature, ValueError, TypeError):
        return None
    esperado = hashlib.sha256(f'{site_id}\0{pessoa_id}'.encode()).hexdigest()
    if dono != esperado or etapa_token != etapa or not all(isinstance(n, int) and n >= 0 for n in (tarefa, faixa)):
        return None
    if not (tarefa or faixa) or tarefa > recebido(pessoa_id, site_id, etapa):
        return None
    if faixa and (etapa != 4 or faixa > recebido_faixa_amarela(pessoa_id, site_id)):
        return None
    return tarefa, faixa
