"""Agregado de uso dos links existentes; não afirma primeiro login geral."""
import datetime as dt
from zoneinfo import ZoneInfo

from django.db.models import F
from django.db.models.functions import Lower, Trim
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.matriculas.models import Matricula, STATUS_QUE_JA_DERAM_ACESSO

router = Router()


class UsoDosLinks(Schema):
    site_id: str
    de: dt.date
    ate: dt.date
    liberadas: int
    com_link: int
    usaram_link: int


@router.get('/jornada-acesso/medicoes', response=UsoDosLinks)
def medir(request, site_id: str, de: dt.date, ate: dt.date):
    if not site_id.strip() or not 0 <= (ate - de).days < 366:
        raise HttpError(422, 'Informe o site e um intervalo de até 366 dias.')
    fuso = ZoneInfo('America/Sao_Paulo')
    inicio = dt.datetime.combine(de, dt.time.min, fuso)
    fim = dt.datetime.combine(ate + dt.timedelta(days=1), dt.time.min, fuso)
    linhas = Matricula.objects.filter(
        site_id=site_id, em_teste=False, order_id__startswith='pre:',
        status__in=STATUS_QUE_JA_DERAM_ACESSO,
        decidido_em__gte=inicio, decidido_em__lt=fim,
    ).annotate(pessoa=Lower(Trim('email'))).exclude(pessoa='')
    com_link = linhas.filter(aviso_event_id__isnull=False)
    usados = com_link.filter(acesso_consumido_em__gte=F('decidido_em'), acesso_consumido_em__lt=fim)
    def pessoas(qs):
        return qs.order_by().values('pessoa').distinct().count()
    return {'site_id': site_id, 'de': de, 'ate': ate, 'liberadas': pessoas(linhas),
            'com_link': pessoas(com_link), 'usaram_link': pessoas(usados)}
