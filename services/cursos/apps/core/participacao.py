import os

import httpx


def consultar(ids):
    ids = list(dict.fromkeys(str(i) for i in ids if i))
    if not ids:
        return {}
    base = os.environ.get("QUIZ_PARTICIPACAO_URL", "").rstrip("/")
    token = os.environ.get("QUIZ_PARTICIPACAO_TOKEN", "")
    site = os.environ.get("SITE_ID", "")
    if not base or not token or not site:
        return {}
    mapa = {}
    try:
        with httpx.Client(timeout=5) as cliente:
            for inicio in range(0, len(ids), 500):
                lote = ids[inicio:inicio + 500]
                resposta = cliente.post(base + "/interno/nps/participacao", json={"site_id": site, "ids": lote}, headers={"Authorization": "Bearer " + token})
                resposta.raise_for_status()
                dados = resposta.json()
                if not isinstance(dados, dict) or any(i not in dados or not isinstance(dados[i], dict) or dados[i].get("segmento") not in ("sem_avaliacao", "promotor", "neutro", "detrator") for i in lote):
                    return {}
                mapa.update(dados)
    except (httpx.HTTPError, ValueError):
        return {}
    return mapa


def publica(estado):
    return bool(estado and estado.get("segmento") != "detrator")


def minha(pessoa_id):
    return consultar([pessoa_id]).get(str(pessoa_id), {})


def comentarios_visiveis(consulta, pessoa):
    from django.db.models import Q
    ids = list(consulta.values_list("autor_id", flat=True).distinct())
    estados = consultar(ids)
    visiveis = [i for i, e in estados.items() if e.get("segmento") != "detrator"]
    return consulta.filter(Q(autor_id__in=visiveis) | Q(autor=pessoa))
