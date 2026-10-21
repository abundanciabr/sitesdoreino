"""Entrada da comunidade em construção; a votação dos alunos permanece no ar."""

import io
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .clients import AlunosClient, IdentidadeClient, IdentidadeIndisponivel, http
from .comunidade_modelos import PerfilDaComunidade
from .placar import site_de
from .porta import PortaAdministrativa, _emails_autorizados

TEMAS = [
    ("apple", "Apple"),
    ("premium", "Premium"),
    ("estudio", "Estúdio criativo"),
    ("gamificada", "Gamificada"),
    ("galeria", "Galeria de artistas"),
    ("acolhedora", "Acolhedora"),
    ("futurista", "Futurista"),
    ("minimalista", "Minimalista"),
    ("ultra-premium", "Ultra Premium"),
]
AVATARES = {
    "azul": ("Azul", "#dcecff", "#3778ed"),
    "violeta": ("Violeta", "#ece5ff", "#8060d0"),
    "coral": ("Coral", "#ffe6dc", "#e58364"),
    "verde": ("Verde", "#ddf1e8", "#4b9780"),
    "ambar": ("Âmbar", "#fff0cf", "#cca44b"),
    "grafite": ("Grafite", "#e8eaf0", "#616c86"),
}
ASSETS = Path(__file__).resolve().parent / "comunidade_assets"


def reconhecer_admin(request):
    guardado = getattr(request, "admin", None)
    if guardado and not guardado.get("equipe_apenas") and guardado.get("id"):
        return guardado
    local = PortaAdministrativa._admin_local_da_requisicao(request)
    if local and local.get("id"):
        request.admin = local
        return local
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return None
    try:
        sessao = IdentidadeClient().sessao_completa(cookie)
    except IdentidadeIndisponivel:
        return None
    request._comunidade_sessao = sessao
    email = str(sessao.get("email") or "").strip().lower()
    if not (
        sessao.get("autenticado")
        and sessao.get("id")
        and email in _emails_autorizados()
    ):
        return None
    request.admin = {
        "id": str(sessao["id"]),
        "email": email,
        "nome": str(sessao.get("nome_exibido") or "Admin"),
        "equipe_apenas": False,
    }
    return request.admin


def _admin(request):
    admin = reconhecer_admin(request)
    if not admin:
        raise Http404
    return admin


def _dono(request):
    dono = getattr(request, "_comunidade_participante", None)
    if dono and dono.get("id") and dono.get("email"):
        return dono
    return _admin(request)


def _host(request):
    return request.get_host().split(":")[0].lower()


def _perfil(request):
    admin = _dono(request)
    return PerfilDaComunidade.objects.filter(
        site_host=_host(request), identidade_id=str(admin["id"])
    ).first()


def _resposta(resposta):
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data: blob:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )
    return resposta


def _configurar(request, erro="", status=200, usuario="", avatar=""):
    perfil = _perfil(request)
    return _resposta(
        render(
            request,
            getattr(request, "_comunidade_template_perfil", "admin/comunidade_perfil.html"),
            {
                "perfil": perfil,
                "nome": request.POST.get("nome", perfil.nome if perfil else str(_dono(request).get("nome") or "").split(" ")[0]),
                "usuario": usuario or (perfil.usuario if perfil else ""),
                "avatar": avatar or (perfil.avatar if perfil else ""),
                "avatares": [{"id": a, "nome": v[0]} for a, v in AVATARES.items()],
                "erro": erro,
            },
            status=status,
        )
    )


