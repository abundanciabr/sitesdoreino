"""Percurso real do preparo à publicação visual, com fronteira de privacidade."""

import json
from io import BytesIO

import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from apps.portfolio import dossie, vitrine
from apps.portfolio.models import MaterialDaPeca, Peca, Portfolio
from conftest import ANA, COOKIE, SITE, URL_DA_SESSAO, dublar_matricula


def como_aluna():
    return {"HTTP_COOKIE": COOKIE}


def imagem(nome, cor):
    saida = BytesIO()
    Image.new("RGB", (80, 80), cor).save(saida, format="PNG")
    return SimpleUploadedFile(nome, saida.getvalue(), content_type="image/png")


def preparo_url(peca):
    return reverse("preparar_trabalho", kwargs={"peca_id": peca.pk})


def montagem_dados(peca, materiais, titulo, *, acao="salvar"):
    return {
        "acao": acao,
        "apelido": "ana-3d",
        "selecao_trabalhos": "1",
        "trabalhos_ids": [str(peca.pk)],
        "conteudo_json": json.dumps({"pagina": {
            "titulo": titulo,
            "subtitulo": "Peças para experiências Roblox",
            "trabalho_destaque": str(peca.pk),
            "ordem_trabalhos": [str(peca.pk)],
            "materiais_ids": [str(item.pk) for item in materiais],
            "legendas": [{"peca_id": str(peca.pk), "titulo": peca.titulo,
                          "texto": peca.descricao}],
        }}),
    }


def test_preparo_upload_ficha_checklist_retorno_e_isolamento(
    aluna, site_declarado, criar_portfolio, criar_peca, rede
):
    portfolio = criar_portfolio(ANA["id"])
    peca = criar_peca(portfolio, legenda="Meu modelo")
    cliente = Client()
    url = preparo_url(peca)

    primeira_tela = cliente.get(url, **como_aluna())
    assert primeira_tela.status_code == 200
    assert b"https://exemplo.test/render.png" in primeira_tela.content
    enviados = cliente.post(url, {
        "acao": "enviar", "categoria": "vistas", "legenda": "Duas vistas",
        "principal": "1", "arquivos": [imagem("frente.png", "red"), imagem("lado.png", "blue")],
    }, **como_aluna())
    assert enviados.status_code == 302
    materiais = list(peca.materiais.order_by("ordem"))
    assert len(materiais) == 2
    assert [item.principal for item in materiais] == [True, False]
    assert all(item.categoria == "vistas" and item.bytes for item in materiais)
    substituida = cliente.post(url, {
        "acao": "material", "material_id": str(materiais[0].pk),
        "categoria": "render", "legenda": "Imagem nova", "ordem": "1",
        "principal": "1", "substituir": imagem("nova.png", "green"),
    }, **como_aluna())
    assert substituida.status_code == 302
    ativos = list(peca.materiais.filter(substituido_por__isnull=True).order_by("ordem"))
    assert len(ativos) == 2
    assert materiais[1].pk in {item.pk for item in ativos}
    materiais[0].refresh_from_db()
    assert materiais[0].substituido_por_id is not None
    assert materiais[0].substituido_por.principal is True

    salvo = cliente.post(url, {
        "acao": "salvar", "titulo": "Espada feita por Ana", "descricao": "Modelo para aventura",
        "uso_pretendido": "Experiência Roblox", "triangulos": "1.200",
        "textura": "1024 × 1024", "checklist": ["nome_descricao", "vistas_detalhes"],
    }, **como_aluna())
    assert salvo.status_code == 302
    retomado = cliente.get(url, **como_aluna())
    assert retomado.status_code == 200
    assert b"Espada feita por Ana" in retomado.content
    assert b"https://exemplo.test/render.png" in retomado.content
    peca.refresh_from_db()
    assert peca.titulo == "Espada feita por Ana"
    assert peca.triangulos == "1.200"
    assert {i["chave"] for i in peca.checklist_preparacao if i["marcado"]} == {
        "nome_descricao", "vistas_detalhes"
    }
    abrir_previa = cliente.post(url, {
        "acao": "salvar", "ver_previa": "1", "titulo": "Espada feita por Ana",
        "descricao": "Descrição alterada antes da prévia",
        "checklist": ["nome_descricao", "vistas_detalhes"],
    }, **como_aluna())
    assert abrir_previa.status_code == 302
    assert abrir_previa["Location"].endswith("?previa=1#previa")
    previa = cliente.get(abrir_previa["Location"], **como_aluna())
    assert previa.status_code == 200
    assert b"Descri\xc3\xa7\xc3\xa3o alterada antes da pr\xc3\xa9via" in previa.content

    outra = {**ANA, "id": "p_outra"}
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, json=outra))
    dublar_matricula(rede, outra["email"])
    assert cliente.get(url, **como_aluna()).status_code == 404
    assert cliente.post(url, {"acao": "salvar", "titulo": "Intruso"}, **como_aluna()).status_code == 404
    peca.refresh_from_db()
    assert peca.titulo == "Espada feita por Ana"


