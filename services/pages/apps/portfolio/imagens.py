"""Recepção e entrega de imagens próprias do portfólio."""

from __future__ import annotations

from io import BytesIO
import warnings

from django.db import models, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import EstadoDoLink, ImagemDoPortfolio, MaterialDaPeca, Peca, Portfolio

LIMITE_ORIGINAL = 5 * 1024 * 1024
LIMITE_PIXELS = 20_000_000
LIMITE_LADO = 1920
LIMITE_WEBP = 2 * 1024 * 1024
LIMITE_PORTFOLIO = 50 * 1024 * 1024
FORMATOS = frozenset({"JPEG", "PNG", "WEBP"})


from .normalizacao import _normalizar, ImagemRecusada


def guardar(
    arquivo, *, site_id: str, aluno_id: str, legenda: str, base_url: str
) -> Peca:
    """Grava a peça e seus bytes em uma única transação, sob bloqueio do portfólio."""
    if not site_id or not aluno_id or not base_url:
        raise ImagemRecusada("Não foi possível identificar a escola ou o aluno.")
    legenda = (legenda or "").strip()
    if len(legenda) > 200:
        raise ImagemRecusada("A legenda deve ter até 200 caracteres.")
    dados, largura, altura = _normalizar(arquivo)

    with transaction.atomic():
        Portfolio.objects.get_or_create(site_id=site_id, aluno_id=aluno_id)
        portfolio = Portfolio.objects.select_for_update().get(
            site_id=site_id, aluno_id=aluno_id
        )
        from .vitrine import garantir_publicacao_legada
        garantir_publicacao_legada(portfolio)
        usado = _uso_do_portfolio(portfolio)
        if usado + len(dados) > LIMITE_PORTFOLIO:
            raise ImagemRecusada(
                "Este portfólio atingiu o limite de 50 MiB em imagens."
            )
        ordem = (
            Peca.todas.filter(portfolio=portfolio).aggregate(ultima=models.Max("ordem"))["ultima"] or 0
        ) + 1
        imagem = ImagemDoPortfolio(
            tamanho=len(dados), largura=largura, altura=altura, bytes=dados
        )
        link = base_url.rstrip("/") + "/portfolio/imagens/" + str(imagem.id)
        peca = Peca.objects.create(
            portfolio=portfolio,
            link=link,
            legenda=legenda,
            ordem=ordem,
            estado_do_link=EstadoDoLink.RESPONDENDO,
            conferido_em=timezone.now(),
        )
        imagem.peca = peca
        imagem.save()
        return peca


def _peca_do_aluno(*, site_id, aluno_id, peca_id):
    try:
        return Peca.objects.do_aluno(site_id=site_id, aluno_id=aluno_id).select_related("portfolio").get(pk=peca_id)
    except (Peca.DoesNotExist, ValueError, TypeError) as exc:
        raise ImagemRecusada("Trabalho não encontrado para este aluno e site.") from exc


def _uso_do_portfolio(portfolio):
    antigo = ImagemDoPortfolio.objects.filter(peca__portfolio=portfolio).aggregate(total=models.Sum("tamanho"))["total"] or 0
    novos = MaterialDaPeca.objects.filter(peca__portfolio=portfolio).aggregate(total=models.Sum("tamanho"))["total"] or 0
    return antigo + novos


def adicionar_material(arquivo, *, site_id: str, aluno_id: str, peca_id: int,
                       categoria: str = "render", legenda: str = "", principal: bool = False) -> MaterialDaPeca:
    if categoria not in MaterialDaPeca.Categoria.values:
        raise ImagemRecusada("Escolha render, vistas, wireframe ou UV.")
    legenda = (legenda or "").strip()
    if len(legenda) > 200:
        raise ImagemRecusada("A legenda deve ter até 200 caracteres.")
    dados, largura, altura = _normalizar(arquivo)
    with transaction.atomic():
        peca = _peca_do_aluno(site_id=site_id, aluno_id=aluno_id, peca_id=peca_id)
        Portfolio.objects.select_for_update().get(pk=peca.portfolio_id)
        from .vitrine import garantir_publicacao_legada
        garantir_publicacao_legada(peca.portfolio)
        if _uso_do_portfolio(peca.portfolio) + len(dados) > LIMITE_PORTFOLIO:
            raise ImagemRecusada("Este portfólio atingiu o limite de 50 MiB em imagens.")
        ordem = (peca.materiais.aggregate(ultima=models.Max("ordem"))["ultima"] or 0) + 1
        if principal:
            peca.materiais.filter(substituido_por__isnull=True, principal=True).update(principal=False)
        return MaterialDaPeca.objects.create(
            peca=peca, categoria=categoria, legenda=legenda, ordem=ordem,
            principal=bool(principal), tamanho=len(dados), largura=largura,
            altura=altura, bytes=dados,
        )