def _alunos(request):
    site = site_de(request)
    if not site:
        return None
    linhas = AlunosClient().alunos(status="ativa")
    if linhas is None:
        return None
    admins = _emails_autorizados()
    unicos = {}
    for linha in linhas:
        email = str(linha.get("email") or "").strip().lower()
        if (
            str(linha.get("site_id")) != str(site)
            or linha.get("status") != "ativa"
            or linha.get("origem") == "teste"
            or not email
            or email in admins
        ):
            continue
        partes = str(linha.get("nome_completo") or "").split()
        nome = partes[0] if partes and "@" not in partes[0] else "Aluno"
        unicos.setdefault(email, {"nome": nome, "inicial": nome[0].upper()})
    perfis = {
        p.email: p for p in PerfilDaComunidade.objects.filter(site_host=_host(request))
    }
    from .comunidade_seguidores import chave
    for email, item in unicos.items():
        item["seguir_chave"] = chave(_host(request), email)
        perfil = perfis.get(email)
        item["perfil"] = perfil
        item["usuario"] = perfil.usuario if perfil else ""
    return sorted(unicos.values(), key=lambda a: a["nome"].casefold())


def _forum(request):
    base = (
        str(os.environ.get("FORUM_API_URL") or "").rstrip("/").removesuffix("/interno")
    )
    if not base:
        return None
    try:
        resposta = http().get(
            base + "/comunidade/quem-ajuda/dados/",
            headers={
                "Cookie": request.META.get("HTTP_COOKIE", ""),
                "Authorization": "Bearer " + str(os.environ.get("TOKEN_FORUM") or ""),
            },
            timeout=5,
        )
        dados = resposta.json() if resposta.status_code == 200 else None
        if not isinstance(dados, dict) or not isinstance(dados.get("ranking"), list):
            return None
        for item in [*dados.get("conversas", []), *dados.get("grupos", [])]:
            url = str(item.get("url") or "")
            if url.startswith(("/t/", "/a/")):
                item["url"] = "/forum" + url
        return dados
    except (httpx.HTTPError, ValueError):
        return None


@require_GET
@never_cache
def percurso_aluno(request):
    """Mesma interface ensaiada, em página completa exclusiva de administradores."""
    _admin(request)
    return _resposta(HttpResponse((ASSETS / "percurso.html").read_text(encoding="utf-8")))


@require_GET
@never_cache
def alunos_atual(request):
    """Leitura administrativa do visual vigente dos alunos, sem votar por eles."""
    _admin(request)
    from .galeria_comunidade import classificacao
    return _resposta(render(request, "admin/galeria_publica.html", {
        "imagens": classificacao(),
        "aluno": {"nome": "Aluno · visual atual"},
        "somente_leitura": True,
    }))


def entrada(request):
    _dono(request)
    perfil = _perfil(request)
    if not perfil or request.GET.get("perfil") == "editar":
        return _configurar(request)
    forum = _forum(request)
    contexto = {
        "perfil": perfil,
        "temas": TEMAS,
        "forum": forum,
        "ranking": (forum or {}).get("ranking", []),
        "grupos": (forum or {}).get("grupos", []),
    }
    return _resposta(render(request, getattr(request, "_comunidade_template", "admin/comunidade_apple.html"), contexto))


@require_POST
@never_cache
def salvar_perfil(request):
    admin = _dono(request)
    usuario = str(request.POST.get("usuario") or "").strip().lstrip("@").lower()
    avatar = str(request.POST.get("avatar") or "")
    existente = _perfil(request)
    nome = " ".join(str(request.POST.get("nome", existente.nome if existente else str(admin.get("nome") or "").split(" ")[0])).split())
    if not nome or len(nome) > 120:
        return _configurar(request, "Informe seu nome na comunidade, com até 120 caracteres.", 400, usuario, avatar)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.]{0,31}", usuario):
        return _configurar(
            request,
            "Escolha seu @ usando letras, números, ponto ou sublinhado.",
            400,
            usuario,
            avatar,
        )
    foto = None
    enviado = request.FILES.get("foto")
    if enviado:
        if enviado.size > 4 * 1024 * 1024:
            return _configurar(
                request, "Escolha uma imagem de até 4 MB.", 400, usuario, avatar
            )
        try:
            from PIL import Image, ImageOps

            with Image.open(io.BytesIO(enviado.read())) as imagem:
                if (
                    imagem.format not in {"PNG", "JPEG", "WEBP"}
                    or imagem.width * imagem.height > 20000000
                ):
                    raise ValueError()
                imagem = ImageOps.exif_transpose(imagem)
                imagem = ImageOps.fit(imagem.convert("RGB"), (320, 320))
                saida = io.BytesIO()
                imagem.save(saida, "JPEG", quality=88)
                foto = saida.getvalue()
        except (ValueError, OSError, Image.DecompressionBombError):
            return _configurar(
                request,
                "Não consegui abrir a imagem. Use PNG, JPG ou WebP.",
                400,
                usuario,
                avatar,
            )
    elif avatar not in AVATARES and not (existente and existente.foto):
        return _configurar(
            request,
            "Escolha uma imagem de perfil ou envie sua foto.",
            400,
            usuario,
            avatar,
        )
    valores = {
        "usuario": usuario,
        "nome": nome[:120],
        "email": str(admin.get("email") or "").lower(),
    }
    if foto is not None:
        valores.update(foto=foto, avatar="")
    elif avatar in AVATARES:
        valores.update(avatar=avatar, foto=b"")
    try:
        with transaction.atomic():
            PerfilDaComunidade.objects.update_or_create(
                site_host=_host(request),
                identidade_id=str(admin["id"]),
                defaults=valores,
            )
    except IntegrityError:
        return _configurar(
            request, "Esse @ já está em uso. Escolha outro nome.", 409, usuario, avatar
        )
    return _resposta(HttpResponseRedirect(getattr(request, "_comunidade_raiz", "/comunidade")))


