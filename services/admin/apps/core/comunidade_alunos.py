"""Comunidade acessível por endereço próprio, sem anunciar o link aos alunos."""
from pathlib import Path
from urllib.parse import quote

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import comunidade_entrada as entrada
from .clients import IdentidadeClient, IdentidadeIndisponivel, AlunosClient
from .comunidade_modelos import PerfilDaComunidade
from .placar import site_de
from .porta import _emails_autorizados

BASE = "/comunidade/nova-20261014"
INTERNO = "/galeria-publica/nova-20261014"


def caminho_publico(caminho):
    if caminho == INTERNO or caminho == INTERNO + "/":
        return True
    partes = caminho.removeprefix(INTERNO + "/").split("/")
    if not caminho.startswith(INTERNO + "/"):
        return False
    return (
        partes in [["perfil"], ["tema"], ["disponivel"]]
        or len(partes) == 2 and partes[0] in {"foto", "avatar", "assets"}
    )


def participante(request):
    if hasattr(request, "_comunidade_participante"):
        return request._comunidade_participante
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return None
    try:
        sessao = IdentidadeClient().sessao_completa(cookie)
    except IdentidadeIndisponivel:
        return None
    if not sessao.get("autenticado") or not sessao.get("id") or not sessao.get("email"):
        return None
    request._comunidade_participante = {
        "id": str(sessao["id"]),
        "email": str(sessao["email"]).strip().lower(),
        "nome": str(sessao.get("nome_exibido") or "Participante"),
    }
    return request._comunidade_participante


def preparar(request):
    dono = participante(request)
    if not dono:
        return None
    # Este contexto não é request.admin e não concede poderes administrativos.
    request._comunidade_raiz = BASE
    request._comunidade_template = "admin/comunidade_aluno.html"
    request._comunidade_template_perfil = "admin/comunidade_aluno_perfil.html"
    return dono


def diretorio(request):
    """Só perfis escolhidos pelas próprias pessoas; nunca a lista privada da escola."""
    dono = participante(request)
    site = site_de(request)
    if not dono or not site:
        return []
    linhas = AlunosClient().alunos(status="ativa")
    if linhas is None:
        return None
    admins = _emails_autorizados()
    ativos = {
        str(l.get("email") or "").strip().lower()
        for l in linhas
        if str(l.get("site_id")) == str(site)
        and l.get("status") == "ativa"
        and l.get("origem") != "teste"
    }
    if dono["email"] not in ativos and dono["email"] not in admins:
        return []
    perfis = PerfilDaComunidade.objects.filter(
        site_host=entrada._host(request), email__in=ativos
    ).exclude(email__in=admins).order_by("nome", "usuario")
    return [
        {"nome": p.nome, "inicial": p.nome[:1].upper(), "usuario": p.usuario, "perfil": p}
        for p in perfis
    ]


def entrar():
    return entrada._resposta(HttpResponseRedirect("/login?next=" + quote(BASE, safe="/")))


@require_GET
@never_cache
def pagina(request):
    if not preparar(request):
        return entrada._resposta(render(request, "admin/comunidade_chegada.html", {"base": BASE}))
    request._comunidade_alunos = diretorio(request)
    return entrada.entrada(request)


@require_POST
@never_cache
def salvar_perfil(request):
    return entrada.salvar_perfil(request) if preparar(request) else entrar()


@require_POST
@never_cache
def salvar_tema(request):
    return entrada.salvar_tema(request) if preparar(request) else entrar()


@require_GET
@never_cache
def disponibilidade(request):
    return entrada.disponibilidade(request) if preparar(request) else entrar()


@require_GET
@never_cache
def foto(request, perfil_id):
    dono = preparar(request)
    if not dono:
        raise Http404
    perfil = PerfilDaComunidade.objects.filter(pk=perfil_id, site_host=entrada._host(request)).first()
    if not perfil:
        raise Http404
    if perfil.identidade_id != dono["id"]:
        permitidos = diretorio(request) or []
        if not any(item["perfil"].pk == perfil.pk for item in permitidos):
            raise Http404
    return entrada.foto(request, perfil_id)


@require_GET
@never_cache
def avatar(request, escolha):
    if escolha not in entrada.AVATARES:
        raise Http404
    _, fundo, cor = entrada.AVATARES[escolha]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160"><rect width="160" height="160" rx="80" fill="{fundo}"/><path d="M80 31 119 55v46L80 125 41 101V55Z" fill="{cor}"/><path d="m80 31 39 24-39 24-39-24Z" fill="white" opacity=".35"/><path d="M80 79v46l39-24V55Z" fill="black" opacity=".12"/></svg>'
    return entrada._resposta(HttpResponse(svg, content_type="image/svg+xml"))


@require_GET
@never_cache
def recurso(request, nome):
    if nome == "hero.png":
        caminho = Path(entrada.__file__).resolve().parent / "feed_previa_assets" / nome
        tipo = "image/png"
    elif nome in {"comunidade.css", "comunidade.js"}:
        caminho = entrada.ASSETS / nome
        tipo = "text/css" if nome.endswith(".css") else "application/javascript"
    else:
        raise Http404
    return entrada._resposta(HttpResponse(caminho.read_bytes(), content_type=tipo))
