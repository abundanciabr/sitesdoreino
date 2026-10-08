"""Visibilidade atual consultada na avaliação, sem cache entre requisições."""

import os

import httpx
from django.db.models import Q


class AvaliacaoIndisponivel(RuntimeError):
    pass


def consultar(ids):
    ids = list(dict.fromkeys(str(i) for i in ids if i))
    if not ids:
        return {}
    base = os.environ.get("QUIZ_PARTICIPACAO_URL", "").rstrip("/")
    token = os.environ.get("QUIZ_PARTICIPACAO_TOKEN", "")
    site = os.environ.get("SITE_ID", "")
    if not base or not token or not site:
        raise AvaliacaoIndisponivel("Avaliação indisponível.")
    mapa = {}
    try:
        with httpx.Client(timeout=5) as cliente:
            for inicio in range(0, len(ids), 500):
                lote = ids[inicio:inicio + 500]
                resposta = cliente.post(base + "/interno/nps/participacao", json={"site_id": site, "ids": lote}, headers={"Authorization": "Bearer " + token})
                resposta.raise_for_status()
                dados = resposta.json()
                if not isinstance(dados, dict) or any(i not in dados or not isinstance(dados[i], dict) or dados[i].get("segmento") not in ("sem_avaliacao", "promotor", "neutro", "detrator") for i in lote):
                    raise AvaliacaoIndisponivel("Avaliação indisponível.")
                mapa.update(dados)
    except (httpx.HTTPError, ValueError) as erro:
        raise AvaliacaoIndisponivel("Avaliação indisponível.") from erro
    return mapa


def da_pessoa(pessoa):
    return consultar([pessoa.pk]).get(str(pessoa.pk), {}) if pessoa else {}


def topicos_visiveis(consulta, ator):
    if ator.eh_admin:
        return consulta
    ids = consulta.values_list("autor_id", flat=True).distinct()
    try:
        estados = consultar(ids)
        restritos = [i for i, e in estados.items() if e["segmento"] == "detrator"]
        return consulta.filter(~Q(autor_id__in=restritos) | Q(autor_id=ator.pessoa.pk if ator.pessoa else ""))
    except AvaliacaoIndisponivel:
        return consulta.filter(Q(autor__isnull=True) | Q(autor_id=ator.pessoa.pk if ator.pessoa else ""))


def mensagens_visiveis(consulta, ator):
    if ator.eh_admin:
        return consulta
    ids = set(consulta.values_list("autor_id", flat=True)) | set(consulta.values_list("topico__autor_id", flat=True))
    try:
        estados = consultar(ids)
        restritos = [i for i, e in estados.items() if e["segmento"] == "detrator"]
        proprio = str(ator.pessoa.pk) if ator.pessoa else ""
        return consulta.filter(~Q(autor_id__in=restritos) | Q(autor_id=proprio)).filter(~Q(topico__autor_id__in=restritos) | Q(topico__autor_id=proprio))
    except AvaliacaoIndisponivel:
        return consulta.filter(Q(autor__isnull=True) | Q(autor_id=ator.pessoa.pk if ator.pessoa else "")).filter(Q(topico__autor__isnull=True) | Q(topico__autor_id=ator.pessoa.pk if ator.pessoa else ""))


def selo_visivel(estado, proprio=False):
    return bool(estado.get("embaixador") and (proprio or (estado.get("segmento") != "detrator" and not estado.get("conquistas_privadas_ate"))))


def decorar(lista, ator):
    try:
        estados = consultar([item.autor_id for item in lista])
    except AvaliacaoIndisponivel:
        estados = {}
    for item in lista:
        estado = estados.get(str(item.autor_id), {})
        proprio = ator.pessoa is not None and item.autor_id == ator.pessoa.pk
        item.embaixador = selo_visivel(estado, proprio)
        item.prioridade_promotor = estado.get("segmento") == "promotor"
        if not proprio and (estado.get("segmento") == "detrator" or estado.get("conquistas_privadas_ate")):
            item.etiqueta = None
    return lista
