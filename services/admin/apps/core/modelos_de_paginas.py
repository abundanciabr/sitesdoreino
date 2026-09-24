"""Editor da FLP: o texto mora no catálogo, e publicar é um gesto separado."""

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient
from .views import _auditar

SLUG = "flp-0"
SECOES = (
    (
        "abertura",
        "Abertura",
        ("headline", "subheadline", "cta_texto", "cta_destino", "imagem"),
    ),
    (
        "entrega",
        "O que recebe",
        ("headline", "dashboard", "skills_ia", "checklists", "playbook"),
    ),
    ("convite", "Convite", ("headline", "texto", "cta_texto", "cta_destino")),
    ("prova", "Prova", ("headline", "texto")),
    ("perguntas", "Perguntas", ("headline", "perguntas")),
)


def _site(request):
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


def _ler(site):
    situacao, corpo = CatalogoClient().rascunho_da_pagina(site["id"], SLUG)
    if situacao == CatalogoClient.SEM_RASCUNHO:
        return {}, 0
    if situacao != CatalogoClient.OK or corpo.get("tipo") != "flp":
        return None
    secoes = corpo.get("secoes")
    versao = corpo.get("base_version")
    if (
        not isinstance(secoes, list)
        or isinstance(versao, bool)
        or not isinstance(versao, int)
        or versao < 0
        or any(
            not isinstance(secao, dict)
            or not isinstance(secao.get("nome"), str)
            or not isinstance(secao.get("slots"), dict)
            or any(not isinstance(valor, str) for valor in secao["slots"].values())
            for secao in secoes
        )
    ):
        return None
    return {secao["nome"]: secao["slots"] for secao in secoes}, versao


def _campos(escritos):
    return [
        {
            "nome": nome,
            "titulo": titulo,
            "preenchida": bool(escritos.get(nome)),
            "campos": [
                {
                    "chave": f"{nome}.{slot}",
                    "titulo": slot.replace("_", " ").capitalize(),
                    "valor": escritos.get(nome, {}).get(slot, ""),
                }
                for slot in slots
            ],
        }
        for nome, titulo, slots in SECOES
    ]


def _mostrar(
    request, escritos=None, *, versao=0, erro="", estado="", status=200, previa=False
):
    return render(
        request,
        "admin/modelos_de_paginas.html",
        {
            "admin": request.admin,
            "secoes": _campos(escritos or {}) if escritos is not None else None,
            "versao": versao,
            "erro": erro,
            "estado": estado,
            "previa": previa,
        },
        status=status,
    )


@require_GET
def modelos_de_paginas(request):
    return render(
        request,
        "admin/modelos_de_paginas.html",
        {"admin": request.admin, "lista": True},
    )


@require_GET
def modelo_flp_editar(request):
    site = _site(request)
    if site is None:
        return _mostrar(
            request,
            erro="O catálogo não respondeu. Recarregue a página antes de editar.",
            status=503,
        )
    lido = _ler(site)
    if lido is None:
        return _mostrar(
            request,
            erro="Não consegui ler o rascunho. Recarregue a página antes de editar.",
            status=503,
        )
    escritos, versao = lido
    return _mostrar(
        request, escritos, versao=versao, estado=request.GET.get("estado", "")
    )


def _do_formulario(post):
    return {
        nome: {
            slot: texto
            for slot in slots
            if (texto := (post.get(f"{nome}.{slot}") or "").strip())
        }
        for nome, _, slots in SECOES
    }


def _para_catalogo(escritos):
    return [
        {"nome": nome, "ordem": ordem, "slots": escritos[nome]}
        for ordem, (nome, _, _) in enumerate(SECOES)
        if escritos[nome]
    ]


