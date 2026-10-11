"""Preparo visual de uma peça do portfólio do aluno."""

from __future__ import annotations

import json
from copy import deepcopy

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from apps.portfolio import comercial, imagens, preparacao
from apps.portfolio.models import Peca, Portfolio

from .jornada import desenhar, dono


CATEGORIAS = (
    ("render", "Render principal ou contexto de uso"),
    ("vistas", "Vistas e detalhes"),
    ("wireframe", "Malha · wireframe"),
    ("uv", "Mapa UV ou textura"),
)


def _veio_da_apresentacao(request):
    return (request.POST.get("voltar") or request.GET.get("voltar")) == "apresentacao"


def _atualizar_textos_da_apresentacao(peca, dados):
    """A edição feita na montagem atualiza só a legenda desse trabalho no rascunho."""
    portfolio = peca.portfolio
    conteudo = deepcopy(portfolio.apresentacao_comercial or {})
    pagina = conteudo.setdefault("pagina", {})
    legendas = pagina.setdefault("legendas", [])
    legenda = next((item for item in legendas if str(item.get("peca_id")) == str(peca.pk)), None)
    if legenda is None:
        legenda = {"peca_id": str(peca.pk)}
        legendas.append(legenda)
    for origem, destino in (("titulo", "titulo"), ("descricao", "texto")):
        if origem in dados:
            legenda[destino] = getattr(peca, origem)
    portfolio.apresentacao_comercial = conteudo
    portfolio.save(update_fields=["apresentacao_comercial"])


def _mostrar(request, peca, *, recusa="", feito="", status=200):
    dados = preparacao.carregar_preparacao(peca)
    if _veio_da_apresentacao(request):
        conteudo = comercial.conteudo_de(peca.portfolio)
        comercial.preparar_trabalhos([peca], conteudo)
        dados["titulo"] = peca.titulo_comercial
        dados["descricao"] = peca.texto_comercial
    marcados = sum(1 for item in dados["checklist"] if item["marcado"])
    campos_pendentes = []
    for chave, rotulo in (
        ("descricao", "descrição"),
        ("uso_pretendido", "uso pretendido"),
        ("triangulos", "triângulos"),
        ("textura", "textura"),
    ):
        if not dados[chave]:
            campos_pendentes.append(rotulo)
    imagem_principal = next((item for item in dados["materiais"] if item.principal), None)
    return desenhar(
        request,
        "preparar.html",
        {
            "peca": peca,
            "preparo": dados,
            "categorias": CATEGORIAS,
            "marcados": marcados,
            "pendentes": len(dados["checklist"]) - marcados,
            "campos_pendentes": campos_pendentes,
            "recusa": recusa,
            "feito": feito,
            "previa": request.GET.get("previa") == "1",
            "imagem_previa": imagem_principal.url if imagem_principal else peca.link,
            "imagem_legada": bool(getattr(peca, "imagem_enviada", None)),
            "voltar_apresentacao": _veio_da_apresentacao(request),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def preparar_trabalho(request, peca_id):
    """Salva rascunhos parciais e acrescenta materiais sem exigir checklist completo."""
    peca = get_object_or_404(Peca.objects.do_aluno(**dono(request)), pk=peca_id)
    if request.method == "GET":
        return _mostrar(request, peca)

    acao = request.POST.get("acao", "salvar")
    try:
        if acao == "salvar":
            dados = request.POST.copy()
            dados["checklist_json"] = json.dumps(
                request.POST.getlist("checklist"), ensure_ascii=False
            )
            with transaction.atomic():
                peca.portfolio = Portfolio.objects.select_for_update().get(pk=peca.portfolio_id)
                preparacao.salvar_preparacao(peca, dados)
                if _veio_da_apresentacao(request):
                    _atualizar_textos_da_apresentacao(peca, dados)
            feito = "Seu trabalho foi salvo."
        elif acao == "enviar":
            arquivos = request.FILES.getlist("arquivos")
            if not arquivos:
                raise imagens.ImagemRecusada("Escolha ao menos uma imagem para enviar.")
            categoria = request.POST.get("categoria", "render")
            if categoria not in dict(CATEGORIAS):
                raise ValueError("Escolha uma categoria de imagem disponível.")
            legenda = request.POST.get("legenda", "").strip()
            with transaction.atomic():
                for indice, arquivo in enumerate(arquivos):
                    imagens.adicionar_material(
                        arquivo,
                        **dono(request),
                        peca_id=peca.pk,
                        categoria=categoria,
                        legenda=legenda,
                        principal=request.POST.get("principal") == "1" and indice == 0,
                    )
            feito = "Imagem adicionada." if len(arquivos) == 1 else "Imagens adicionadas."
        elif acao == "material":
            identificador = request.POST.get("material_id", "")
            material = next(
                (item for item in preparacao.carregar_preparacao(peca)["materiais"]
                 if str(item.id) == identificador),
                None,
            )
            if material is None:
                raise Http404
            ordem_texto = request.POST.get("ordem", "").strip()
            ordem = int(ordem_texto) if ordem_texto else None
            with transaction.atomic():
                novo = request.FILES.get("substituir")
                if novo:
                    material = imagens.substituir_material(
                        novo, **dono(request), peca_id=peca.pk, imagem_id=material.id
                    )
                imagens.editar_material(
                    **dono(request),
                    peca_id=peca.pk,
                    imagem_id=material.id,
                    categoria=request.POST.get("categoria", material.categoria),
                    legenda=request.POST.get("legenda", material.legenda),
                    ordem=ordem,
                    principal=request.POST.get("principal") == "1",
                )
            feito = "Material atualizado."
        else:
            raise ValueError("Ação não reconhecida.")
    except (imagens.ImagemRecusada, ValueError) as erro:
        return _mostrar(request, peca, recusa=str(erro), status=422)

    # O retorno conserva o endereço da peça, inclusive quando o aluno está na prévia.
    if acao == "salvar" and request.POST.get("concluir") == "1" and _veio_da_apresentacao(request):
        resposta = redirect("apresentacao_publica")
        resposta["Location"] += "#escolher-trabalhos"
    else:
        resposta = redirect("preparar_trabalho", peca_id=peca.pk)
        parametros = []
        if _veio_da_apresentacao(request):
            parametros.append("voltar=apresentacao")
        previa = acao == "salvar" and request.POST.get("ver_previa") == "1"
        if previa:
            parametros.append("previa=1")
        if parametros:
            resposta["Location"] += "?" + "&".join(parametros)
        if previa:
            resposta["Location"] += "#previa"
    resposta["Cache-Control"] = "no-store"
    return resposta