@transaction.atomic
def editar_material(*, site_id: str, aluno_id: str, peca_id: int, imagem_id,
                    categoria=None, legenda=None, ordem=None, principal=None) -> MaterialDaPeca:
    peca = _peca_do_aluno(site_id=site_id, aluno_id=aluno_id, peca_id=peca_id)
    try:
        material = peca.materiais.get(pk=imagem_id, substituido_por__isnull=True)
    except (MaterialDaPeca.DoesNotExist, ValueError, TypeError) as exc:
        raise ImagemRecusada("Imagem não encontrada neste trabalho.") from exc
    from .vitrine import garantir_publicacao_legada
    garantir_publicacao_legada(peca.portfolio)
    campos = []
    if categoria is not None:
        if categoria not in MaterialDaPeca.Categoria.values:
            raise ImagemRecusada("Escolha render, vistas, wireframe ou UV.")
        material.categoria = categoria
        campos.append("categoria")
    if legenda is not None:
        if not isinstance(legenda, str) or len(legenda.strip()) > 200:
            raise ImagemRecusada("A legenda deve ter até 200 caracteres.")
        material.legenda = legenda.strip()
        campos.append("legenda")
    if ordem is not None:
        try:
            valor = int(ordem)
        except (ValueError, TypeError) as exc:
            raise ImagemRecusada("A ordem da imagem deve ser um número positivo.") from exc
        if valor < 1:
            raise ImagemRecusada("A ordem da imagem deve ser um número positivo.")
        material.ordem = valor
        campos.append("ordem")
    if principal is not None:
        if principal:
            peca.materiais.filter(substituido_por__isnull=True, principal=True).exclude(pk=material.pk).update(principal=False)
        material.principal = bool(principal)
        campos.append("principal")
    if campos:
        material.save(update_fields=campos)
    return material


def substituir_material(arquivo, *, site_id: str, aluno_id: str, peca_id: int, imagem_id) -> MaterialDaPeca:
    """Nova URL para novos bytes; a URL antiga continua válida no publicado."""
    dados, largura, altura = _normalizar(arquivo)
    with transaction.atomic():
        peca = _peca_do_aluno(site_id=site_id, aluno_id=aluno_id, peca_id=peca_id)
        Portfolio.objects.select_for_update().get(pk=peca.portfolio_id)
        try:
            antigo = peca.materiais.get(pk=imagem_id, substituido_por__isnull=True)
        except (MaterialDaPeca.DoesNotExist, ValueError, TypeError) as exc:
            raise ImagemRecusada("Imagem não encontrada neste trabalho.") from exc
        from .vitrine import garantir_publicacao_legada
        garantir_publicacao_legada(peca.portfolio)
        if _uso_do_portfolio(peca.portfolio) + len(dados) > LIMITE_PORTFOLIO:
            raise ImagemRecusada("Este portfólio atingiu o limite de 50 MiB em imagens.")
        novo = MaterialDaPeca.objects.create(
            peca=peca, categoria=antigo.categoria, legenda=antigo.legenda,
            ordem=antigo.ordem, principal=antigo.principal,
            selecionado_publicacao=antigo.selecionado_publicacao,
            tamanho=len(dados), largura=largura, altura=altura, bytes=dados,
        )
        antigo.substituido_por = novo
        antigo.save(update_fields=["substituido_por"])
        return novo


def imagem_do_portfolio(imagem_id, portfolio=None):
    imagem = ImagemDoPortfolio.objects.select_related("peca__portfolio").filter(pk=imagem_id).first()
    if imagem is None:
        imagem = MaterialDaPeca.objects.select_related("peca__portfolio").filter(pk=imagem_id).first()
    if imagem is not None and portfolio is not None and imagem.peca.portfolio_id != portfolio.pk:
        return None
    return imagem


def _recusa() -> HttpResponse:
    resposta = HttpResponse(status=404)
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@require_GET
def servir_imagem(request, imagem_id):
    """A vitrine publicada é pública; o rascunho exige dono ativo ou equipe."""
    from apps.core.clients import (
        AdminIndisponivel,
        AlunosClient,
        AlunosIndisponivel,
        ConfiguracaoAusente,
        IdentidadeClient,
        IdentidadeIndisponivel,
    )
    from apps.core.equipe import e_da_equipe
    from apps.core.views import site_atual

    site_id = site_atual()
    imagem = imagem_do_portfolio(imagem_id) if site_id else None
    if imagem is not None and imagem.peca.portfolio.site_id != site_id:
        imagem = None
    if imagem is None:
        return _recusa()
    portfolio = imagem.peca.portfolio
    from .vitrine import dados_publicados
    snapshot = dados_publicados(portfolio)
    if snapshot is not None:
        publica = portfolio.vitrine_publicada and str(imagem.pk) in snapshot.get("imagens_ids", [])
    else:
        publica = portfolio.vitrine_publicada and isinstance(imagem, ImagemDoPortfolio) and imagem.peca.mostrar_na_pagina_publica
    if snapshot is None and portfolio.vitrine_publicada and not publica:
        from .comercial import provas_de
        # Uma prova escolhida para uma peça pública pertence ao mesmo portfólio.
        publica = any(
            prova["link"] == imagem.peca.link
            for obra in portfolio.pecas.filter(mostrar_na_pagina_publica=True)
            for prova in provas_de(obra.provas_comerciais)
        )
    if not publica:
        cookie = request.META.get("HTTP_COOKIE", "")
        if not cookie:
            return _recusa()
        try:
            sessao = IdentidadeClient().sessao_completa(cookie)
            if (
                not sessao.get("autenticado")
                or not sessao.get("id")
                or not sessao.get("email")
            ):
                return _recusa()
            email = sessao["email"].strip().lower()
            from .colegas import compartilha_imagem
            compartilhada = compartilha_imagem(portfolio, imagem.pk)
            categoria = AlunosClient().categoria_de(email) if sessao["id"] == portfolio.aluno_id or compartilhada else None
            dono = sessao["id"] == portfolio.aluno_id and categoria == "aluno"
            colega = categoria == "aluno" and compartilhada
            if not dono and not colega and not e_da_equipe(email):
                return _recusa()
        except (
            IdentidadeIndisponivel,
            AlunosIndisponivel,
            AdminIndisponivel,
            ConfiguracaoAusente,
            KeyError,
            TypeError,
            AttributeError,
        ):
            return _recusa()
    resposta = HttpResponse(imagem.bytes, content_type="image/webp")
    resposta["Cache-Control"] = "no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
