"""O checklist acrescenta contexto sem antecipar a conquista da jornada."""

from datetime import date
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings
from django.utils import timezone

from apps.gamificacao.models import FaixaDoAluno, JornadaPessoal, Pessoa, RecebimentoDeclarado

pytestmark = pytest.mark.django_db
SITE = "escola-checklist"
URL = "/api/gamificacao/trilha-do-aluno"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr(settings, "TOKENS_ACEITOS", ["token-checklist"])


def consultar(client, pessoa_id="a"):
    resposta = client.get(URL, {"pessoa_id": pessoa_id, "site_id": SITE},
                          HTTP_AUTHORIZATION="Bearer token-checklist")
    assert resposta.status_code == 200
    return resposta.json()


def pessoa(identificador):
    return Pessoa.objects.create(id_da_plataforma=identificador,
                                email=f"{identificador}@example.test", nome_exibido="PRIVADO")


def item(dados, ordem):
    return dados["etapas"][ordem - 1]["checklist"]["itens"][-1]


def test_vazio_mostra_pendencias_sem_inventar_modelagem(client):
    dados = consultar(client)
    assert dados["consultado_em"]
    assert item(dados, 1)["estado"] == "concluido"
    assert item(dados, 2)["estado"] == "pendente"
    assert item(dados, 3)["estado"] == "pendente"
    assert item(dados, 4)["estado"] == "pendente"
    assert item(dados, 6)["estado"] == "pendente"
    assert dados["etapas"][5]["checklist"]["itens"][0]["estado"] == "pendente"
    assert Pessoa.objects.count() == JornadaPessoal.objects.count() == 0


def test_item_salvo_e_eventos_antigos_nao_promovem_conclusao(client):
    a = pessoa("a")
    b = pessoa("b")
    agora = timezone.now()
    for ordem, origem in ((2, "item"), (3, "sandbox"), (4, "fila")):
        FaixaDoAluno.objects.create(pessoa=a, site_id=SITE, ordem=ordem,
            estado="alcancada", origem=origem, alcancada_em=agora)
    FaixaDoAluno.objects.create(pessoa=b, site_id=SITE, ordem=2,
        estado="alcancada", origem="item", alcancada_em=agora)
    JornadaPessoal.objects.create(pessoa=a, site_id=SITE, declaracoes={"4": True})
    dados = consultar(client)
    assert [e["alcancada"] for e in dados["etapas"][:4]] == [True, False, False, True]
    assert [item(dados, n)["estado"] for n in (2, 3, 4)] == [
        "andamento", "pendente", "concluido",
    ]
    assert "salvo" in item(dados, 2)["detalhe"]
    assert consultar(client, "b")["etapas"][1]["alcancada"] is False


def test_confirmado_pendente_e_meta_sem_simulacao(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "apps.gamificacao.prints_recebimentos",
                        SimpleNamespace(mensagem=lambda registro: ""))
    a = pessoa("a")
    RecebimentoDeclarado.objects.create(
        pessoa=a, site_id=SITE, chave=uuid4(), valor_cents=400,
        valor_original_cents=400, origem="fora", estado="pendente",
        recebido_em=date(2026, 10, 1),
    )
    dados = consultar(client)
    assert dados["total_cents"] == 0
    assert item(dados, 5)["estado"] == "andamento"
    assert item(dados, 6)["estado"] == "pendente"
    assert dados["etapas"][5]["meta_cents"] is None
    JornadaPessoal.objects.create(pessoa=a, site_id=SITE, meta_cents=10000)
    RecebimentoDeclarado.objects.create(
        pessoa=a, site_id=SITE, chave=uuid4(), valor_cents=150,
        valor_original_cents=150, origem="fora", estado="confirmado",
        recebido_em=date(2026, 10, 2),
    )
    dados = consultar(client)
    assert dados["total_cents"] == 150
    assert item(dados, 5)["estado"] == "concluido"
    assert item(dados, 6)["estado"] == "concluido"
    assert dados["etapas"][5]["checklist"]["itens"][0]["estado"] == "concluido"



@pytest.mark.parametrize("estado,valor", [("anulado", 400), ("pendente", 0), ("falha", 400), ("esclarecer", 400)])
def test_recebimentos_sem_confirmacao_ativa_ficam_pendentes(client, monkeypatch, estado, valor):
    monkeypatch.setitem(sys.modules, "apps.gamificacao.prints_recebimentos",
                        SimpleNamespace(mensagem=lambda registro: ""))
    a = pessoa("a")
    RecebimentoDeclarado.objects.create(
        pessoa=a, site_id=SITE, chave=uuid4(), valor_cents=valor,
        valor_original_cents=valor, origem="fora", estado=estado,
        recebido_em=date(2026, 10, 1),
    )
    dados = consultar(client)
    assert dados["total_cents"] == 0
    assert item(dados, 5)["estado"] == "pendente"


def test_releitura_preserva_valor_confirmado_da_jornada(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "apps.gamificacao.prints_recebimentos",
                        SimpleNamespace(mensagem=lambda registro: ""))
    a = pessoa("a")
    RecebimentoDeclarado.objects.create(
        pessoa=a, site_id=SITE, chave=uuid4(), valor_cents=900,
        valor_original_cents=900, origem="fora", estado="analisando",
        leitura={"anterior_cents": 400}, recebido_em=date(2026, 10, 1),
    )
    dados = consultar(client)
    assert dados["total_cents"] == 400
    assert item(dados, 5)["estado"] == "concluido"
