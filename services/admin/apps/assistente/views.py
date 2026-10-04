"""A tela do assistente do site: /admin/crm/assistente/. Só do administrador
(a porta barra quem não é). O site vem do domínio pelo qual a pessoa entrou,
nunca de um campo do formulário."""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.core.clients import CatalogoClient

from . import identidade
from .models import IdentidadeAssistente


def _quem(request) -> str:
    admin = getattr(request, "admin", None) or {}
    return str(admin.get("email") or admin.get("nome_exibido") or "admin") if isinstance(admin, dict) else "admin"


@require_http_methods(["GET", "POST"])
def assistente_do_site(request):
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    contexto = {
        "admin": getattr(request, "admin", None),
        "tons": IdentidadeAssistente.Tom.choices,
        "vozes": IdentidadeAssistente.Voz.choices,
        "recado": "Identidade salva. As próximas conversas já usam estes dados." if request.GET.get("salvo") == "1" else "",
    }
    if not site or not site.get("id"):
        contexto["erro"] = "Não consegui identificar este site agora. Nada foi alterado; tente de novo em instantes."
        return render(request, "assistente/assistente.html", contexto, status=503)
    site_id = str(site["id"])
    nome_do_site = str(site.get("name") or site.get("host") or "")
    if request.method == "POST":
        identidade.salvar(
            site_id,
            nome_do_site=nome_do_site,
            nome=request.POST.get("nome", ""),
            apresentacao=request.POST.get("apresentacao", ""),
            assinatura=request.POST.get("assinatura", ""),
            tom=request.POST.get("tom", ""),
            resposta_em_voz=request.POST.get("resposta_em_voz", ""),
            quem=_quem(request),
        )
        return HttpResponseRedirect(reverse("assistente_do_site") + "?salvo=1")
    linha = IdentidadeAssistente.objects.filter(site_id=site_id).first()
    contexto.update(
        site=site,
        nome_do_site=nome_do_site,
        linha=linha,
        atual=identidade.identidade_do_site(site_id, nome_do_site),
    )
    return render(request, "assistente/assistente.html", contexto)
