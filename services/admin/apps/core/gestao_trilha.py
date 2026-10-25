"""Gerenciamento da Trilha a partir das matrículas da escola."""
import httpx
from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from urllib.parse import urlencode, quote
from .trilha import _admin, _privada, _matriculas, _identidade, _texto, _alunos
from .clients import GamificacaoClient, http

@require_http_methods(["GET", "POST"])
def gestao_trilha(request):
    _admin(request)
    ctx = {"admin": request.admin}
    linhas = _matriculas()
    if linhas is None:
        ctx["erro"] = "Não foi possível consultar os alunos agora."
        return _privada(render(request, "admin/gestao_trilha.html", ctx, status=503))
    dados = request.POST if request.method == "POST" else request.GET
    aluno = _texto(dados.get("aluno"), 120)
    if not aluno:
        q = _texto(request.GET.get("q"), 120).casefold()
        ctx.update(q=q, alunos=[dict(a, url=reverse("gestao_trilha") + "?" + a["url"].split("?",1)[1]) for a in _alunos(linhas, q)])
    else:
        matricula = next((m for m in linhas if str(m.get("id")) == aluno), None)
        if not matricula:
            raise Http404
        ctx.update(aluno=aluno, nome=matricula.get("nome_completo") or "Aluno")
        estado, pessoa = _identidade(matricula.get("email", ""))
        config = GamificacaoClient()._configuracao()
        if estado != "ok" or config is None:
            ctx["erro"] = "Não foi possível consultar a Trilha deste aluno agora."
        else:
            base, token = config
            url = base + "/gestao-trilha/" + quote(matricula["site_id"], safe="") + "/" + quote(pessoa, safe="")
            try:
                headers = {"Authorization": "Bearer " + token}
                if request.method == "POST":
                    ordem = int(dados.get("ordem", "0"))
                    revisao = int(dados.get("revisao", "-1"))
                    resposta = http().post(url, headers=headers, json={"ordem": ordem,
                        "tipo": dados.get("tipo", ""), "revisao": revisao,
                        "ator": str(request.admin.get("id") or request.admin.get("email") or "admin")}, timeout=10)
                    if resposta.status_code == 200:
                        return _privada(redirect(reverse("gestao_trilha") + "?" + urlencode({"aluno": aluno, "removida": "1"})))
                    ctx["erro"] = resposta.json().get("detail", "A remoção não foi confirmada. Recarregue e confira a Trilha.") if resposta.status_code == 409 else "A remoção não foi confirmada. Recarregue e confira a Trilha."
                resposta = http().get(url, headers=headers, timeout=10)
                if resposta.status_code == 200:
                    ctx["trilha"] = resposta.json()
                else:
                    ctx["erro"] = ctx.get("erro") or "O progresso está indisponível agora."
            except (httpx.HTTPError, ValueError, TypeError):
                ctx["erro"] = "Não foi possível confirmar a operação. Recarregue e confira a Trilha antes de tentar novamente."
    ctx["removida"] = request.GET.get("removida") == "1"
    return _privada(render(request, "admin/gestao_trilha.html", ctx))
