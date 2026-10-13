"""Prévia administrativa; nenhum gesto de publicação ou alteração de recebimento."""
from urllib.parse import quote, urlencode
from decimal import Decimal

import httpx
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.utils.dateparse import parse_date

from .clients import GamificacaoClient, http
from .placar import site_de


def _admin(request):
    admin = getattr(request, "admin", None)
    if not isinstance(admin, dict) or admin.get("equipe_apenas"):
        raise Http404


def _consultar(site, caminho="", parametros=None, imagem=False):
    config = GamificacaoClient()._configuracao()
    if not config or not site:
        return None
    base, token = config
    try:
        resposta = http().get(
            f"{base}/ganhos-admin/{quote(site, safe='')}{caminho}",
            headers={"Authorization": f"Bearer {token}"}, params=parametros, timeout=8,
        )
        if resposta.status_code != 200:
            return None
        if imagem:
            if resposta.headers.get("content-type", "").split(";")[0] != "image/png":
                return None
            return resposta.content
        dados = resposta.json()
        return dados if isinstance(dados, dict) and dados.get("site_id") == site else None
    except (httpx.HTTPError, ValueError):
        return None


def _dinheiro(cents, moeda="BRL"):
    if type(cents) is not int or cents < 0:
        return "Valor não informado"
    numero = f"{Decimal(cents)/100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{'R$' if moeda == 'BRL' else moeda} {numero}"


def _data(texto):
    try:
        return parse_date(texto)
    except ValueError:
        return None


def _item(dados):
    if not isinstance(dados, dict) or type(dados.get("id")) is not int:
        raise ValueError
    item = {chave: dados.get(chave) for chave in (
        "id", "nome", "trabalho", "origem", "recebido_em", "analisada_em", "revisao", "leitura_status",
        "historico", "estado_texto", "print_disponivel", "elegivel", "motivos_exclusao",
    )}
    item["nome"] = str(item["nome"] or "Aluno")[:120]
    item["inicial"] = item["nome"][0].upper()
    item["trabalho"] = str(item["trabalho"] or "Trabalho não descrito no registro")[:280]
    item["data"] = _data(str(item["recebido_em"] or ""))
    moeda = str(dados.get("moeda_original") or "BRL")
    valor = dados.get("valor_original_cents")
    if not valor and moeda == "BRL":
        valor = dados.get("valor_cents")
    item["valor"] = _dinheiro(valor, moeda)
    item["url"] = reverse("ganhos_previa_detalhe", args=[item["id"]])
    item["print_url"] = reverse("ganhos_previa_print", args=[item["id"]])
    return item


@never_cache
@require_GET
def previa(request):
    _admin(request)
    de, ate = request.GET.get("de", ""), request.GET.get("ate", "")
    erro = ""
    inicio, fim = _data(de) if de else None, _data(ate) if ate else None
    if (de and not inicio) or (ate and not fim) or (inicio and fim and inicio > fim):
        erro = "Informe um período válido, com a data inicial antes da final."
    try:
        pagina = max(1, int(request.GET.get("pagina", "1")))
    except ValueError:
        pagina = 1
    dados = None if erro else _consultar(site_de(request), parametros={"de": de, "ate": ate, "pagina": pagina})
    itens = []
    if dados is not None:
        try:
            itens = [_item(i) for i in dados["itens"]]
        except (KeyError, ValueError, TypeError):
            dados = None
    return render(request, "admin/ganhos_previa.html", {
        "admin": request.admin, "itens": itens, "destaques": [i for i in itens if i["elegivel"]][:3],
        "indisponivel": dados is None and not erro, "erro": erro,
        "de": de, "ate": ate, "pagina": pagina, "total": dados.get("total", 0) if dados else None,
        "anterior": "?" + urlencode({"de": de, "ate": ate, "pagina": pagina-1}) if pagina > 1 else "",
        "proxima": "?" + urlencode({"de": de, "ate": ate, "pagina": pagina+1}) if dados and dados.get("mais") else "",
    }, status=400 if erro else 200)


@never_cache
@require_GET
def detalhe(request, registro_id):
    _admin(request)
    dados = _consultar(site_de(request), f"/{registro_id}")
    if not dados:
        raise Http404
    try:
        item = _item(dados["item"])
    except (KeyError, ValueError, TypeError):
        raise Http404 from None
    return render(request, "admin/ganhos_previa.html", {"admin": request.admin, "item": item})


@never_cache
@require_GET
def print_privado(request, registro_id):
    _admin(request)
    conteudo = _consultar(site_de(request), f"/{registro_id}/print", imagem=True)
    if not conteudo:
        raise Http404
    resposta = HttpResponse(conteudo, content_type="image/png")
    resposta["Cache-Control"] = "private, no-store"
    resposta["Content-Disposition"] = 'inline; filename="print-privado.png"'
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta
