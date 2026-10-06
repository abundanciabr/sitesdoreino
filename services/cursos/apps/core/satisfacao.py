"""Pesquisa dos alunos: a sessão e a matrícula fornecem a identidade ao quiz."""
import os
import uuid
from urllib.parse import urlencode

import httpx
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.cursos.models import Curso, Progresso, Envio, ComentarioDeAula
from .sessao import quem_e, site_atual
from .clients import http


def pedir(metodo, caminho, identidade, corpo=None):
    base = (os.environ.get("QUIZ_API_URL") or "").rstrip("/")
    token = os.environ.get("QUIZ_API_TOKEN") or ""
    if not base or not token:
        return 503, {"detail": "A pesquisa está temporariamente indisponível."}
    base = base.removesuffix("/interno")
    try:
        resposta = http().request(metodo, base + "/interno/nps/" + caminho,
            headers={"Authorization": "Bearer " + token}, params=identidade,
            json={**(corpo or {}), **identidade} if metodo == "POST" else None,
            timeout=12)
        return resposta.status_code, resposta.json()
    except (httpx.HTTPError, ValueError):
        return 503, {"detail": "Não conseguimos consultar a pesquisa agora. Tente novamente."}


def evidencias(pessoa, curso):
    progressos = Progresso.objects.filter(pessoa=pessoa, aula__bloco__curso=curso)
    envios = Envio.objects.filter(pessoa=pessoa, aula__bloco__curso=curso)
    comentarios = ComentarioDeAula.objects.filter(autor=pessoa, aula__bloco__curso=curso)
    ultimo = envios.order_by("-enviado_em").values_list("enviado_em", flat=True).first()
    return {"participacao": "participação não disponível", "fonte_externa": None,
        "observacao": "Os registros abaixo são deste site. Não medem os estudos na Hotmart ou Herospark.",
        "registros_locais": {"aulas_concluidas": progressos.filter(estado="concluida").count(),
            "entregas": envios.count(), "comentarios": comentarios.count(),
            "ultima_entrega": ultimo.isoformat() if ultimo else None}}


@never_cache
@require_http_methods(["GET", "POST"])
def pesquisa(request, slug=None):
    ator = quem_e(request)
    contexto = {"curso": None, "erro": "", "cursos": [], "tentativa": None}
    if not ator.autenticado:
        return render(request, "cursos/satisfacao.html", {**contexto, "entrar": True})
    if not ator.matricula_conferida or not ator.eh_aluno:
        contexto["erro"] = "Não conseguimos confirmar uma matrícula ativa. Entre com o e-mail cadastrado na escola ou fale com a equipe."
        return render(request, "cursos/satisfacao.html", contexto, status=403)
    site = site_atual()
    cursos = Curso.objects.filter(site_id=site, produto_id__in=ator.produtos_matriculados)
    contexto["cursos"] = cursos
    if slug is None:
        return render(request, "cursos/satisfacao.html", contexto)
    curso = cursos.filter(slug=slug).first()
    if not curso:
        raise Http404("Curso não matriculado")
    contexto["curso"] = curso
    dono = {"site_id": site, "aluno_id": str(ator.pessoa.pk)}
    tid = request.POST.get("tentativa_id") if request.method == "POST" else request.GET.get("tentativa")
    if tid:
        try:
            tid = str(uuid.UUID(tid))
        except (ValueError, TypeError):
            raise Http404("Tentativa inválida") from None
    dados, status = None, 200
    if request.method == "POST":
        if request.POST.get("acao") == "iniciar":
            matricula = next((m for m in getattr(request, "_matriculas_nps", [])
                if m.get("site_id") == site and m.get("product_id") == curso.produto_id), None)
            if not matricula:
                return render(request, "cursos/satisfacao.html", {**contexto, "erro": "Não foi possível confirmar a matrícula deste curso."}, status=403)
            status, dados = pedir("POST", "tentativas", dono, {
                "aluno": getattr(request, "_identidade_nps", {"id": str(ator.pessoa.pk), "nome": ator.pessoa.nome_exibido}),
                "produto": {"id": curso.produto_id}, "curso": {"id": str(curso.pk), "slug": curso.slug, "nome": curso.nome},
                "matricula": matricula, "evidencias": evidencias(ator.pessoa, curso)})
            if status in (200, 201):
                return HttpResponseRedirect(reverse("satisfacao-curso", args=[slug]) + "?" + urlencode({"tentativa": dados["id"]}))
        elif tid:
            # Confira o curso também: uma tentativa de outro curso não entra nesta tela.
            status, dados = pedir("GET", f"tentativas/{tid}", dono)
            if status == 200 and (dados.get("curso") or {}).get("slug") != slug:
                raise Http404("Tentativa de outro curso")
            if status == 200:
                corpo = {"acao": request.POST.get("acao", "responder")}
                if corpo["acao"] == "responder":
                    corpo.update(pergunta_id=request.POST.get("pergunta_id", ""), valor=request.POST.get("valor", ""))
                status, dados = pedir("POST", f"tentativas/{tid}/respostas", dono, corpo)
                if status == 200:
                    return HttpResponseRedirect(reverse("satisfacao-curso", args=[slug]) + "?" + urlencode({"tentativa": tid}))
    elif tid:
        status, dados = pedir("GET", f"tentativas/{tid}", dono)
        if status == 200 and (dados.get("curso") or {}).get("slug") != slug:
            raise Http404("Tentativa de outro curso")
    if status not in (200, 201):
        contexto["erro"] = (dados or {}).get("detail", "Não foi possível salvar. Tente novamente.")
        # Volta à pergunta atual após uma resposta inválida, preservando a tentativa.
        if tid:
            _, atual = pedir("GET", f"tentativas/{tid}", dono)
            if isinstance(atual, dict) and atual.get("id"):
                dados = atual
    contexto["tentativa"] = dados
    if dados:
        pergunta = dados.get("proxima_pergunta") or {}
        contexto["pergunta"] = pergunta
        contexto["nota_opcoes"] = range(11)
        contexto["valor_atual"] = (dados.get("respostas") or {}).get(pergunta.get("id"), "")
    return render(request, "cursos/satisfacao.html", contexto, status=status if status not in (200, 201) else 200)
