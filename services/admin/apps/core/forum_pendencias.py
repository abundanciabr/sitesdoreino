"""Lista central de questões do fórum que ainda não estão resolvidas."""

import os
from datetime import datetime
from urllib.parse import urlencode

import httpx
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def forum_pendencias(request):
    if not getattr(request, "admin", None) or request.admin.get("equipe_apenas"):
        raise Http404
    filtro = request.GET.get("filtro", "abertas")
    if filtro not in ("abertas", "sem-resposta", "respondidas"):
        filtro = "abertas"
    params = {"filtro": filtro, "area": request.GET.get("area", "")[:60], "q": request.GET.get("q", "").strip()[:120]}
    try:
        pagina = max(1, int(request.GET.get("pagina", "1")))
    except (ValueError, TypeError):
        pagina = 1
    contexto = {"admin": request.admin, **params, "dados": None, "erro": ""}
    base = (os.environ.get("FORUM_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("TOKEN_FORUM") or "").strip()
    if base and token:
        if not base.endswith("/interno"):
            base += "/interno"
        try:
            resposta = httpx.get(base + "/questoes/pendentes", params={**params, "pagina": pagina}, headers={"Authorization": f"Bearer {token}"}, timeout=8.0)
            resposta.raise_for_status()
            dados = resposta.json()
            if not isinstance(dados, dict) or not isinstance(dados.get("itens"), list):
                raise ValueError("resposta inválida")
            for item in dados["itens"]:
                item["criado_em"] = datetime.fromisoformat(item["criado_em"])
                dias = max(0, (timezone.now() - item["criado_em"]).days)
                item["tempo"] = "hoje" if dias == 0 else ("há 1 dia" if dias == 1 else f"há {dias} dias")
            contexto["dados"] = dados
            contexto["anterior"] = urlencode({**params, "pagina": dados["pagina"] - 1}) if dados["pagina"] > 1 else ""
            contexto["proxima"] = urlencode({**params, "pagina": dados["pagina"] + 1}) if dados["pagina"] < dados["paginas"] else ""
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            contexto["erro"] = "Não foi possível consultar o fórum agora. Tente novamente."
    else:
        contexto["erro"] = "Não foi possível consultar o fórum agora. Tente novamente."
    return render(request, "admin/forum_pendencias.html", contexto, status=503 if contexto["erro"] else 200)
