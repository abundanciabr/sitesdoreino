"""Leituras da jornada por site; volumes observados não são uma coorte."""
import datetime as dt

from django.db.models import Min, Max
from ninja import Router, Schema
from ninja.errors import HttpError

from .models import Evento

router = Router()


class Leitura(Schema):
    chave: str
    quantidade: int | None
    primeiro: dt.datetime | None
    ultimo: dt.datetime | None
    sem_identificador: int


class Jornada(Schema):
    site_id: str
    de: dt.date
    ate: dt.date
    leituras: list[Leitura]


@router.get('/jornada-acesso', response=Jornada)
def jornada(request, site_id: str, de: dt.date, ate: dt.date):
    if not site_id.strip() or not 0 <= (ate - de).days < 366:
        raise HttpError(422, 'Informe o site e um intervalo de até 366 dias.')
    fontes = (
        ('cadastros', {'tipo': 'identidade.pessoa-cadastrada'}, 'dados__pessoa_id'),
        ('pedidos', {'tipo': 'matricula.situacao-alterada', 'dados__situacao_nova': 'aguardando'}, 'dados__matricula_id'),
        ('liberacoes', {'tipo': 'matricula.situacao-alterada', 'dados__situacao_nova': 'ativa', 'dados__origem': 'liberado'}, 'dados__matricula_id'),
        ('forum', {'tipo__in': ['forum.topico-criado', 'forum.mensagem-criada']}, 'ator_id'),
    )
    leituras = []
    for chave, filtros, campo in fontes:
        fonte = Evento.objects.filter(site_id=site_id, **filtros)
        cobertura = fonte.aggregate(primeiro=Min('ocorrido_em'), ultimo=Max('ocorrido_em'))
        valores = list(fonte.filter(dia__gte=de, dia__lte=ate).values_list(campo, flat=True))
        ids = {v.strip() for v in valores if isinstance(v, str) and v.strip()}
        leituras.append({
            'chave': chave,
            'quantidade': len(ids) if cobertura['primeiro'] is not None else None,
            **cobertura,
            'sem_identificador': sum(not isinstance(v, str) or not v.strip() for v in valores),
        })
    return {'site_id': site_id, 'de': de, 'ate': ate, 'leituras': leituras}
