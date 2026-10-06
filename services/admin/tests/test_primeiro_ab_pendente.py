"""A headline B pendente vive no admin; o experimento só nasce com texto B."""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from apps.core import experimentos
from apps.core.models import RascunhoDeConfiguracao


SITE = {"id": "mesh", "host": "testserver"}


@pytest.mark.django_db
def test_preparar_plano_persistente_sem_experimento(monkeypatch):
    criacoes = []
    monkeypatch.setattr(experimentos.CatalogoClient, "criar_experimento",
                        lambda *args: criacoes.append(args))
    plano = experimentos.preparar_primeiro_ab(SITE["id"])
    assert plano.conteudo["texto_b"] == ""
    assert plano.conteudo["metrica_principal"] == "checkout_iniciado"
    assert plano.conteudo["parte_b"] == "50"
    assert plano.conteudo["taxa_base"] == "3"
    assert plano.base["situacao"] == "aguardando_headline_b"
    assert experimentos.preparar_primeiro_ab(SITE["id"]).pk == plano.pk
    assert RascunhoDeConfiguracao.objects.filter(tipo="primeiro_ab").count() == 1
    assert criacoes == []


@pytest.mark.django_db
def test_pagina_primeiro_ab_le_plano_e_a_headline_publicada(monkeypatch):
    experimentos.preparar_primeiro_ab(SITE["id"])
    monkeypatch.setattr(experimentos, "_site", lambda request: SITE)
    monkeypatch.setattr(experimentos, "texto_no_ar", lambda site, espaco: ("ok", "Headline vigente"))
    req = RequestFactory().get("/paginas/experimentos/novo", {"primeiro": "1"})
    req.admin = {"email": "mantenedor@exemplo.com"}
    resposta = experimentos.experimento_novo(req)
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Headline vigente" in corpo
    assert 'name="texto_b" rows="3"></textarea>' in corpo
    assert 'name="metrica_principal"' in corpo
    assert 'value="checkout_iniciado" selected' in corpo
    assert "hipótese de planejamento" in corpo


@pytest.mark.django_db
def test_sem_b_nao_cria_experimento_nem_ativa(monkeypatch):
    experimentos.preparar_primeiro_ab(SITE["id"])
    monkeypatch.setattr(experimentos, "_site", lambda request: SITE)
    monkeypatch.setattr(experimentos, "texto_no_ar", lambda site, espaco: ("ok", "Headline vigente"))
    chamadas = []
    monkeypatch.setattr(experimentos.CatalogoClient, "criar_experimento",
                        lambda *args: chamadas.append(args))
    req = RequestFactory().post("/paginas/experimentos/novo", {
        **RascunhoDeConfiguracao.objects.get(tipo="primeiro_ab").conteudo,
        "primeiro": "1", "gesto": "salvar",
    })
    req.admin = {"email": "mantenedor@exemplo.com"}
    resposta = experimentos.experimento_novo(req)
    assert resposta.status_code == 422
    assert chamadas == []
    assert RascunhoDeConfiguracao.objects.get(tipo="primeiro_ab").base["situacao"] == "aguardando_headline_b"


@pytest.mark.django_db
def test_b_exata_cria_somente_rascunho_do_catalogo(monkeypatch):
    experimentos.preparar_primeiro_ab(SITE["id"])
    monkeypatch.setattr(experimentos, "_site", lambda request: SITE)
    monkeypatch.setattr(experimentos, "texto_no_ar", lambda site, espaco: ("ok", "Headline vigente"))
    enviados = []

    def criar(_cliente, site_id, slug, corpo):
        enviados.append(corpo)
        return "ok", {"id": "exp-1", "estado": "rascunho"}

    monkeypatch.setattr(experimentos.CatalogoClient, "criar_experimento", criar)
    monkeypatch.setattr(experimentos, "_auditar", lambda *args: None)
    plano = RascunhoDeConfiguracao.objects.get(tipo="primeiro_ab")
    req = RequestFactory().post("/paginas/experimentos/novo", {
        **plano.conteudo, "texto_b": "Headline B exata do mantenedor",
        "primeiro": "1", "gesto": "salvar",
    })
    req.admin = {"email": "mantenedor@exemplo.com"}
    resposta = experimentos.experimento_novo(req)
    assert resposta.status_code == 302
    assert len(enviados) == 1
    assert enviados[0]["variantes"] == [
        {"variante_id": "a", "peso": 5000},
        {"variante_id": "b", "peso": 5000, "valor": "Headline B exata do mantenedor"},
    ]
    assert enviados[0]["metrica_principal"] == "checkout_iniciado"
    plano.refresh_from_db()
    assert plano.base["experimento_id"] == "exp-1"
    assert plano.conteudo["texto_b"] == ""


def test_lista_tem_link_do_resultado_sem_declarar_vencedor():
    item = experimentos._para_a_tela({
        "id": "exp-1", "secao": "cubo", "slot": "headline", "estado": "encerrado",
        "n_por_braco_planejado": 123, "variantes": [],
    })
    assert item["amostra"] == "123"
    assert "vencedor" not in item


@pytest.mark.django_db
def test_lista_mostra_pendencia_ate_criar_rascunho(monkeypatch):
    plano = experimentos.preparar_primeiro_ab(SITE["id"])
    monkeypatch.setattr(experimentos.CatalogoClient, "experimentos_da_pagina",
                        lambda *args: ("ok", []))
    req = RequestFactory().get("/paginas/experimentos/")
    req.admin = {"email": "mantenedor@exemplo.com"}
    assert "headline B pendente" in experimentos._lista(req, SITE).content.decode()
    plano.base = {"situacao": "rascunho_no_catalogo", "experimento_id": "exp-1"}
    plano.save(update_fields=["base"])
    assert "headline B pendente" not in experimentos._lista(req, SITE).content.decode()
