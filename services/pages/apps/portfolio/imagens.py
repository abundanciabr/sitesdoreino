"""Recepção e entrega de imagens próprias do portfólio."""

from __future__ import annotations

from io import BytesIO
import warnings

from django.db import models, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import EstadoDoLink, ImagemDoPortfolio, Peca, Portfolio

LIMITE_ORIGINAL = 5 * 1024 * 1024
LIMITE_PIXELS = 20_000_000
LIMITE_LADO = 1920
LIMITE_WEBP = 2 * 1024 * 1024
LIMITE_PORTFOLIO = 50 * 1024 * 1024
FORMATOS = frozenset({"JPEG", "PNG", "WEBP"})


class ImagemRecusada(ValueError):
    """Recusa apresentável ao aluno, sem detalhes do decodificador."""


def _normalizar(arquivo) -> tuple[bytes, int, int]:
    if arquivo is None:
        raise ImagemRecusada("Escolha uma imagem JPEG, PNG ou WebP.")
    if getattr(arquivo, "size", 0) > LIMITE_ORIGINAL:
        raise ImagemRecusada("A imagem deve ter até 5 MiB.")

    conteudo = bytearray()
    try:
        pedacos = (
            arquivo.chunks()
            if hasattr(arquivo, "chunks")
            else iter(lambda: arquivo.read(64 * 1024), b"")
        )
        for pedaco in pedacos:
            conteudo.extend(pedaco)
            if len(conteudo) > LIMITE_ORIGINAL:
                raise ImagemRecusada("A imagem deve ter até 5 MiB.")
    except ImagemRecusada:
        raise
    except (OSError, ValueError) as erro:
        raise ImagemRecusada("Não foi possível ler a imagem enviada.") from erro
    if not conteudo:
        raise ImagemRecusada("Escolha uma imagem JPEG, PNG ou WebP.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(conteudo)) as origem:
                if origem.format not in FORMATOS or getattr(origem, "n_frames", 1) != 1:
                    raise ImagemRecusada(
                        "Envie uma imagem JPEG, PNG ou WebP sem animação."
                    )
                largura, altura = origem.size
                if not largura or not altura or largura * altura > LIMITE_PIXELS:
                    raise ImagemRecusada(
                        "A imagem deve ter no máximo 20 milhões de pixels."
                    )
                origem.verify()
            with Image.open(BytesIO(conteudo)) as origem:
                origem.load()
                imagem = ImageOps.exif_transpose(origem)
                imagem.thumbnail((LIMITE_LADO, LIMITE_LADO), Image.Resampling.LANCZOS)
                imagem = imagem.convert(
                    "RGBA"
                    if "A" in imagem.getbands() or "transparency" in imagem.info
                    else "RGB"
                )
                saida = BytesIO()
                imagem.save(saida, format="WEBP", quality=85, method=6)
                dados = saida.getvalue()
                largura, altura = imagem.size
    except ImagemRecusada:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as erro:
        raise ImagemRecusada(
            "O arquivo não é uma imagem válida JPEG, PNG ou WebP."
        ) from erro
    if len(dados) > LIMITE_WEBP:
        raise ImagemRecusada(
            "A imagem processada ultrapassou 2 MiB. Envie outra imagem."
        )
    return dados, largura, altura


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
        usado = (
            ImagemDoPortfolio.objects.filter(peca__portfolio=portfolio).aggregate(
                total=models.Sum("tamanho")
            )["total"]
            or 0
        )
        if usado + len(dados) > LIMITE_PORTFOLIO:
            raise ImagemRecusada(
                "Este portfólio atingiu o limite de 50 MiB em imagens."
            )
        ordem = (
            portfolio.pecas.aggregate(ultima=models.Max("ordem"))["ultima"] or 0
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
    imagem = (
        ImagemDoPortfolio.objects.select_related("peca__portfolio")
        .filter(id=imagem_id, peca__portfolio__site_id=site_id)
        .first()
        if site_id
        else None
    )
    if imagem is None:
        return _recusa()
    portfolio = imagem.peca.portfolio
    if not (portfolio.vitrine_publicada and imagem.peca.mostrar_na_pagina_publica):
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
            dono = (
                sessao["id"] == portfolio.aluno_id
                and AlunosClient().categoria_de(email) == "aluno"
            )
            if not dono and not e_da_equipe(email):
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
