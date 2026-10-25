"""Apresentação das conquistas reconhecidas; nunca concede nem retira XP."""


def fila(pendente):
    if not isinstance(pendente, dict):
        return []
    itens = pendente.get('fila', [pendente] if pendente else [])
    return [dict(item) for item in itens if isinstance(item, dict)
            and type(item.get('ordem')) is int and 2 <= item['ordem'] <= 13]


def empacotar(itens):
    if not itens:
        return {}
    return {**itens[0], **({'fila': itens} if len(itens) > 1 else {})}


def acrescentar(jornada, antes, depois):
    from .bonus_inicio import recebido_faixa

    itens = fila(jornada.celebracao_pendente)
    existentes = {item['ordem'] for item in itens}
    for ordem in range(antes['atual']['ordem'] + 1, depois['atual']['ordem'] + 1):
        if ordem not in existentes:
            itens.append({'ordem': ordem, 'tipo': 'grau' if ordem > 7 else 'cor',
                          'bonus_xp': recebido_faixa(jornada.pessoa_id, jornada.site_id, ordem)})
    jornada.celebracao_pendente = empacotar(itens)


def confirmar(jornada, ordem):
    itens = fila(jornada.celebracao_pendente)
    if itens and str(itens[0]['ordem']) == str(ordem):
        jornada.celebracao_pendente = empacotar(itens[1:])
        return True
    return False


def para_tela(jornada):
    from .bonus_inicio import recebido_faixa

    itens = fila(jornada.celebracao_pendente) if jornada else []
    for item in itens:
        # Inclui pendências antigas sem inventar uma recompensa configurada.
        if 'bonus_xp' not in item:
            item['bonus_xp'] = recebido_faixa(jornada.pessoa_id, jornada.site_id, item['ordem'])
    return empacotar(itens)
