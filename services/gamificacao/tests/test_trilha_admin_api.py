"""A consulta do bastidor expõe o progresso real sem mudar a jornada."""

from datetime import date
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings

from apps.gamificacao.models import JornadaPessoal, Pessoa, RecebimentoDeclarado


pytestmark = pytest.mark.django_db
SITE = "escola-v4"
URL = "/api/gamificacao/trilha-do-aluno"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr(settings, "TOKENS_ACEITOS", ["token-v4"])


def consultar(client, pessoa_id="aluna-v4", site_id=SITE, token="token-v4"):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.get(URL, {"pessoa_id": pessoa_id, "site_id": site_id}, **headers)


def pessoa(identificador):
    return Pessoa.objects.create(
        id_da_plataforma=identificador,
        email=f"{identificador}@example.test",
        nome_exibido="NOME-PRIVADO",
    )


def recebimento(aluna, site, valor, estado, leitura=None):
    return RecebimentoDeclarado.objects.create(
        pessoa=aluna,
        site_id=site,
        chave=uuid4(),
        valor_cents=valor,
        valor_original_cents=valor,
        origem="fora",
        estado=estado,
        leitura=leitura or {},
        recebido_em=date(2026, 10, 1),
    )


def test_bearer_e_site_local_sao_obrigatorios(client, monkeypatch):
    assert consultar(client, token=None).status_code == 401
    assert consultar(client, token="errado").status_code == 401
    assert consultar(client, site_id="outra-escola").status_code == 404
    monkeypatch.delenv("SITE_ID")
    assert consultar(client).status_code == 503


def test_aluno_sem_jornada_tem_branca_sem_meta_simulada_ou_escrita(client):
    resposta = consultar(client)
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["X-Robots-Tag"] == "noindex, nofollow"
    dados = resposta.json()
    assert set(dados) == {
        "pessoa_id", "site_id", "atual_ordem", "etapas", "total_cents",
        "meta_cents", "meta_escolhida",
    }
    assert (dados["pessoa_id"], dados["site_id"], dados["atual_ordem"]) == (
        "aluna-v4", SITE, 1,
    )
    assert dados["total_cents"] == 0
    assert dados["meta_cents"] is None and dados["meta_escolhida"] is False
    assert [etapa["ordem"] for etapa in dados["etapas"]] == list(range(1, 14))
    assert [etapa["alcancada"] for etapa in dados["etapas"]] == [True] + [False] * 12
    assert all(etapa["meta_cents"] is None for etapa in dados["etapas"])
    assert all(set(etapa) == {
        "ordem", "nome", "alcancada", "conquista", "meta_cents", "alcancada_em",
    } for etapa in dados["etapas"])
    assert JornadaPessoal.objects.count() == 0
    assert Pessoa.objects.count() == 0


def test_salto_nao_inventa_etapas_e_isola_pessoa_e_site(client):
    aluna = pessoa("aluna-v4")
    outra = pessoa("outra-aluna")
    JornadaPessoal.objects.create(
        pessoa=aluna, site_id=SITE, meta_cents=10000,
        declaracoes={"3": True}, proposito="PROPOSITO-PRIVADO",
    )
    JornadaPessoal.objects.create(
        pessoa=aluna, site_id="outro-site", meta_cents=100000,
        declaracoes={"2": True, "4": True},
    )
    JornadaPessoal.objects.create(
        pessoa=outra, site_id=SITE, meta_cents=50000,
        declaracoes={"2": True, "4": True},
    )
    resposta = consultar(client)
    dados = resposta.json()
    assert dados["atual_ordem"] == 3
    assert [e["alcancada"] for e in dados["etapas"][:5]] == [True, False, True, False, False]
    assert dados["meta_cents"] == 10000 and dados["meta_escolhida"] is True
    assert dados["etapas"][5]["meta_cents"] == 125
    assert "PROPOSITO-PRIVADO" not in resposta.content.decode()
    assert "NOME-PRIVADO" not in resposta.content.decode()
    assert "@example.test" not in resposta.content.decode()
    assert consultar(client, pessoa_id="outra-aluna").json()["atual_ordem"] == 4


def test_total_confirmado_pendente_e_correcao_preservada(client, monkeypatch):
    aluna = pessoa("aluna-v4")
    JornadaPessoal.objects.create(pessoa=aluna, site_id=SITE, meta_cents=10000)
    recebimento(aluna, SITE, 1000, "confirmado")
    recebimento(aluna, SITE, 9000, "pendente")
    recebimento(aluna, SITE, 700, "analisando", {"anterior_cents": 500})
    recebimento(aluna, SITE, 800, "esclarecer", {"motivo": "leitor", "anterior_cents": 300})
    recebimento(aluna, SITE, 900, "esclarecer", {"motivo": "divergencia", "anterior_cents": 900})
    recebimento(aluna, "outro-site", 50000, "confirmado")
    # situacao também formata mensagens privadas; a projeção não as utiliza.
    monkeypatch.setitem(
        sys.modules, "apps.gamificacao.prints_recebimentos",
        SimpleNamespace(mensagem=lambda registro: ""),
    )
    dados = consultar(client).json()
    assert dados["total_cents"] == 1800
    assert dados["atual_ordem"] == 9
    assert dados["etapas"][4]["alcancada"] is True
    assert dados["etapas"][6]["alcancada"] is True
    assert dados["etapas"][8]["alcancada"] is True
    assert dados["etapas"][9]["alcancada"] is False
    assert dados["etapas"][1]["alcancada"] is False
    assert RecebimentoDeclarado.objects.count() == 6
    assert JornadaPessoal.objects.get(pessoa=aluna, site_id=SITE).revisao == 0
