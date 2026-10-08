"""Ações explícitas sobre uma avaliação de satisfação do aluno."""
from urllib.parse import urlencode

from django.http import HttpResponseBadRequest, HttpResponseRedirect, Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .nps import _site, _texto
from .nps_client import NPSClient
from .nps_painel import preparar_painel


def _dados(request):
    origem = request.POST if request.method == "POST" else request.GET
    return {"site_id": _texto(origem.get("site_id"), 100), "aluno_id": _texto(origem.get("aluno_id")),
            "tentativa_id": _texto(origem.get("avaliacao"), 100)}


def _painel_url(dados, **extra):
    return reverse("crm_satisfacao") + "?" + urlencode({"site_id": dados["site_id"], **extra})


def _executar(request, acao):
    dados = _dados(request)
    if not all(dados.values()):
        return HttpResponseBadRequest("Informe site, aluno e avaliação.")
    corpo = {**dados, "acao": acao}
    if acao == "excluir":
        if request.POST.get("confirmacao") != "excluir":
            return HttpResponseBadRequest("Confirme a exclusão definitiva desta avaliação.")
        corpo["confirmacao"] = "excluir"
    estado, detalhe = NPSClient().acao_avaliacao(corpo)
    if estado != NPSClient.OK:
        return render(request, "admin/crm_satisfacao_acao.html", {
            "admin": request.admin, "erro": detalhe if isinstance(detalhe, str) else "Não foi possível concluir a ação. Tente novamente.",
            "voltar_url": _painel_url(dados, aluno_id=dados["aluno_id"], avaliacao=dados["tentativa_id"]),
        }, status=503 if estado == NPSClient.INDISPONIVEL else 400)
    if acao == "restaurar":
        return HttpResponseRedirect(_painel_url(dados, aluno_id=dados["aluno_id"], avaliacao=dados["tentativa_id"], acao=acao))
    return HttpResponseRedirect(_painel_url(dados, acao=acao))


@require_POST
def arquivo(request):
    acao = request.POST.get("acao")
    if acao not in ("arquivar", "restaurar"):
        return HttpResponseBadRequest("Ação inválida.")
    return _executar(request, acao)


@require_GET
def confirmar_exclusao(request):
    dados = _dados(request)
    if not all(dados.values()):
        raise Http404
    estado, historico = NPSClient().historico(dados["site_id"], aluno_id=dados["aluno_id"])
    voltar = _painel_url(dados, aluno_id=dados["aluno_id"], avaliacao=dados["tentativa_id"])
    if estado != NPSClient.OK or not isinstance(historico, dict):
        return render(request, "admin/crm_satisfacao_acao.html", {
            "admin": request.admin, "erro": "Não foi possível consultar esta avaliação agora. Tente novamente.", "voltar_url": voltar,
        }, status=503)
    avaliacao = next((a for a in historico.get("avaliacoes", []) if a.get("id") == dados["tentativa_id"] and a.get("aluno_id") == dados["aluno_id"] and a.get("status") == "concluida"), None)
    if not avaliacao:
        raise Http404
    return render(request, "admin/crm_satisfacao_acao.html", {
        "admin": request.admin, "painel": preparar_painel(avaliacao), "dados": dados, "voltar_url": voltar,
    })


@require_POST
def excluir(request):
    return _executar(request, "excluir")
