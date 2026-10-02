"""Dados privados de campanhas para a interface administrativa do quiz."""

from urllib.parse import urlencode, urlsplit

from django.http import Http404, JsonResponse

from .campanhas import relatorio_campanhas
from .direcionadas import parametros_de_entrada
from .editor import _authorized, _error, _site
from .experiencias import resolver_experiencia
from .models import Quiz


AVISO_CLIQUE = "Saída registra clique no botão; compra, receita e LTV dependem de confirmação do checkout."


def _quiz_privado(request, slug):
    site = _site(request)
    if site is None:
        return None
    return Quiz.objects.filter(site=site, slug=slug).select_related("site").first()


def _host_https(host):
    try:
        partes = urlsplit(f"https://{host}")
        valido = (
            bool(partes.hostname)
            and partes.netloc == host
            and partes.username is None
            and partes.password is None
            and partes.path == ""
            and partes.query == ""
            and partes.fragment == ""
        )
    except ValueError:
        valido = False
    if not valido:
        raise ValueError("Host do site inválido para gerar links HTTPS.")
    return host


def relatorio(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    quiz = _quiz_privado(request, slug)
    if quiz is None:
        return _error("Quiz ou site não encontrado.", 404)
    try:
        dados = relatorio_campanhas(
            quiz,
            inicio=request.GET.get("inicio") or None,
            fim=request.GET.get("fim") or None,
        )
    except ValueError as erro:
        return _error(str(erro), 422)
    dados["aviso"] = AVISO_CLIQUE
    return JsonResponse(dados)


def links(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    quiz = _quiz_privado(request, slug)
    if quiz is None:
        return _error("Quiz ou site não encontrado.", 404)
    try:
        host = _host_https(quiz.site.host)
    except ValueError as erro:
        return _error(str(erro), 422)

    contexto, utm = parametros_de_entrada(request.GET)
    campanha = {
        chave: contexto[chave]
        for chave in ("src", "med", "cpg", "ctv")
        if contexto[chave]
    }
    utms = {f"utm_{chave}": valor for chave, valor in utm.items() if valor}
    itens = []
    vistos = set()
    for versao in quiz.versions.filter(active=True).order_by("key"):
        experience = versao.experience if isinstance(versao.experience, dict) else {}
        formatos = experience.get("formats")
        segmentos = experience.get("segments")
        if not isinstance(formatos, dict):
            continue
        opcoes_segmento = [""] + (
            sorted(segmentos) if isinstance(segmentos, dict) else []
        )
        for formato in sorted(formatos):
            for segmento in opcoes_segmento:
                try:
                    resolvida = resolver_experiencia(versao, formato, segmento or None)
                except Http404:
                    continue
                if resolvida["fmt"] == "ai" and not resolvida["ai_disponivel"]:
                    continue
                identidade = (versao.key, resolvida["fmt"], segmento)
                if identidade in vistos:
                    continue
                vistos.add(identidade)
                parametros = {"v": versao.key, "fmt": resolvida["fmt"]}
                if segmento:
                    parametros["seg"] = segmento
                parametros.update(campanha)
                parametros.update(utms)
                itens.append(
                    {
                        "version_key": versao.key,
                        "fmt": resolvida["fmt"],
                        "seg": segmento,
                        "url": f"https://{host}/quiz/{quiz.slug}/?{urlencode(parametros)}",
                    }
                )
    return JsonResponse(
        {
            "site_id": quiz.site_id,
            "quiz_slug": quiz.slug,
            "links": itens,
            "total": len(itens),
        }
    )
