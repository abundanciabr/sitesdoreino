"""A leitura de trabalhos devolve só o estado da conta e do site da sessão."""

from datetime import timedelta

import pytest
from django.utils import timezone
from django.test import override_settings

from apps.encomendas.models import (
    ClienteFila, ParticipacaoSandbox, PedidoClienteFila, PedidoMarketplace,
    PerfilProfissional, Pessoa, ProjetoSandbox,
)
from apps.core.sessao import ConfiguracaoAusente, VizinhaIndisponivel

pytestmark = pytest.mark.django_db
URL = "/minha-trilha/"
SITE = "escola-checklist"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.trilha_pessoal._sessao",
                        lambda cookie: {"autenticado": True, "id": cookie.split("=")[-1]})


def consultar(client, cookie_id="a", **parametros):
    return client.get(URL, parametros, HTTP_COOKIE=f"sessao={cookie_id}")


def projeto(site=SITE):
    return ProjetoSandbox.objects.create(
        site_id=site, slug=f"pratica-{site}", titulo="Projeto privado",
        briefing="", criterios="",
    )


def participacao(pessoa_id, site=SITE, status="em_producao"):
    p = projeto(site)
    return ParticipacaoSandbox.objects.create(
        site_id=site, pessoa_id=pessoa_id, projeto=p, status=status,
        aceite_em=timezone.now(), prazo_ate=timezone.now() + timedelta(days=1),
    )


def pedido_fila(pessoa_id, site=SITE, status="em_producao"):
    pessoa, _ = Pessoa.objects.get_or_create(id_da_plataforma=pessoa_id)
    perfil = PerfilProfissional.objects.create(pessoa=pessoa, site_id=site)
    pedido = PedidoMarketplace.objects.create(
        site_id=site, cliente_id=f"cliente-{pessoa_id}", aluno=perfil,
        status=status, ambiente="production",
    )
    cliente = ClienteFila.objects.create(site_id=site, slug=f"cliente-{pessoa_id}",
                                        nome="Cliente privado")
    PedidoClienteFila.objects.create(site_id=site, pedido=pedido, cliente=cliente)
    return pedido


def test_sem_sessao_invalida_configuracao_e_metodo(client, monkeypatch):
    assert client.get(URL).status_code == 403
    monkeypatch.setattr("apps.core.trilha_pessoal._sessao", lambda cookie: {"autenticado": True, "id": 5})
    assert consultar(client).status_code == 403
    monkeypatch.setattr("apps.core.trilha_pessoal._sessao", lambda cookie: {"autenticado": False, "id": "a"})
    assert consultar(client).status_code == 403
    def falha(cookie):
        raise VizinhaIndisponivel("segredo-privado")
    monkeypatch.setattr("apps.core.trilha_pessoal._sessao", falha)
    assert consultar(client).status_code == 503
    monkeypatch.setattr("apps.core.trilha_pessoal._sessao",
                        lambda cookie: (_ for _ in ()).throw(ConfiguracaoAusente("token")))
    assert consultar(client).status_code == 503
    monkeypatch.delenv("SITE_ID")
    assert consultar(client).status_code == 503
    resposta = client.post(URL, HTTP_COOKIE="sessao=a")
    assert resposta.status_code == 405
    assert resposta["Allow"] == "GET, HEAD"


def test_isolamento_estados_atuais_sem_mutacao(client):
    a = participacao("a")
    participacao("b", site="outro-site")
    fila = pedido_fila("a")
    pedido_fila("b", site="outro-site")
    resposta = consultar(client, "a", pessoa_id="b", site_id="outro-site")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"
    assert "Cookie" in resposta["Vary"]
    dados = resposta.json()
    assert set(dados) == {"pessoa_id", "site_id", "consultado_em", "atividades"}
    assert (dados["pessoa_id"], dados["site_id"]) == ("a", SITE)
    assert [x["ordem"] for x in dados["atividades"]] == [3, 4]
    assert all(x["estado"] == "andamento" for x in dados["atividades"])
    assert str(a.pk) in dados["atividades"][0]["acao"]["url"]
    assert str(fila.pk) in dados["atividades"][1]["acao"]["url"]
    assert "privado" not in resposta.content.decode()
    assert ParticipacaoSandbox.objects.count() == 2
    assert PedidoMarketplace.objects.count() == 2
    assert consultar(client, "b").json()["atividades"] == []


def test_entrega_aprovacao_e_cancelamento_nao_viram_conquista(client):
    p = participacao("a", status="entregue")
    fila = pedido_fila("a", status="entregue")
    dados = consultar(client).json()
    assert [a["estado"] for a in dados["atividades"]] == ["andamento", "andamento"]
    assert all("enviada" in a["detalhe"] for a in dados["atividades"])
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(status="aprovado")
    PedidoMarketplace.objects.filter(pk=fila.pk).update(status="aprovado")
    dados = consultar(client).json()
    assert [a["estado"] for a in dados["atividades"]] == ["pendente", "pendente"]
    assert all("aguardando registro" in a["detalhe"] for a in dados["atividades"])
    PedidoMarketplace.objects.filter(pk=fila.pk).update(status="cancelado")
    dados = consultar(client).json()
    assert dados["atividades"][1]["estado"] == "pendente"
    assert dados["atividades"][1]["acao"] is None
    assert consultar(client, "a", site_id="outro")["Cache-Control"] == "private, no-store"


def test_acoes_respeitam_prefixo_publico_e_head_nao_tem_corpo(client):
    participacao("a")
    pedido_fila("a")
    with override_settings(FORCE_SCRIPT_NAME="/encomendas"):
        resposta = consultar(client)
        assert resposta.status_code == 200
        assert [a["acao"]["url"] for a in resposta.json()["atividades"]] == [
            "/encomendas/sandbox/trabalhos/" + str(
                ParticipacaoSandbox.objects.get(site_id=SITE, pessoa_id="a").pk
            ) + "/",
            "/encomendas/cliente/trabalhos/" + str(
                PedidoMarketplace.objects.get(site_id=SITE).pk
            ) + "/",
        ]
        cabeca = client.head(URL, HTTP_COOKIE="sessao=a")
        assert cabeca.status_code == 200
        assert cabeca.content == b""
        assert cabeca["Cache-Control"] == "private, no-store"


def test_estado_desconhecido_nao_e_aprovacao(client):
    p = participacao("a")
    ParticipacaoSandbox.objects.filter(pk=p.pk).update(status="estado_futuro")
    atividade = consultar(client).json()["atividades"][0]
    assert atividade["estado"] == "pendente"
    assert "aprovada" not in atividade["detalhe"]