@require_POST
@never_cache
def salvar_tema(request):
    perfil = _perfil(request)
    tema = request.POST.get("tema")
    if not perfil or tema not in dict(TEMAS):
        raise Http404
    perfil.tema = tema
    perfil.save(update_fields=["tema", "atualizado_em"])
    return _resposta(HttpResponseRedirect(getattr(request, "_comunidade_raiz", "/comunidade")))


@require_GET
@never_cache
def disponibilidade(request):
    admin = _dono(request)
    usuario = str(request.GET.get("usuario") or "").strip().lstrip("@").lower()
    existe = (
        PerfilDaComunidade.objects.filter(site_host=_host(request), usuario=usuario)
        .exclude(identidade_id=str(admin["id"]))
        .exists()
    )
    return _resposta(
        JsonResponse(
            {
                "disponivel": bool(re.fullmatch(r"[a-z0-9][a-z0-9_.]{0,31}", usuario))
                and not existe
            }
        )
    )


@require_GET
@never_cache
def foto(request, perfil_id):
    _dono(request)
    perfil = PerfilDaComunidade.objects.filter(
        pk=perfil_id, site_host=_host(request)
    ).first()
    if not perfil:
        raise Http404
    if perfil.foto:
        return _resposta(HttpResponse(bytes(perfil.foto), content_type="image/jpeg"))
    return avatar(request, perfil.avatar)


@require_GET
@never_cache
def avatar(request, escolha):
    _dono(request)
    if escolha not in AVATARES:
        raise Http404
    _, fundo, cor = AVATARES[escolha]
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160"><rect width="160" height="160" rx="80" fill="{fundo}"/><ellipse cx="80" cy="125" rx="38" ry="6" fill="{cor}" opacity=".12"/><path d="M80 31 119 55v46L80 125 41 101V55Z" fill="{cor}"/><path d="m80 31 39 24-39 24-39-24Z" fill="white" opacity=".35"/><path d="M80 79v46l39-24V55Z" fill="black" opacity=".12"/><path d="m65 47 15-9 20 12-15 9Z" fill="white" opacity=".65"/></svg>'
    return _resposta(HttpResponse(svg, content_type="image/svg+xml"))


@require_GET
@never_cache
def recurso(request, nome):
    _admin(request)
    if nome == "hero.png":
        caminho = Path(__file__).resolve().parent / "feed_previa_assets" / "hero.png"
        tipo = "image/png"
    elif nome in {"comunidade.css", "comunidade.js", "percurso.css", "percurso.js"}:
        caminho = ASSETS / nome
        tipo = "text/css" if nome.endswith(".css") else "application/javascript"
    else:
        raise Http404
    return _resposta(HttpResponse(caminho.read_bytes(), content_type=tipo))
