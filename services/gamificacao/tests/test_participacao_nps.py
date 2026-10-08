import pytest

from apps.core import api, participacao, views
from apps.gamificacao.models import Pessoa, PerfilJogador, NivelDefinicao


@pytest.mark.django_db
def test_perfil_publico_some_imediatamente_e_nao_reaparece_na_recuperacao(monkeypatch):
    monkeypatch.setenv("SITE_ID", "escola")
    pessoa = Pessoa.objects.create(id_da_plataforma="aluno", email="aluno@example.test")
    PerfilJogador.objects.create(pessoa=pessoa, site_id="escola", nivel=1)
    NivelDefinicao.objects.create(site_id="escola", nivel=1, xp_necessario=0, titulo="Aprendiz", ativa=True)
    estado = {"segmento": "promotor", "embaixador": True, "conquistas_privadas_ate": None}
    monkeypatch.setattr(api, "estados_participacao", lambda ids: {"aluno": estado})
    assert "aluno" in api.get_public_profiles(None, "aluno")
    estado.update(segmento="detrator", conquistas_privadas_ate="2026-10-08T00:00:00Z")
    assert api.get_public_profiles(None, "aluno") == {}
    estado["segmento"] = "promotor"
    assert api.get_public_profiles(None, "aluno") == {}
    assert PerfilJogador.objects.get(pessoa=pessoa).nivel == 1


@pytest.mark.django_db
def test_dono_continua_vendo_selo_historico_na_colecao(client, monkeypatch):
    monkeypatch.setattr(views, "site_atual", lambda: "escola")
    monkeypatch.setattr(views, "quem_e", lambda request: "aluno")
    monkeypatch.setattr(views, "minha_participacao", lambda pessoa: {"segmento": "detrator", "embaixador": True, "conquistas_privadas_ate": "2026-10-08T00:00:00Z"})
    resposta = client.get("/medalhas")
    assert resposta.status_code == 200
    assert b"Aluno Embaixador" in resposta.content


@pytest.mark.django_db
def test_indisponibilidade_da_avaliacao_nao_expoe_perfil(monkeypatch):
    monkeypatch.setenv("SITE_ID", "escola")
    pessoa = Pessoa.objects.create(id_da_plataforma="aluno", email="aluno@example.test")
    PerfilJogador.objects.create(pessoa=pessoa, site_id="escola", nivel=1)
    monkeypatch.setattr(api, "estados_participacao", lambda ids: {})
    assert api.get_public_profiles(None, "aluno") == {}


def test_estado_sem_avaliacao_nao_inventa_restricao():
    assert participacao.publica({"segmento": "sem_avaliacao", "conquistas_privadas_ate": None})
    assert not participacao.publica({})
