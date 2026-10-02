"""Tela de melhoria contínua do quiz: gargalos medidos e propostas de nova versão.

Mesma porta e mesmo caminho de dados da tela de campanhas. Aqui só se lê a
medição e se registra a decisão sobre propostas; versões existentes não mudam.
"""

from __future__ import annotations

import json

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .conteudos import _erro, _pedir

CAMPOS_PROPOSTA = (
    "versao_base",
    "gargalo",
    "hipotese",
    "prioridade",
    "mudanca",
    "key_sugerida",
)
CAMPOS_ATUALIZACAO = ("estado", "resultado_texto", "decisao_seguinte")
RECADOS = {
    "criada": "Proposta registrada. Nenhuma versão foi alterada.",
    "atualizada": "Proposta atualizada.",
}


def _periodo(request):
    return {
        nome: request.GET.get(nome, "").strip()[:10]
        for nome in ("inicio", "fim")
        if request.GET.get(nome, "").strip()
    }


def _detalhe(dados, padrao):
    if isinstance(dados, dict) and isinstance(dados.get("detail"), str):
        return dados["detail"]
    return padrao


def _salvar(request, slug):
    acao = request.POST.get("acao", "")
    if acao == "criar":
        corpo = {c: request.POST.get(c, "").strip() for c in CAMPOS_PROPOSTA}
        status, dados = _pedir(request, "quiz", "POST", slug, "propostas", corpo=corpo)
        recado = "criada"
    elif acao == "atualizar":
        proposta_id = request.POST.get("proposta_id", "")
        if not proposta_id.isdigit():
            return None, "Proposta inválida.", 422
        corpo = {
            c: request.POST.get(c, "").strip()
            for c in CAMPOS_ATUALIZACAO
            if request.POST.get(c, "").strip()
        }
        texto_json = request.POST.get("resultado_json", "").strip()
        if texto_json:
            try:
                corpo["resultado_json"] = json.loads(texto_json)
            except ValueError:
                return None, "O resultado em JSON não está válido.", 422
        status, dados = _pedir(
            request,
            "quiz",
            "PATCH",
            slug,
            f"propostas/{proposta_id}",
            corpo=corpo,
        )
        recado = "atualizada"
    else:
        return None, "Ação desconhecida.", 400
    if status in (200, 201):
        return recado, "", 200
    mensagem = _detalhe(dados, "Não consegui salvar a proposta agora.")
    return None, mensagem, 422 if status in (400, 409, 422) else 503


@require_http_methods(["GET", "POST"])
def quiz_evolucao(request, slug: str):
    falha = ""
    if request.method == "POST":
        recado, falha, _ = _salvar(request, slug)
        if recado:
            return HttpResponseRedirect(
                reverse("quiz_evolucao", kwargs={"slug": slug}) + f"?recado={recado}"
            )

    periodo = _periodo(request)
    status_leitura, leitura = _pedir(
        request, "quiz", "GET", slug, "evolucao", params=periodo
    )
    if status_leitura != 200 or not isinstance(leitura, dict):
        return _erro(
            request,
            "quiz",
            _detalhe(leitura, "Não consegui ler a evolução agora.")
            if status_leitura == 422
            else "Não consegui ler a evolução agora.",
            422 if status_leitura == 422 else 503,
        )
    status_propostas, propostas = _pedir(request, "quiz", "GET", slug, "propostas")
    if status_propostas != 200 or not isinstance(propostas, dict):
        return _erro(request, "quiz", "Não consegui ler as propostas agora.")
    lista = propostas.get("propostas")
    if not isinstance(lista, list) or not isinstance(leitura.get("gargalos"), list):
        return _erro(request, "quiz", "Os dados da evolução vieram incompletos.")

    return render(
        request,
        "admin/quiz_evolucao.html",
        {
            "admin": request.admin,
            "slug": slug,
            "filtros": {"inicio": periodo.get("inicio", ""), "fim": periodo.get("fim", "")},
            "leitura": leitura,
            "gargalos": leitura["gargalos"],
            "faltantes": leitura.get("dados_faltantes") or [],
            "por_dia": leitura.get("por_dia") or [],
            "por_campanha": leitura.get("por_campanha") or [],
            "por_dimensao": leitura.get("por_dimensao") or [],
            "comparacoes": leitura.get("comparacoes") or {},
            "propostas": lista,
            "recado": RECADOS.get(request.GET.get("recado", ""), ""),
            "falha": falha,
            "dados": request.POST if falha else {},
        },
        status=422 if falha else 200,
    )
