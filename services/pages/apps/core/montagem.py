"""Prévia privada e recursos da montagem visual do portfólio."""
from pathlib import Path
from types import SimpleNamespace

from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.portfolio import vitrine, dossie, comercial
from apps.portfolio.models import Portfolio
from .jornada import dono
from .views import site_atual, _sem_rastro


@require_GET
def script_montagem(request):
    caminho = Path(__file__).parent / "static/pages/portfolio-montagem.js"
    return HttpResponse(caminho.read_text(encoding="utf-8"), content_type="application/javascript")


@require_GET
def script_endereco(request):
    caminho = Path(__file__).parent / "static/pages/portfolio-endereco.js"
    return HttpResponse(caminho.read_text(encoding="utf-8"), content_type="application/javascript")


@require_GET
def previa(request):
    portfolio = Portfolio.objects.do_aluno(**dono(request)).first()
    publico = vitrine.snapshot_rascunho(portfolio) if portfolio else {"conteudo": {"pagina": {}}, "obras": []}
    pagina = publico["conteudo"]["pagina"]
    destaque = pagina.get("trabalho_destaque")
    hero = next((obra for obra in publico["obras"] if str(obra["id"]) == destaque), None) or next(iter(publico["obras"]), None)
    resposta = render(request, "pages/portfolio-previa.html", {"publico": publico, "hero": hero,
        "apelido": (portfolio.apelido if portfolio else "") or request.aluno.get("nome", ""),
        "contato_url": comercial.url_publica(publico.get("oferta", {}).get("contato")), "pdf_url": reverse("dossie")})
    resposta["Cache-Control"] = "no-store"
    resposta["X-Frame-Options"] = "SAMEORIGIN"
    resposta["Content-Security-Policy"] = "frame-ancestors 'self'"
    return resposta


@require_GET
def pdf_publico(request, apelido):
    portfolio = vitrine.publicada(site_id=site_atual(), apelido=apelido)
    if portfolio is None:
        raise Http404
    contexto = vitrine.contexto_comercial(portfolio)
    publico = contexto.get("publico") or vitrine.snapshot_rascunho(portfolio)
    resposta = HttpResponse(dossie.montar_visual(apelido=portfolio.apelido, publico=publico,
        imagens=dossie.bytes_de_imagens_publicadas(portfolio, publico),
        endereco_publico=request.build_absolute_uri(vitrine.endereco(portfolio.apelido))), content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{dossie.nome_do_arquivo(portfolio.apelido)}"'
    return _sem_rastro(resposta)


@require_GET
def previa_equipe(request):
    """Mostra as telas reais com exemplos da escola, sem criar ou editar portfólios."""
    from .jornada import desenhar
    from .preparar import CATEGORIAS
    from apps.portfolio.preparacao import ITENS_INICIAIS

    if not getattr(request, "membro_da_equipe", None):
        raise Http404
    exemplos = (
        ("Cabelo Cascata", "praticas-3d/modelos/cabelo-cascata/v3/miniatura.png"),
        ("Robô Pingo", "praticas-3d/modelos/robo-pingo/v2/miniatura.png"),
        ("Árvore estilizada", "joguinho-ep1/06-resultado.webp"),
    )
    trabalhos = [SimpleNamespace(
        pk=i, id=i, titulo=titulo, titulo_comercial=titulo, legenda=titulo,
        descricao="Exemplo da escola para demonstrar a apresentação.",
        texto_comercial="Exemplo da escola para demonstrar a apresentação.",
        link="/cursos/static/" + arquivo, imagem_montagem="/cursos/static/" + arquivo,
        imagem_principal="/cursos/static/" + arquivo, materiais_montagem=[],
        mostrar_na_pagina_publica=True, destaque=i == 1,
    ) for i, (titulo, arquivo) in enumerate(exemplos, 1)]
    conteudo = comercial.normalizar_conteudo({"pagina": {
        "titulo": "Meus trabalhos em 3D", "subtitulo": "Crio objetos e acessórios para Roblox.",
        "ordem_trabalhos": [str(item.pk) for item in trabalhos],
        "trabalho_destaque": "1", "apelido_rascunho": "exemplo",
    }})
    comum = {"previa_admin": True, "aluno": {"nome": "Exemplo ilustrativo"}}
    tela = request.GET.get("tela", "montagem")
    if tela == "resultado":
        resposta = render(request, "pages/portfolio-previa.html", {
            "publico": {"conteudo": conteudo, "obras": trabalhos},
            "hero": trabalhos[0], "apelido": "Exemplo ilustrativo",
        })
        resposta["X-Frame-Options"] = "SAMEORIGIN"
        resposta["Content-Security-Policy"] = "frame-ancestors 'self'"
    elif tela == "preparo":
        resposta = desenhar(request, "preparar.html", {**comum,
            "peca": trabalhos[0], "preparo": {
                "titulo": trabalhos[0].titulo, "descricao": trabalhos[0].descricao,
                "materiais": [], "checklist": [
                    {"chave": chave, "rotulo": rotulo, "marcado": i < 2}
                    for i, (chave, rotulo) in enumerate(ITENS_INICIAIS)
                ],
            }, "categorias": CATEGORIAS, "marcados": 2, "pendentes": 2,
            "imagem_previa": trabalhos[0].link, "voltar_apresentacao": True,
        })
    elif tela == "montagem":
        resposta = desenhar(request, "montagem.html", {**comum,
            "conteudo": conteudo, "trabalhos": trabalhos, "selecionados": 3,
            "portfolio": SimpleNamespace(apelido="exemplo", vitrine_publicada=False),
            "base_endereco_publico": request.build_absolute_uri("/portfolio/"),
        })
    else:
        raise Http404
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow"
    return resposta
