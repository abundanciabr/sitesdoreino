"""Visita autenticada observada agora; a sessão é reconferida na dona."""
from datetime import datetime
from django.db import transaction
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from apps.matriculas.models import Matricula, AcessoAutenticado
from .clients import IdentidadeClient

router = Router()
ORIGENS = ('funil', 'cursos', 'forum', 'sugestoes')

class Visita(Schema):
    site_id: str
    origem: str

@router.post('/jornada-acesso/observar', response={204: None})
def observar(request, corpo: Visita):
    if not corpo.site_id.strip() or corpo.origem not in ORIGENS:
        raise HttpError(422, 'Site e origem da página são obrigatórios.')
    sessao = IdentidadeClient().sessao_completa(request.META.get('HTTP_COOKIE', ''))
    if not sessao:
        raise HttpError(401, 'Não foi possível confirmar a sessão.')
    agora = timezone.now()
    # O bloqueio também serializa uma liberação/revogação concorrente.
    with transaction.atomic():
        linhas = Matricula.objects.select_for_update().filter(
            site_id=corpo.site_id, em_teste=False, status__in=Matricula.STATUS_QUE_VALEM,
        ).annotate(email_canonico=Lower(Trim('email'))).filter(
            email_canonico=sessao['email'].strip().lower())
        for linha in linhas:
            data = linha.virou_aluno_em()
            liberada = datetime.fromisoformat(data) if data else None
            if liberada is None or liberada > agora:
                continue
            AcessoAutenticado.objects.get_or_create(
                matricula=linha, liberada_em=liberada,
                defaults={'pessoa_id': sessao['id'], 'origem': corpo.origem})
    return 204, None
