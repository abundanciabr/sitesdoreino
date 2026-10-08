"""Integração preparada; concessão aguarda ação, pontos e retroatividade do mantenedor."""
import importlib
import uuid

DEFINICAO_DO_MANTENEDOR = None


def envelope(participacao, acao, fato_id, quando):
    return {'event_id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'meshcraft:pratica:{participacao.pk}:{acao}:{fato_id}')),
            'event': 'pratica.' + acao, 'version': 1, 'ator_id': participacao.pessoa_id,
            'occurred_at': quando.isoformat(), 'data': {'participacao_id': str(participacao.pk),
                                                      'fato_id': str(fato_id), 'origem': 'fila_de_pratica'}}


def aplicar(participacao, acao, fato_id, quando):
    # Nenhum ponto, regra ativa ou retroativo nasce sem a definição pedida.
    if DEFINICAO_DO_MANTENEDOR is None:
        return []
    runtime = importlib.import_module('config.runtime')
    with runtime.serving('gamificacao'):
        motor = importlib.import_module('modules.gamificacao.apps.gamificacao.motor')
        return motor.aplicar(envelope(participacao, acao, fato_id, quando), participacao.site_id)
