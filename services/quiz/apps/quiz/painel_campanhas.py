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


def _lista(valor):
    return list(dict.fromkeys(item.strip() for item in valor.split(",") if item.strip()))


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

    # ctv, v e fmt aceitam listas separadas por vírgula: cada criativo vira um
    # link para cada experiência existente (4 criativos × 2 formatos × 3
    # segmentos = 24 links por versão).
    consulta = request.GET.copy()
    criativos = _lista(consulta.pop("ctv", [""])[-1]) or [""]
    content_fixo = request.GET.get("utm_content", "").strip()
    chaves = _lista(request.GET.get("v", ""))
    formatos_pedidos = _lista(request.GET.get("fmt", ""))
    # "geral" é o link sem segmento.
    segmentos_pedidos = [
        "" if item == "geral" else item for item in _lista(request.GET.get("seg", ""))
    ]
    contexto, utm = parametros_de_entrada(consulta)
    campanha = {
        chave: contexto[chave] for chave in ("src", "med", "cpg") if contexto[chave]
    }
    utms = {f"utm_{chave}": valor for chave, valor in utm.items() if valor}
    versoes = quiz.versions.filter(active=True).order_by("key")
    if chaves:
        versoes = versoes.filter(key__in=chaves)
        faltam = sorted(set(chaves) - set(versoes.values_list("key", flat=True)))
        if faltam:
            return _error(f"Versão ativa indisponível: {', '.join(faltam)}.", 422)
    from .conversa import _chave

    # Sem a chave do provedor a conversa por IA ainda abre, com as perguntas fixas.
    ia_ligada = bool(_chave())
    itens = []
    vistos = set()
    for versao in versoes:
        experience = versao.experience if isinstance(versao.experience, dict) else {}
        formatos = experience.get("formats")
        segmentos = experience.get("segments")
        if not isinstance(formatos, dict):
            continue
        opcoes_segmento = [""] + (
            sorted(segmentos) if isinstance(segmentos, dict) else []
        )
        if segmentos_pedidos:
            opcoes_segmento = [s for s in opcoes_segmento if s in segmentos_pedidos]
        for formato in formatos_pedidos or sorted(formatos):
            for segmento in opcoes_segmento:
                try:
                    resolvida = resolver_experiencia(versao, formato, segmento or None)
                except Http404:
                    continue
                identidade = (versao.key, resolvida["fmt"], segmento)
                if identidade in vistos:
                    continue
                vistos.add(identidade)
                for criativo in criativos:
                    parametros = {"v": versao.key, "fmt": resolvida["fmt"]}
                    if segmento:
                        parametros["seg"] = segmento
                    parametros.update(campanha)
                    if criativo:
                        parametros["ctv"] = criativo
                    parametros.update(utms)
                    if criativo and not content_fixo:
                        parametros["utm_content"] = criativo
                    itens.append(
                        {
                            "version_key": versao.key,
                            "fmt": resolvida["fmt"],
                            "seg": segmento,
                            "ctv": criativo,
                            "url": f"https://{host}/quiz/{quiz.slug}/?{urlencode(parametros)}",
                        }
                    )
    if (formatos_pedidos or segmentos_pedidos) and not itens:
        return _error(
            "Nenhuma experiência existe com esses formatos e segmentos.", 422
        )
    return JsonResponse(
        {
            "site_id": quiz.site_id,
            "quiz_slug": quiz.slug,
            "links": itens,
            "total": len(itens),
            "ia_ligada": ia_ligada,
        }
    )
