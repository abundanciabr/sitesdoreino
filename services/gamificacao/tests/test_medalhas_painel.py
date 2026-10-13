import json
import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse
from ninja.errors import HttpError

from apps.core import medalhas_painel as tela
from apps.gamificacao.medalhas_painel import dar, colecao
from apps.gamificacao.models import (
    CelebracaoDeMedalha, Concessao, ConquistaDefinicao, HistoricoDaConcessao,
    LancamentoDeXP, MovimentoDeCristais,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", "escola")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-teste")
    monkeypatch.setattr(tela, "quem_e", lambda r: "aluna")
    monkeypatch.setattr("apps.gamificacao.validacao.relay_apos_commit", lambda: None)


def premiar(**extras):
    return dar(**{"site_id": "escola", "pessoa_id": "aluna", "nome": "Embaixador",
                  "mensagem": "Obrigado pela sua confiança!", "quem_id": "admin-1", **extras})


def test_concessao_historico_sem_xp_e_repeticao_idempotente(ambiente):
    primeira, nova = premiar(referencia="satisfacao:avaliacao-1")
    segunda, repetida = premiar(nome="  embaixador  ", mensagem="Não substitui a original")
    assert nova and not repetida and primeira.pk == segunda.pk
    assert Concessao.objects.count() == CelebracaoDeMedalha.objects.count() == HistoricoDaConcessao.objects.count() == 1
    assert primeira.concessao.validador_id == "admin-1"
    assert primeira.concessao.validador_papel == "admin"
    assert primeira.referencia == "satisfacao:avaliacao-1"
    assert segunda.mensagem == "Obrigado pela sua confiança!"
    assert not LancamentoDeXP.objects.exists() and not MovimentoDeCristais.objects.exists()


def test_get_nao_consume_celebracao_e_post_confirma_persistente(ambiente):
    item, _ = premiar()
    c = Client(enforce_csrf_checks=True)
    r = c.get(reverse("minhas-medalhas"))
    assert r.status_code == 200 and r.json()["pendente"]["id"] == item.pk
    item.refresh_from_db()
    assert item.vista_em is None and "no-store" in r["Cache-Control"]
    url = reverse("medalha-vista", args=[item.pk])
    assert c.get(url).status_code == 405
    assert c.post(url).status_code == 403
    assert c.post(url, HTTP_X_CSRFTOKEN=r.json()["csrf"]).json() == {"vista": True}
    assert c.get(reverse("minhas-medalhas")).json()["pendente"] is None
    assert len(c.get(reverse("minhas-medalhas")).json()["medalhas"]) == 1
    _, nova = premiar()
    assert not nova
    item.refresh_from_db()
    assert item.vista_em is not None


def test_outro_aluno_e_outro_site_nao_recebem_ou_confirmam(ambiente, monkeypatch):
    item, _ = premiar()
    monkeypatch.setattr(tela, "quem_e", lambda r: "outra")
    assert Client().get(reverse("minhas-medalhas")).json()["medalhas"] == []
    assert Client().post(reverse("medalha-vista", args=[item.pk])).status_code == 404
    monkeypatch.setattr(tela, "quem_e", lambda r: "aluna")
    monkeypatch.setenv("SITE_ID", "outra-escola")
    assert Client().get(reverse("minhas-medalhas")).json()["medalhas"] == []


def test_visitante_sem_colecao(ambiente, monkeypatch):
    premiar()
    monkeypatch.setattr(tela, "quem_e", lambda r: None)
    assert Client().get(reverse("minhas-medalhas")).json() == {"medalhas": [], "pendente": None}


def test_revogada_nao_reaparece_e_historico_preservado(ambiente):
    item, _ = premiar()
    Concessao.objects.filter(pk=item.concessao_id).update(estado="revogada")
    assert not colecao("aluna", "escola").exists()
    with pytest.raises(Exception, match="retirada"):
        premiar()
    assert HistoricoDaConcessao.objects.count() == 1


def test_api_so_token_admin_site_certo_e_sem_query_response(ambiente, settings):
    settings.TOKENS_ACEITOS = {"admin-teste", "outro-token"}
    url = "/api/gamificacao/medalhas-painel/escola/aluna"
    c = Client()
    assert c.get(url).status_code == 401
    assert c.get(url, HTTP_AUTHORIZATION="Bearer outro-token").status_code == 403
    assert c.get(url.replace("/escola/", "/outra/"), HTTP_AUTHORIZATION="Bearer admin-teste").status_code == 404
    r = c.post(url, data=json.dumps({"nome": "Embaixador", "mensagem": "Parabéns!", "quem_id": "admin-1"}),
               content_type="application/json", HTTP_AUTHORIZATION="Bearer admin-teste")
    assert r.status_code == 200, r.content
    assert r.json()["nova"] is True
    assert c.get(url, HTTP_AUTHORIZATION="Bearer admin-teste").json()["medalhas"][0]["nome"] == "Embaixador"


@pytest.mark.parametrize("extras", [{"nome": " "}, {"mensagem": ""}, {"nome": "a"*121}, {"mensagem": "a"*1001}, {"quem_id": ""}])
def test_dados_invalidos_nao_concedem(ambiente, extras):
    with pytest.raises(ValueError):
        premiar(**extras)
    assert not Concessao.objects.exists()


def test_nome_nao_altera_outras_medalhas_ou_pontos(ambiente):
    existente = ConquistaDefinicao.objects.create(site_id="escola", slug="embaixador", nome="Embaixador",
                  classe="medalha", familia="comunidade", pontos=25)
    item, _ = premiar()
    existente.refresh_from_db()
    assert existente.pontos == 25 and item.concessao.conquista_id != existente.pk
