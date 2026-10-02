"""Prévia isolada de uma versão de quiz direcionado.

O operador do admin manda o documento (rascunho ou publicado) e, se quiser, as
respostas. Aqui só se calcula: pontuação, faixa, oferta e textos por formato e
segmento. Nada é gravado: nenhuma Submission, TelemetryEvent ou OutboxEvent,
nenhuma consulta ao banco e nenhum cookie de sessão do quiz.
"""

import json
from types import SimpleNamespace

from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .conteudo import conferir_documento
from .editor import FORMATO_DIRECIONADO, _authorized, _error
from .experiencias import calcular, resolver_experiencia

LIMITE_CORPO = 2_000_000


def _resposta(dados, status=200):
    resposta = JsonResponse(dados, status=status)
    resposta["Cache-Control"] = "no-store"
    return resposta


def _documento(payload, slug):
    documento = payload.get("documento")
    if not isinstance(documento, dict) or documento.get("formato") != FORMATO_DIRECIONADO:
        raise ValueError("documento: envie o documento quiz-low-ticket/2")
    try:
        conferir_documento(documento)
    except (TypeError, KeyError, AttributeError) as erro:
        raise ValueError("documento: estrutura inválida") from erro
    if documento["quiz"]["slug"] != slug:
        raise ValueError("quiz.slug: difere do endereço do quiz")
    return documento


def _versao(documento, chave):
    versoes = documento["versoes"]
    if chave in (None, ""):
        return versoes[0]
    for versao in versoes:
        if versao["key"] == chave:
            return versao
    raise ValueError(f"versao: {chave!r} não existe neste documento")


def _experiencia(versao, fmt, seg):
    candidata = SimpleNamespace(
        experience={
            "default_format": versao["default_format"],
            "formats": versao["formats"],
            "segments": versao["segments"],
        }
    )
    try:
        return resolver_experiencia(candidata, fmt=fmt or None, seg=seg or None)
    except Http404 as erro:
        raise ValueError(f"experiencia: {erro}") from erro


def _pontuar(versao, respostas):
    if not isinstance(respostas, dict):
        raise ValueError("respostas: precisa ser objeto pergunta -> opção")
    total = 0
    for numero, pergunta in enumerate(versao["perguntas"], start=1):
        escolhida = respostas.get(pergunta["id"])
        if escolhida is None:
            raise ValueError(f"respostas: responda a pergunta {numero}")
        opcao = next((o for o in pergunta["opcoes"] if o["id"] == escolhida), None)
        if opcao is None:
            raise ValueError(f"respostas: opção desconhecida na pergunta {numero}")
        total += opcao["pontos"]
    return total


def calcular_previa(documento, versao, experiencia, respostas, valores):
    pontuacao = _pontuar(versao, respostas)
    faixa = next(
        f for f in versao["faixas"] if f["min_score"] <= pontuacao <= f["max_score"]
    )
    oferta = next(o for o in documento["ofertas"] if o["id"] == faixa["oferta_id"])
    texto = (experiencia.get("results") or {}).get(faixa["key"], {})
    checkout = oferta.get("checkout_url")
    resultado = {
        "pontuacao": pontuacao,
        "faixa": {
            "key": faixa["key"],
            "min_score": faixa["min_score"],
            "max_score": faixa["max_score"],
            "title": texto.get("title", faixa["title"]),
            "description": texto.get("description", faixa["description"]),
            "botao_rotulo": texto.get("botao_rotulo", faixa["botao_rotulo"]),
            "botao_destino": checkout or "",
        },
        "oferta": {
            "id": oferta["id"],
            "nome": oferta["nome"],
            "para_quem": oferta.get("para_quem", ""),
            "entrega": oferta.get("entrega", ""),
            "checkout_url": checkout or "",
            "demonstracao": not checkout,
        },
    }
    if experiencia["fmt"] == "calc":
        resultado["calculo"] = calcular(experiencia["calculator"], valores or {})
    return resultado


@csrf_exempt
def previa(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "POST":
        return _error("Método não permitido.", 405)
    if len(request.body) > LIMITE_CORPO:
        return _error("Documento grande demais.", 413)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError("corpo: precisa ser objeto")
        documento = _documento(payload, slug)
        versao = _versao(documento, payload.get("versao"))
        experiencia = _experiencia(versao, payload.get("fmt"), payload.get("seg"))
        dados = {
            "ok": True,
            "versao": versao["key"],
            "formatos": sorted(versao["formats"]),
            "segmentos": sorted(versao["segments"]),
            "experiencia": {
                "fmt": experiencia["fmt"],
                "seg": experiencia["seg"],
                "headline": experiencia["headline"],
                "subheadline": experiencia["subheadline"],
                "video_url": experiencia["video_url"],
                "video_kind": experiencia["video_kind"],
                "calculator": experiencia["calculator"],
            },
            "perguntas": [
                {
                    "id": pergunta["id"],
                    "texto": pergunta["texto"],
                    "opcoes": [
                        {"id": o["id"], "texto": o["texto"]} for o in pergunta["opcoes"]
                    ],
                }
                for pergunta in versao["perguntas"]
            ],
        }
        if payload.get("respostas") is not None:
            dados.update(
                calcular_previa(
                    documento,
                    versao,
                    experiencia,
                    payload["respostas"],
                    payload.get("valores"),
                )
            )
    except (ValueError, UnicodeDecodeError) as erro:
        return _error(str(erro), 422)
    return _resposta(dados)
