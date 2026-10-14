"""Assinatura do conteúdo efetivamente lido pela banca."""
import hashlib
import json


def assinatura(conteudo):
    return hashlib.sha256(json.dumps(conteudo, ensure_ascii=False,
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def blocos(secoes):
    saida = {}
    for secao in secoes:
        nome = secao.get('nome', secao.get('tipo', ''))
        for slot, valor in secao.get('slots', {}).items():
            if isinstance(valor, str) and valor.strip() and slot not in {'imagem', 'cta_destino'}:
                saida[f'{nome}.{slot}'] = valor
    return saida
