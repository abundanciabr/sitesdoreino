from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from apps.portfolio.imagens import adicionar_material, guardar, servir_imagem, substituir_material
from apps.portfolio.models import Peca, Portfolio
from apps.portfolio.preparacao import carregar_preparacao, salvar_preparacao
from apps.portfolio import vitrine


def arquivo(cor="red"):
    saida = BytesIO()
    Image.new("RGB", (24, 24), cor).save(saida, format="PNG")
    return SimpleUploadedFile("imagem.png", saida.getvalue())


@pytest.mark.django_db
def test_publicacao_congela_texto_selecao_e_bytes_da_galeria():
    portfolio = Portfolio.objects.create(site_id="escola-a", aluno_id="ana")
    peca = Peca.objects.create(portfolio=portfolio, link="https://example.com/obra", ordem=1,
                              legenda="Original", mostrar_na_pagina_publica=True)
    escolhida = adicionar_material(arquivo(), site_id="escola-a", aluno_id="ana",
                                  peca_id=peca.pk, categoria="render", principal=True)
    escondida = adicionar_material(arquivo("blue"), site_id="escola-a", aluno_id="ana",
                                  peca_id=peca.pk, categoria="uv")
    portfolio.apresentacao_comercial = {"pagina": {"titulo": "Primeira versão", "materiais_ids": [str(escolhida.pk)]}}
    portfolio.save(update_fields=["apresentacao_comercial"])
    vitrine.publicar(site_id="escola-a", aluno_id="ana", texto="ana")
    portfolio.refresh_from_db()
    assert portfolio.publicacao_comercial["imagens_ids"] == [str(escolhida.pk)]
    assert vitrine.contexto_comercial(portfolio)["comercial"]["titulo"] == "Primeira versão"

    salvar_preparacao(peca, {"titulo": "Novo rascunho", "checklist_json": '["nome_descricao"]'})
    novo = substituir_material(arquivo("green"), site_id="escola-a", aluno_id="ana",
                              peca_id=peca.pk, imagem_id=escolhida.pk)
    portfolio.apresentacao_comercial = {"pagina": {"titulo": "Rascunho"}}
    portfolio.save(update_fields=["apresentacao_comercial"])
    portfolio.refresh_from_db()
    publicado = vitrine.contexto_comercial(portfolio)
    assert publicado["comercial"]["titulo"] == "Primeira versão"
    assert publicado["obras"][0].imagem_principal == escolhida.url
    assert publicado["obras"][0].titulo == ""
    assert carregar_preparacao(peca)["titulo"] == "Novo rascunho"
    assert novo.pk != escolhida.pk
    assert peca.materiais.count() == 3

    with patch("apps.core.views.site_atual", return_value="escola-a"):
        assert servir_imagem(RequestFactory().get(escolhida.url), escolhida.pk).status_code == 200
        assert servir_imagem(RequestFactory().get(escondida.url), escondida.pk).status_code == 404
        assert servir_imagem(RequestFactory().get(novo.url), novo.pk).status_code == 404

    portfolio.apresentacao_comercial = {"pagina": {"materiais_ids": [str(novo.pk)]}}
    portfolio.save(update_fields=["apresentacao_comercial"])
    vitrine.publicar(site_id="escola-a", aluno_id="ana", texto="ana")
    portfolio.refresh_from_db()
    assert vitrine.contexto_comercial(portfolio)["obras"][0].imagem_principal == novo.url
    with patch("apps.core.views.site_atual", return_value="escola-a"):
        assert servir_imagem(RequestFactory().get(escolhida.url), escolhida.pk).status_code == 404
        assert servir_imagem(RequestFactory().get(novo.url), novo.pk).status_code == 200


@pytest.mark.django_db
def test_legado_congela_antes_de_editar_e_preserva_vitrine():
    portfolio = Portfolio.objects.create(site_id="escola-a", aluno_id="ana", apelido="ana",
                                         vitrine_publicada=True, publicada_em="2026-10-01T12:00:00Z",
                                         apresentacao_publica="Texto original")
    peca = Peca.objects.create(portfolio=portfolio, link="https://example.com/obra", ordem=1,
                              legenda="Original", mostrar_na_pagina_publica=True)
    assert vitrine.dados_publicados(portfolio) is None
    salvar_preparacao(peca, {"titulo": "Novo título"})
    portfolio.refresh_from_db()
    assert vitrine.dados_publicados(portfolio)["obras"][0]["titulo"] == ""
    assert vitrine.contexto_comercial(portfolio)["comercial"]["apresentacao"] == "Texto original"


@pytest.mark.django_db
def test_selecao_vazia_explicita_nao_republica_imagem_legada():
    portfolio = Portfolio.objects.create(site_id="escola-a", aluno_id="ana")
    peca = Peca.objects.create(portfolio=portfolio, link="https://example.com/obra", ordem=1,
                              mostrar_na_pagina_publica=True)
    portfolio.apresentacao_comercial = {"pagina": {"materiais_ids": []}}
    portfolio.save(update_fields=["apresentacao_comercial"])
    retrato = vitrine.snapshot_rascunho(portfolio)
    assert retrato["obras"][0]["imagem_principal"] == ""
    assert retrato["obras"][0]["link"] == ""


@pytest.mark.django_db
def test_arquivar_trabalho_conserva_bytes_do_retrato_publicado():
    portfolio = Portfolio.objects.create(site_id="escola-a", aluno_id="ana")
    peca = Peca.objects.create(portfolio=portfolio, link="https://example.com/obra", ordem=1,
                              mostrar_na_pagina_publica=True)
    material = adicionar_material(arquivo(), site_id="escola-a", aluno_id="ana",
                                  peca_id=peca.pk, principal=True)
    portfolio.apresentacao_comercial = {"pagina": {"materiais_ids": [str(material.pk)]}}
    portfolio.save(update_fields=["apresentacao_comercial"])
    vitrine.publicar(site_id="escola-a", aluno_id="ana", texto="ana")
    peca.arquivada = True
    peca.save(update_fields=["arquivada"])
    assert Peca.objects.count() == 0
    assert Peca.todas.count() == 1
    portfolio.refresh_from_db()
    assert len(vitrine.obras(portfolio)) == 1
    assert vitrine.snapshot_rascunho(portfolio)["obras"] == []
    with patch("apps.core.views.site_atual", return_value="escola-a"):
        assert servir_imagem(RequestFactory().get(material.url), material.pk).status_code == 200
    seguinte = guardar(arquivo("green"), site_id="escola-a", aluno_id="ana",
                       legenda="Novo", base_url="https://site.test")
    assert seguinte.ordem == 2
