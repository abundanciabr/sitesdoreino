"""Diretório de alunos autenticados, com os perfis existentes da comunidade."""
import unicodedata

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import comunidade_entrada as comunidade
from .comunidade_seguidores import pessoa, resposta
from .comunidade_modelos import PerfilDaComunidade


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def corresponde(aluno, busca):
    termo = normalizar(busca)
    usuario = normalizar(aluno.get("usuario"))
    if termo.startswith("@"):
        return bool(usuario) and termo[1:] == usuario
    perfil = aluno.get("perfil")
    nomes = {normalizar(aluno.get("nome")), normalizar(perfil.nome if perfil else "")}
    return bool(termo) and (termo in nomes or (bool(usuario) and termo == usuario))


@require_GET
@never_cache
def pagina(request):
    dono = pessoa(request)
    if not dono:
        return resposta({"erro": "Entre com sua conta de aluno para conhecer a comunidade."}, 403)
    perfil = PerfilDaComunidade.objects.filter(
        site_host=comunidade._host(request), identidade_id=str(dono["id"])
    ).first()
    busca = str(request.GET.get("q") or "").strip()
    alunos = []
    if normalizar(busca):
        encontrados = comunidade._alunos(request)
        alunos = None if encontrados is None else [a for a in encontrados if corresponde(a, busca)]
    return comunidade._resposta(render(request, "admin/comunidade_alunos.html", {
        "perfil": perfil, "tema": perfil.tema if perfil else "apple",
        "alunos": alunos, "busca": busca, "pesquisou": bool(normalizar(busca)),
    }, status=503 if alunos is None else 200))


@require_GET
@never_cache
def interface(request, nome):
    if nome not in {"interface.css", "interface.js"}:
        raise Http404
    if not pessoa(request):
        return resposta({"erro": "Entre com sua conta de aluno."}, 403)
    arquivo = comunidade.ASSETS / ("alunos." + nome.rsplit(".", 1)[1])
    conteudo = arquivo.read_bytes()
    if nome.endswith(".css"):
        conteudo = (comunidade.ASSETS / "comunidade.css").read_bytes() + b"\n" + conteudo
    return comunidade._resposta(HttpResponse(conteudo, content_type="text/css" if nome.endswith(".css") else "application/javascript"))


@require_GET
@never_cache
def foto(request, alvo):
    if not pessoa(request):
        return resposta({"erro": "Entre com sua conta de aluno."}, 403)
    alunos = comunidade._alunos(request)
    if alunos is None:
        return resposta({"erro": "Não foi possível carregar a imagem agora."}, 503)
    aluno = next((a for a in alunos if a.get("seguir_chave") == alvo), None)
    perfil = aluno.get("perfil") if aluno else None
    if not perfil:
        raise Http404
    if perfil.foto:
        return comunidade._resposta(HttpResponse(bytes(perfil.foto), content_type="image/jpeg"))
    if perfil.avatar not in comunidade.AVATARES:
        raise Http404
    _, fundo, cor = comunidade.AVATARES[perfil.avatar]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160"><rect width="160" height="160" rx="80" fill="{fundo}"/><ellipse cx="80" cy="125" rx="38" ry="6" fill="{cor}" opacity=".12"/><path d="M80 31 119 55v46L80 125 41 101V55Z" fill="{cor}"/><path d="m80 31 39 24-39 24-39-24Z" fill="white" opacity=".35"/><path d="M80 79v46l39-24V55Z" fill="black" opacity=".12"/><path d="m65 47 15-9 20 12-15 9Z" fill="white" opacity=".65"/></svg>'
    return comunidade._resposta(HttpResponse(svg, content_type="image/svg+xml"))
