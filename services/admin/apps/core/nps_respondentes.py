"""Página do CRM com os alunos que concluíram a pesquisa."""

from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from .nps import _site, _texto
from .nps_client import NPSClient


@require_GET
def crm_satisfacao_respondentes(request):
    site_id = _site(request)
    q = _texto(request.GET.get("q"), 120)
    pagina = _texto(request.GET.get("pagina"), 10) or "1"
    estado, dados = NPSClient().respondentes(site_id, q=q, pagina=pagina) if site_id else ("sem-site", None)
    dados = dados if isinstance(dados, dict) else {}
    if estado == NPSClient.OK and (not isinstance(dados.get("itens"), list)
                                  or any(type(dados.get(k)) is not int for k in ("alunos", "total", "pagina", "paginas"))):
        estado, dados = NPSClient.INDISPONIVEL, {}
    for item in dados.get("itens", []):
        item["data"] = parse_datetime(item.get("concluida_em") or "")
        item["respostas_url"] = reverse("crm_satisfacao") + "?" + urlencode({
            "site_id": site_id, "aluno_id": item.get("aluno_id", ""),
            "email": item.get("email", ""),
        })
    def endereco(numero):
        return reverse("crm_satisfacao_respondentes") + "?" + urlencode({"site_id": site_id, "q": q, "pagina": numero})
    atual = dados.get("pagina", 1)
    return render(request, "admin/crm_satisfacao_respondentes.html", {
        "admin": request.admin, "site_id": site_id, "q": q, "estado": estado, "dados": dados,
        "anterior_url": endereco(atual - 1) if atual > 1 else "",
        "proxima_url": endereco(atual + 1) if atual < dados.get("paginas", 1) else "",
    })
