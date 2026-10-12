from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.gamificacao.models import (
    AvaliacaoDaJornada, AvaliacaoSandboxProjetada, Concessao, ConquistaDefinicao,
    LancamentoDeXP, PerfilJogador, Pessoa,
)


SITE = "escola-individual"
URL = f"/api/gamificacao/resumo-aluno/{SITE}/aluna-ficha"


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, settings):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-admin")
    settings.TOKENS_ACEITOS = {"token-admin", "token-par"}


def _get(client, token="token-admin", url=URL):
    return client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_resumo_vazio_e_privado_nao_cria_perfil_ou_jornada(client):
    assert _get(client, token="token-par").status_code == 403
    assert _get(client, url=f"/api/gamificacao/resumo-aluno/outro-site/aluna-ficha").status_code == 404
    with CaptureQueriesContext(connection) as consultas:
        resposta = _get(client)
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    dados = resposta.json()
    assert dados["fonte"] == "gamificacao"
    assert dados["perfil"] is None
    assert dados["faixa"]["atual"]["ordem"] == 1
    assert dados["faixa"]["origem"] == {"tipo": "faixa_inicial"}
    assert dados["sandbox"]["avaliacoes"] == []
    assert not PerfilJogador.objects.exists()
    assert all(not consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
               for consulta in consultas)


@pytest.mark.django_db
def test_perfil_conquistas_e_atividade_sao_da_pessoa_pedida(client):
    aluna = Pessoa.objects.create(id_da_plataforma="aluna-ficha", email="aluna@example.test")
    outra = Pessoa.objects.create(id_da_plataforma="outra-aluna", email="outra@example.test")
    PerfilJogador.objects.create(pessoa=aluna, site_id=SITE, xp_total=15479, nivel=3)
    PerfilJogador.objects.create(pessoa=outra, site_id=SITE, xp_total=999999, nivel=15)
    agora = timezone.now()
    for pessoa, pontos, quando in ((aluna, 200, agora), (outra, 9000, agora + timedelta(days=1))):
        LancamentoDeXP.objects.create(
            pessoa=pessoa, site_id=SITE, pontos=pontos,
            origem_event_id=str(uuid4()), regra_slug="teste-ficha",
            occurred_at=quando, dia_local=quando.date(),
            status=LancamentoDeXP.Status.DEFINITIVO,
        )
    conquista = ConquistaDefinicao.objects.create(
        site_id=SITE, slug="primeira-obra", nome="Primeira obra",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
    )
    Concessao.objects.create(pessoa=aluna, site_id=SITE, conquista=conquista)
    outra_conquista = ConquistaDefinicao.objects.create(
        site_id=SITE, slug="segredo-outra", nome="Segredo de outra pessoa",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.OFICIO,
    )
    Concessao.objects.create(pessoa=outra, site_id=SITE, conquista=outra_conquista)
    with CaptureQueriesContext(connection) as consultas:
        resposta = _get(client)
    assert resposta.status_code == 200
    perfil = resposta.json()["perfil"]
    assert (perfil["pessoa_id"], perfil["xp"], perfil["nivel"]) == ("aluna-ficha", 15479, 3)
    assert perfil["ultima_atividade_em"].startswith(agora.strftime("%Y-%m-%dT"))
    assert [(item["slug"], item["nome"]) for item in perfil["conquistas"]] == [
        ("primeira-obra", "Primeira obra"),
    ]
    assert "Segredo de outra pessoa" not in resposta.content.decode()
    assert all(not consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
               for consulta in consultas)
    perfil_sql = [c["sql"] for c in consultas if '"gamificacao_perfiljogador"' in c["sql"]]
    assert perfil_sql and all('"pessoa_id"' in sql and '"site_id"' in sql for sql in perfil_sql)


@pytest.mark.django_db
def test_origem_da_analise_anterior_sobrevive_entrega_atual_pendente(client):
    aluna = Pessoa.objects.create(id_da_plataforma="aluna-ficha", email="aluna@example.test")
    instante = timezone.now()
    AvaliacaoSandboxProjetada.objects.create(
        pessoa=aluna, site_id=SITE, trabalho_id="trabalho-1",
        entrega_id="entrega-2", analise_id="analise-2", versao=2,
        entrega_criada_em=instante, origem_atualizada_em=instante,
        ocorrido_em=instante, event_id=str(uuid4()), atual=True,
        estado="pendente", reconhecida_em=instante - timedelta(days=1),
        reconhecida_versao=1, reconhecida_entrega_id="entrega-1",
        reconhecida_analise_id="analise-1",
    )
    item = _get(client).json()["sandbox"]["avaliacoes"][0]
    assert (item["versao"], item["estado"]) == (2, "pendente")
    assert item["reconhecimento"]["origem"] == {
        "tipo": "avaliacao_sandbox_anterior", "entrega_id": "entrega-1",
        "analise_id": "analise-1", "versao": 1,
        "reconhecida_em": (instante - timedelta(days=1)).isoformat(),
    }


@pytest.mark.django_db
def test_origem_da_faixa_e_avaliacao_da_ordem_sem_presumir_sandbox(client):
    aluna = Pessoa.objects.create(id_da_plataforma="aluna-ficha", email="aluna@example.test")
    avaliacao = AvaliacaoDaJornada.objects.create(
        pessoa=aluna, site_id=SITE, ordem=2, caminho="comum",
        resultado="reconhecida", feedback="Compromisso avaliado.",
        evidencia={"chave": "compromisso-1"}, chave="compromisso-1",
    )
    dados = _get(client).json()
    assert dados["faixa"]["atual"]["ordem"] == 2
    assert dados["faixa"]["origem"] == {
        "tipo": "avaliacao_jornada", "caminho": "comum",
        "avaliada_em": avaliacao.criada_em.isoformat(),
        "entrega_id": None, "analise_id": None,
    }
    assert dados["sandbox"]["avaliacoes"] == []
