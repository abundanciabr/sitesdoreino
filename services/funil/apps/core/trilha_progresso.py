"""Confere a resposta individual antes de incluir dados pessoais na página."""

from datetime import datetime
from django.utils.dateparse import parse_datetime


def _texto(valor, limite=300):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def _inteiro(valor, *, minimo=0):
    return type(valor) is int and valor >= minimo


def validar_progresso(dados, pessoa_id, site_id):
    if not isinstance(dados, dict) or str(dados.get("pessoa_id")) != pessoa_id or dados.get("site_id") != site_id:
        return None
    etapas = dados.get("etapas")
    atual = dados.get("atual_ordem")
    if not isinstance(etapas, list) or len(etapas) != 13 or not _inteiro(atual, minimo=1) or atual > 13:
        return None
    if not _inteiro(dados.get("total_cents")) or type(dados.get("meta_escolhida")) is not bool:
        return None
    meta = dados.get("meta_cents")
    if meta is not None and not _inteiro(meta):
        return None
    if dados["meta_escolhida"] and (meta is None or meta <= 0):
        return None
    ordens = set()
    alcancadas = []
    for etapa in etapas:
        if not isinstance(etapa, dict):
            return None
        ordem = etapa.get("ordem")
        if not _inteiro(ordem, minimo=1) or ordem > 13 or ordem in ordens:
            return None
        ordens.add(ordem)
        if not _texto(etapa.get("nome"), 200) or type(etapa.get("alcancada")) is not bool:
            return None
        if not isinstance(etapa.get("conquista"), str):
            return None
        etapa_meta = etapa.get("meta_cents")
        if etapa_meta is not None and not _inteiro(etapa_meta):
            return None
        if ordem <= 5 and etapa_meta is not None:
            return None
        if ordem >= 6 and ((dados["meta_escolhida"] and etapa_meta is None)
                           or (not dados["meta_escolhida"] and etapa_meta is not None)):
            return None
        data = etapa.get("alcancada_em")
        if data is not None:
            if not isinstance(data, str):
                return None
            try:
                if not isinstance(parse_datetime(data), datetime):
                    return None
            except ValueError:
                return None
        if etapa["alcancada"]:
            alcancadas.append(ordem)
        elif data is not None:
            return None
    if ordens != set(range(1, 14)) or not alcancadas or atual != max(alcancadas):
        return None
    return dict(dados, etapas=sorted(etapas, key=lambda etapa: etapa["ordem"]))