@require_POST
def modelo_flp_salvar(request):
    escritos = _do_formulario(request.POST)
    site = _site(request)
    if site is None:
        _auditar(
            request,
            Registro.SALVAR_RASCUNHO_DA_PAGINA,
            SLUG,
            Registro.NAO_RESPONDEU,
            "site não encontrado",
        )
        return _mostrar(
            request,
            escritos,
            erro="O catálogo não respondeu. Seu texto está abaixo; tente salvar de novo.",
            status=503,
        )
    situacao, resposta = CatalogoClient().gravar_rascunho_da_pagina(
        site["id"], SLUG, _para_catalogo(escritos), tipo="flp"
    )
    if situacao == CatalogoClient.OK and (
        resposta.get("slug") != SLUG or resposta.get("tipo") != "flp"
    ):
        situacao, resposta = (
            CatalogoClient.NAO_RESPONDEU,
            "o catálogo devolveu outra página",
        )
    _auditar(
        request,
        Registro.SALVAR_RASCUNHO_DA_PAGINA,
        SLUG,
        (
            Registro.OK
            if situacao == CatalogoClient.OK
            else (
                Registro.RECUSADO_PELA_CELULA
                if situacao == CatalogoClient.RECUSADO
                else Registro.NAO_RESPONDEU
            )
        ),
        f"{SLUG}: {sum(len(valores) for valores in escritos.values())} campos",
    )
    if situacao == CatalogoClient.OK:
        return HttpResponseRedirect(f"{reverse('modelo_flp_editar')}?estado=salvo")
    return _mostrar(
        request,
        escritos,
        erro=f"Não salvei: {resposta}. Seu texto continua nos campos; corrija e tente de novo.",
        status=422 if situacao == CatalogoClient.RECUSADO else 503,
    )


@require_POST
def modelo_flp_publicar(request):
    site = _site(request)
    if site is None:
        _auditar(
            request,
            Registro.PUBLICAR_PAGINA,
            SLUG,
            Registro.NAO_RESPONDEU,
            "site não encontrado",
        )
        return _mostrar(
            request,
            erro="O catálogo não respondeu. Tente publicar de novo mais tarde.",
            status=503,
        )
    situacao, resposta = CatalogoClient().publicar_pagina(site["id"], SLUG)
    if situacao == CatalogoClient.OK and (
        resposta.get("slug") != SLUG
        or resposta.get("tipo") != "flp"
        or isinstance(resposta.get("version"), bool)
        or not isinstance(resposta.get("version"), int)
        or resposta["version"] < 1
    ):
        situacao, resposta = (
            CatalogoClient.NAO_RESPONDEU,
            "o catálogo devolveu outra página",
        )
    _auditar(
        request,
        Registro.PUBLICAR_PAGINA,
        SLUG,
        (
            Registro.OK
            if situacao == CatalogoClient.OK
            else (
                Registro.RECUSADO_PELA_CELULA
                if situacao in (CatalogoClient.VAZIO, CatalogoClient.SEM_PAGINA)
                else Registro.NAO_RESPONDEU
            )
        ),
        (
            f"{SLUG}: versão {resposta.get('version')}"
            if situacao == CatalogoClient.OK
            else f"{SLUG}: {resposta}"
        ),
    )
    if situacao == CatalogoClient.OK:
        return HttpResponseRedirect(f"{reverse('modelo_flp_editar')}?estado=publicado")
    lido = _ler(site)
    return _mostrar(
        request,
        lido[0] if lido is not None else None,
        versao=lido[1] if lido is not None else 0,
        erro=(
            "Não publiquei: salve pelo menos um campo e tente de novo."
            if situacao == CatalogoClient.VAZIO
            else "Não consegui publicar. O rascunho continua salvo; tente de novo mais tarde."
        ),
        status=409 if situacao == CatalogoClient.VAZIO else 503,
    )


@require_GET
def modelo_flp_previa(request):
    site = _site(request)
    if site is None:
        return _mostrar(
            request,
            erro="O catálogo não respondeu. Tente abrir a prévia de novo.",
            status=503,
        )
    lido = _ler(site)
    if lido is None:
        return _mostrar(
            request,
            erro="Não consegui ler o rascunho. Tente abrir a prévia de novo.",
            status=503,
        )
    escritos, versao = lido
    if not any(escritos.values()):
        return _mostrar(
            request,
            escritos,
            erro="A prévia está vazia. Escreva e salve um campo antes de abrir.",
            status=404,
        )
    return _mostrar(request, escritos, versao=versao, previa=True)