def test_montagem_rascunho_ajax_publicacao_pdf_e_bytes_selecionados(
    aluna, site_declarado, criar_portfolio, criar_peca
):
    portfolio = criar_portfolio(ANA["id"])
    peca = criar_peca(portfolio, legenda="Meu objeto")
    cliente = Client()
    preparo = preparo_url(peca)
    assert cliente.post(preparo, {"acao": "enviar", "categoria": "render",
        "arquivos": [imagem("principal.png", "red"), imagem("privada.png", "blue")],
        "principal": "1"}, **como_aluna()).status_code == 302
    materiais = list(MaterialDaPeca.objects.filter(peca=peca).order_by("ordem"))
    principal, privado = materiais
    assert cliente.get(reverse("apresentacao_publica"), **como_aluna()).status_code == 200
    assert cliente.get(reverse("apresentacao_previa"), **como_aluna()).status_code == 200
    assert cliente.get(reverse("script_montagem"), **como_aluna()).status_code == 200

    url_montagem = reverse("apresentacao_publica")
    resposta = cliente.post(url_montagem, montagem_dados(peca, [principal], "Versão publicada", acao="publicar"),
                            HTTP_X_REQUESTED_WITH="XMLHttpRequest", **como_aluna())
    assert resposta.status_code == 200 and resposta.json()["publicada"] is True
    portfolio.refresh_from_db()
    assert portfolio.publicacao_comercial["conteudo"]["pagina"]["titulo"] == "Versão publicada"
    url_publica = reverse("vitrine", kwargs={"apelido": "ana-3d"})
    url_pdf = reverse("pdf_publico", kwargs={"apelido": "ana-3d"})
    visitante = Client()
    assert visitante.get(url_publica).status_code == 200
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": principal.pk})).status_code == 200
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": privado.pk})).status_code == 404

    rascunho = cliente.post(url_montagem, montagem_dados(peca, [privado], "Rascunho novo"),
                            HTTP_X_REQUESTED_WITH="XMLHttpRequest", **como_aluna())
    assert rascunho.status_code == 200 and rascunho.json()["salvo"] is True
    portfolio.refresh_from_db()
    assert portfolio.apresentacao_comercial["pagina"]["titulo"] == "Rascunho novo"
    assert portfolio.publicacao_comercial["conteudo"]["pagina"]["titulo"] == "Versão publicada"
    assert "Versão publicada" in visitante.get(url_publica).content.decode()
    assert "Rascunho novo" not in visitante.get(url_publica).content.decode()
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": principal.pk})).status_code == 200
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": privado.pk})).status_code == 404
    publicado = vitrine.dados_publicados(portfolio)
    assert str(principal.pk) in publicado["imagens_ids"] and str(privado.pk) not in publicado["imagens_ids"]
    assert str(principal.pk) in dossie.bytes_de_imagens_publicadas(portfolio, publicado)
    assert str(privado.pk) not in dossie.bytes_de_imagens_publicadas(portfolio, publicado)
    pdf = visitante.get(url_pdf)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    republicado = cliente.post(url_montagem, montagem_dados(peca, [privado], "Rascunho novo", acao="publicar"),
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest", **como_aluna())
    assert republicado.status_code == 200
    assert "Rascunho novo" in visitante.get(url_publica).content.decode()
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": principal.pk})).status_code == 404
    assert visitante.get(reverse("imagem_portfolio", kwargs={"imagem_id": privado.pk})).status_code == 200
    assert visitante.get(url_pdf).status_code == 200
