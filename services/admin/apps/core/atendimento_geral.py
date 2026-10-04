"""Atendimento geral no CRM: o que dizer a quem escreve sem ter feito o quiz.

O texto e o endereço do quiz moram na mensageria (`/orientacoes/<site>`). Aqui só
se lê e se grava por ela: nenhuma cópia local. Cada alteração fica na auditoria.
"""
from urllib.parse import quote

import httpx
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.auditoria.models import Registro
from .clients import CatalogoClient, MensageriaClient, http
from .conteudos import host_da_requisicao

LIMITE = 300
SEM_MENSAGERIA = "A comunicação com a mensageria ainda não está configurada."
SEM_RESPOSTA = "A mensageria não respondeu agora. Tente novamente em alguns instantes."
NAO_CONFIRMADO = "Não consegui confirmar que a alteração foi salva. Reabra a tela antes de tentar de novo."


def _pedir(metodo, site_id, corpo=None):
    """(status, dados, erro). Sem status quando o pedido nem chegou a uma resposta."""
    config = MensageriaClient()._configuracao()
    if config is None:
        return None, None, SEM_MENSAGERIA
    base, token = config
    try:
        resposta = http().request(
            metodo, f"{base}/orientacoes/{quote(site_id, safe='')}", json=corpo,
            headers={"Authorization": "Bearer " + token}, timeout=8.0)
    except httpx.HTTPError:
        return None, None, SEM_RESPOSTA
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    if resposta.status_code == 403:
        return 403, dados, "A mensageria só deu acesso de leitura a esta tela; a alteração não foi feita."
    if resposta.status_code == 422 and isinstance(dados, dict) and isinstance(dados.get("detail"), str):
        return 422, dados, "A mensageria recusou os dados: " + dados["detail"]
    if resposta.status_code != 200 or not isinstance(dados, dict):
        return resposta.status_code, dados, SEM_RESPOSTA
    return 200, dados, ""


def _validar(endereco, texto):
    if endereco and not endereco.lower().startswith(("https://", "http://")):
        return "O endereço do quiz precisa ser completo, começando com https://"
    if len(endereco) > LIMITE:
        return f"O endereço do quiz aceita até {LIMITE} letras."
    if len(texto) > LIMITE:
        return f"O texto do atendimento geral aceita até {LIMITE} letras. Este tem {len(texto)}."
    return ""


def _auditar(request, site_id, desfecho):
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")
    Registro.objects.create(
        quem_email=request.admin.get("email", ""), quem_id=autor[:64], acao=Registro.EDITAR,
        alvo=site_id[:64], desfecho=desfecho, detalhe="CRM: atendimento geral e endereço do quiz",
    )


@require_http_methods(["GET", "POST"])
def atendimento_geral(request):
    host = host_da_requisicao(request)
    contexto = {"admin": request.admin, "erro": "", "recado": "", "limite": LIMITE,
                "site": {}, "endereco_quiz": "", "atendimento_geral": ""}
    site = CatalogoClient().site_por_host(host)
    if not site:
        contexto["erro"] = "Não consegui identificar este site."
        contexto["indisponivel"] = True
        return render(request, "admin/crm_atendimento_geral.html", contexto, status=503)
    site_id = str(site["id"])
    contexto["site"] = {"id": site_id, "nome": site.get("name", ""), "host": host}
    if request.method == "POST":
        endereco = request.POST.get("endereco_quiz", "").strip()
        texto = request.POST.get("atendimento_geral", "").strip()
        contexto["endereco_quiz"], contexto["atendimento_geral"] = endereco, texto
        erro = _validar(endereco, texto)
        if erro:
            contexto["erro"] = erro
            return render(request, "admin/crm_atendimento_geral.html", contexto, status=422)
        status, _, erro = _pedir("PUT", site_id, {"endereco_quiz": endereco, "atendimento_geral": texto})
        recusou = status in (403, 422)
        _auditar(request, site_id, Registro.OK if status == 200
                 else Registro.RECUSADO_PELA_CELULA if recusou else Registro.NAO_RESPONDEU)
        if status == 200:
            return HttpResponseRedirect(reverse("crm_atendimento_geral") + "?salvo=1")
        contexto["erro"] = erro if recusou else NAO_CONFIRMADO
        return render(request, "admin/crm_atendimento_geral.html", contexto, status=422 if recusou else 503)
    status, dados, erro = _pedir("GET", site_id)
    if status != 200:
        contexto["erro"] = erro
        contexto["indisponivel"] = True
        return render(request, "admin/crm_atendimento_geral.html", contexto, status=503)
    contexto["endereco_quiz"] = str(dados.get("endereco_quiz") or "")
    contexto["atendimento_geral"] = str(dados.get("atendimento_geral") or "")
    if request.GET.get("salvo"):
        contexto["recado"] = "Atendimento geral salvo."
    resposta = render(request, "admin/crm_atendimento_geral.html", contexto)
    resposta["Cache-Control"] = "no-store"
    return resposta
