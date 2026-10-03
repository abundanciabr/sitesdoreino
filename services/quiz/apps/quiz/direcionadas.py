"""Experiência definida pelo link e preservada em cada tentativa."""

import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.http import Http404
from django.urls import reverse

from .experiencias import resolver_experiencia

PARAMETROS = ("v", "fmt", "seg", "src", "med", "cpg", "ctv")
UTMS = ("source", "medium", "campaign", "content", "term")
EQUIVALENCIAS = {"src": "source", "med": "medium", "cpg": "campaign", "ctv": "content"}


def entrada_da_tentativa(quizzes, slug, sessao=None):
    if not isinstance(slug, str) or (
        sessao is not None and not isinstance(sessao, str)
    ):
        return None
    if sessao:
        return quizzes.get(f"{slug}:{sessao}")
    return quizzes.get(slug)


def parametros_de_entrada(query):
    # Limite em bytes para que marcadores Unicode também caibam no cookie.
    def limitado(chave):
        return (
            query.get(chave, "").encode("utf-8")[:200].decode("utf-8", errors="ignore")
        )

    contexto = {chave: limitado(chave) for chave in PARAMETROS}
    utm = {chave: limitado(f"utm_{chave}") for chave in UTMS}
    utm = {chave: valor for chave, valor in utm.items() if valor}
    for interno, padrao in EQUIVALENCIAS.items():
        if not contexto[interno]:
            contexto[interno] = utm.get(padrao, "")
        if contexto[interno] and padrao not in utm:
            utm[padrao] = contexto[interno]
    return contexto, utm


def resolver_direcionada(request, quiz, quizzes, force_new=False):
    sessao = request.POST.get("quiz_attempt") if request.method == "POST" else None
    if request.method == "POST" and not sessao:
        raise Http404("tentativa indisponível")
    if sessao and not force_new:
        entrada = entrada_da_tentativa(quizzes, quiz.slug, sessao)
        if not entrada or entrada.get("site_id") != quiz.site_id:
            raise Http404("tentativa indisponível")
        versao = quiz.versions.filter(pk=entrada.get("version_id"), active=True).first()
        if not versao or (request.GET.get("v") and request.GET["v"] != versao.key):
            raise Http404("versão indisponível")
        return entrada, versao
    anterior = entrada_da_tentativa(quizzes, quiz.slug, sessao) if sessao else None
    if force_new and anterior:
        if anterior.get("site_id") != quiz.site_id:
            raise Http404("tentativa indisponível")
        versao = quiz.versions.filter(
            pk=anterior.get("version_id"), active=True
        ).first()
        if not versao:
            raise Http404("versão indisponível")
        return {**anterior, "session_id": str(uuid.uuid4())}, versao
    chave = request.GET.get("v")
    if not chave:
        raise Http404("este quiz precisa de uma versão no link")
    versao = quiz.versions.filter(key=chave, active=True).first()
    if not versao:
        raise Http404("versão indisponível")
    contexto, utm = parametros_de_entrada(request.GET)
    experiencia = resolver_experiencia(
        versao, contexto["fmt"] or None, contexto["seg"] or None
    )
    contexto.update(
        v=versao.key, fmt=experiencia["fmt"], seg=experiencia.get("seg", "")
    )
    for entrada in reversed(list(quizzes.values())) if not force_new else ():
        if (
            isinstance(entrada, dict)
            and entrada.get("site_id") == quiz.site_id
            and entrada.get("version_id") == versao.id
            and entrada.get("context") == contexto
            and entrada.get("utm") == utm
        ):
            return entrada, versao
    return {
        "session_id": str(uuid.uuid4()),
        "version_id": versao.id,
        "version_key": versao.key,
        "site_id": quiz.site_id,
        "context": contexto,
        "utm": utm,
    }, versao


def destino_com_parametros(destino, utm, contexto, tentativa=None, quiz_slug=None):
    """Endereço da saída: o destino HTTPS da faixa com a origem da tentativa.

    Parâmetros que o destino já traz ficam como estão. ValueError quando o
    destino não é HTTPS sem credenciais. `tentativa` (o session_id do quiz,
    um UUID opaco) vai como `qa` e `quiz_slug` como `qz`: é o que liga a
    compra, mais adiante, à versão e à campanha do quiz. Sem dado pessoal.
    """
    try:
        partes = urlsplit(destino)
        host = partes.hostname
        partes.port
    except (TypeError, ValueError) as erro:
        raise ValueError("destino indisponível") from erro
    if (
        partes.scheme != "https"
        or not host
        or partes.username
        or partes.password
        or any(ord(c) < 33 for c in destino)
    ):
        raise ValueError("destino indisponível")
    existentes = {chave for chave, _ in parse_qsl(partes.query)}
    parametros = {f"utm_{chave}": valor for chave, valor in (utm or {}).items() if valor}
    parametros.update(
        {
            chave: valor
            for chave, valor in (contexto or {}).items()
            if chave in PARAMETROS and isinstance(valor, str) and valor
        }
    )
    if tentativa:
        parametros["qa"] = str(tentativa)
    if quiz_slug:
        parametros["qz"] = str(quiz_slug)
    adicionais = urlencode(
        {chave: valor for chave, valor in parametros.items() if chave not in existentes}
    )
    consulta = partes.query + ("&" if partes.query and adicionais else "") + adicionais
    return urlunsplit(partes._replace(query=consulta))


def url_da_experiencia(quiz, entrada):
    contexto = entrada.get("context") or {}
    parametros = {
        chave: valor
        for chave, valor in contexto.items()
        if chave in PARAMETROS and valor
    }
    parametros.update(
        {
            f"utm_{chave}": valor
            for chave, valor in entrada.get("utm", {}).items()
            if valor
        }
    )
    base = reverse("quiz-formulario", args=[quiz.slug])
    return base + ("?" + urlencode(parametros) if parametros else "")
