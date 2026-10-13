"""O chat recebe pedidos 24h; as respostas seguem o expediente de Brasília."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

FUSO = ZoneInfo('America/Sao_Paulo')


def disponibilidade(config, agora=None):
    agora = (agora or timezone.now()).astimezone(FUSO)
    if not config.expediente_ativo:
        return {'aberto': True, 'respostas_abertas': True, 'programado': False, 'horario': config.horario,
                'proxima_abertura': None, 'mensagem': ''}
    inicio, fim = config.expediente_inicio, config.expediente_fim
    horario = (f'Segunda a sexta, das {inicio:%H:%M} às {fim:%H:%M} '
               '(horário de Brasília). Sábados e domingos: sem atendimento.')
    aberto = agora.weekday() < 5 and inicio <= agora.time() < fim
    proxima = None
    if not aberto:
        for dias in range(8):
            data = agora.date() + timedelta(days=dias)
            candidata = datetime.combine(data, inicio, tzinfo=FUSO)
            if data.weekday() < 5 and candidata > agora:
                proxima = candidata
                break
    mensagem = '' if aberto else 'Suporte fechado. ' + horario
    if proxima:
        mensagem += f' Próxima abertura: {proxima:%d/%m/%Y às %H:%M}.'
    return {'aberto': True, 'respostas_abertas': aberto, 'programado': True, 'horario': horario,
            'proxima_abertura': proxima.isoformat() if proxima else None,
            'mensagem': mensagem}
