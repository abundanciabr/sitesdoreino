"""Um clique no link aprovado abre a sessão; visitas renovam o cookie."""
import os
import httpx
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_GET
from . import sessao

PRAZO_SESSAO = 400 * 24 * 60 * 60

def _privada(resposta):
    resposta["Cache-Control"] = "no-store"
    # O POST automático precisa conservar a origem para a conferência CSRF.
    # O segredo fica no fragmento e é removido antes do envio do formulário.
    resposta["Referrer-Policy"] = "same-origin"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta

@require_http_methods(["GET", "POST"])
def entrar(request):
    if request.method == "GET":
        return _privada(render(request, "identidade/acesso_escola.html"))
    base = (os.environ.get("ALUNOS_API_URL") or "http://alunos:8000/api/alunos").rstrip("/")
    try:
        r = httpx.post(base+"/acesso-escola/consumir", json={"token": request.POST.get("token", "")},
            timeout=8)
    except httpx.HTTPError:
        return _privada(HttpResponse("Não foi possível abrir o acesso agora. Tente novamente.", status=503))
    if r.status_code != 200:
        return _privada(HttpResponse("Este link não está disponível ou já foi utilizado. Se já entrou neste navegador, abra a escola. Para outro acesso, fale com o suporte.", status=400))
    dados = r.json()
    if sessao.e_staff(dados["email"]):
        return _privada(HttpResponse("Use a entrada habitual da equipe.", status=403))
    pessoa = sessao.cunhar_ou_recuperar(email=dados["email"], nome=dados["nome"], site_id=dados["site_id"])
    sessao.abrir_sessao(request, pessoa)
    request.session["acesso_escola_persistente"] = True
    request.session.set_expiry(PRAZO_SESSAO)
    return _privada(HttpResponseRedirect("/"))

@require_GET
def manter(request):
    if request.session.get("acesso_escola_persistente") and sessao.ator_atual(request):
        request.session.set_expiry(PRAZO_SESSAO)
        request.session.modified = True
    return _privada(HttpResponse("", content_type="text/plain"))
