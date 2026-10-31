"""Destinos opcionais das alternativas; documentos antigos continuam lineares."""

FIM = "$resultado"


def documento_da_versao(versao):
    return (versao.experience.get("documento") or {}).get("versao") or {}


def tem_ramificacao(versao):
    return any(o.get("proxima") for p in documento_da_versao(versao).get("perguntas", []) for o in p["opcoes"])


def conferir_caminhos(versao):
    perguntas = versao["perguntas"]
    posicoes = {p["id"]: i for i, p in enumerate(perguntas)}
    somas = {FIM: {0}}
    for i in range(len(perguntas) - 1, -1, -1):
        p = perguntas[i]
        valores = set()
        for o in p["opcoes"]:
            if "proxima" in o and o["proxima"] is not None and not isinstance(o["proxima"], str):
                raise ValueError(f"perguntas.{p['id']}.opcoes.{o['id']}.proxima: precisa ser texto")
            destino = o.get("proxima") or (perguntas[i + 1]["id"] if i + 1 < len(perguntas) else FIM)
            if not isinstance(destino, str) or (destino != FIM and (destino not in posicoes or posicoes[destino] <= i)):
                raise ValueError(f"perguntas.{p['id']}.opcoes.{o['id']}.proxima: escolha uma pergunta posterior ou {FIM}")
            valores.update(o["pontos"] + n for n in somas[destino])
        somas[p["id"]] = valores
    return somas[perguntas[0]["id"]]


def caminho_documento(versao, respostas):
    """Somente o caminho alcançado; respostas de ramos abandonados são ignoradas."""
    perguntas = versao["perguntas"]
    indice = {p["id"]: i for i, p in enumerate(perguntas)}
    caminho = []
    i = 0
    while i < len(perguntas):
        p = perguntas[i]
        caminho.append(p)
        escolhida = respostas.get(p["id"])
        if escolhida is None:
            return caminho, p
        o = next((o for o in p["opcoes"] if o["id"] == escolhida), None)
        if o is None:
            raise ValueError(f"respostas: opção desconhecida na pergunta {p['id']}")
        destino = o.get("proxima")
        if destino == FIM:
            break
        i = indice[destino] if destino else i + 1
    return caminho, None


def preparar(versao):
    perguntas = list(versao.questions.prefetch_related("options"))
    documento = documento_da_versao(versao)
    fontes = documento.get("perguntas", [])
    ids = {p["id"]: str(q.id) for p, q in zip(fontes, perguntas)}
    for q, p in zip(perguntas, fontes):
        q.destinos_quiz = {str(o.id): (None if f.get("proxima") == FIM else ids.get(f.get("proxima"), "")) for o, f in zip(q.options.all(), p["opcoes"])}
    return perguntas


def percurso(perguntas, respostas):
    por_id = {str(p.id): i for i, p in enumerate(perguntas)}
    caminho = []
    i = 0
    while i < len(perguntas):
        q = perguntas[i]
        caminho.append(q)
        valor = respostas.get(str(q.id))
        if valor is None:
            return caminho, q
        if not any(str(o.id) == str(valor) for o in q.options.all()):
            raise ValueError("Opção inválida para esta pergunta.")
        destino = getattr(q, "destinos_quiz", {}).get(str(valor), "")
        if destino is None:
            break
        i = por_id[destino] if destino else i + 1
    return caminho, None
