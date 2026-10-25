import copy
import json
from datetime import datetime
from contextvars import ContextVar
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import Client, RequestFactory

from apps.agentes.super_equipe_percurso import (
    FUSO, coletar, duracoes, periodo, resumir_crm, resumir_escola,
    resumir_ligacao, resumir_quiz,
)
from apps.agentes.views_super_equipe import super_equipe_percurso
from apps.core.models import MembroDaEquipe


@pytest.fixture
def janela():
    return periodo(agora=datetime(2026, 10, 13, 10, tzinfo=FUSO))


@pytest.fixture
def crm():
    return {"filtros": {"site_id": "s"}, "totais": {"elegiveis": 2, "compras_aprovadas": 2},
            "oportunidades": [
                {"id": "o1", "lead_id": "p1", "site_id": "s", "criada_em": "2026-10-12T09:00:00-03:00", "campanha": "sem campanha"},
                {"id": "o2", "lead_id": "p1", "site_id": "s", "criada_em": "2026-10-12T10:00:00-03:00"}],
            "compras": [
                {"pedido_id": "c1", "oportunidade_id": "o1", "lead_id": "p1", "aprovado_em": "2026-10-12T09:01:00-03:00"},
                {"pedido_id": "c2", "oportunidade_id": "o2", "lead_id": "p1", "aprovado_em": "2026-10-12T10:03:00-03:00", "revertida": True}],
            "testes_fora": {"oportunidades": 1, "compras": 3}}


def ficha(**campos):
    return {"site_id": "s", "email": "privado@ensaio.invalid", "origem": "comprou", "status": "ativa",
            "virou_aluno_em": "2026-10-12T09:02:00-03:00", **campos}


def test_periodo_sao_paulo_corta_agora_e_nao_utc(janela):
    assert janela["inicio"] == "2026-10-12"
    assert janela["desde"] == "2026-10-12T00:00:00-03:00"
    assert janela["ate"] == "2026-10-13T10:00:00-03:00"
    assert periodo(janela="45", agora=datetime(2026, 10, 13, tzinfo=FUSO))["inicio"] == "2026-08-30"


@pytest.mark.parametrize("inicio,fim", [("2026-10-14", "2026-10-15"), ("2026-10-13", "2026-10-12"), ("2020-01-01", "2026-10-12"), ("inválido", "")])
def test_periodo_invalido(inicio, fim):
    with pytest.raises(ValueError):
        periodo(inicio, fim, agora=datetime(2026, 10, 13, tzinfo=FUSO))


def test_contato_com_duas_compras_nao_vira_duas_pessoas(crm, janela):
    r = resumir_crm(crm, "s", janela)
    assert (r["oportunidades"], r["contatos"], r["pedidos"], r["compradores"]) == (2, 1, 2, 1)
    assert r["taxa"] == 100 and r["revertidas"] == 1
    assert r["tempos"] == {"amostra": 2, "mediana_s": 120, "p95_s": 180, "min_s": 60, "max_s": 180}
    assert "p1" not in json.dumps(r) and "c1" not in json.dumps(r)


@pytest.mark.parametrize("mudanca", ["truncado", "outra_escola", "duplicado", "futuro", "outra_pessoa"])
def test_leitura_parcial_nao_fabrica_taxa(crm, janela, mudanca):
    if mudanca == "truncado":
        crm["totais"]["compras_aprovadas"] = 30000
    elif mudanca == "outra_escola":
        crm["oportunidades"][0]["site_id"] = "outro"
    elif mudanca == "duplicado":
        crm["compras"].append(copy.deepcopy(crm["compras"][0]))
    elif mudanca == "futuro":
        crm["compras"][0]["aprovado_em"] = "2026-10-14T00:00:00-03:00"
    else:
        crm["compras"][0]["lead_id"] = "alguem-mais"
    r = resumir_crm(crm, "s", janela)
    assert r["estado"] == "parcial" and r["taxa"] is None


def test_tempo_invertido_e_ausente_nao_viram_zero(crm, janela):
    crm["compras"][0]["aprovado_em"] = "2026-10-11T09:00:00-03:00"
    crm["compras"][1]["aprovado_em"] = None
    r = resumir_crm(crm, "s", janela)
    assert r["invertidos"] == 1 and r["sem_tempo"] == 1
    assert r["tempos"]["amostra"] == 0 and r["tempos"]["mediana_s"] is None


def test_api_crm_de_outro_site_rejeitada(crm, janela):
    with pytest.raises(ValueError):
        resumir_crm(crm, "outro", janela)


def test_escola_deduplica_e_preserva_base_anterior(janela):
    fichas = [ficha(), ficha(email=" PRIVADO@ENSAIO.INVALID "),
              ficha(virou_aluno_em="2026-10-10T09:00:00-03:00"),
              ficha(site_id="outro"), ficha(origem="sandbox"), ficha(origem="liberado"),
              ficha(status="reembolsada")]
    r = resumir_escola(fichas, "s", janela)
    assert (r["matriculas"], r["pessoas"], r["pessoas_com_registro_anterior"], r["pessoas_sem_registro_anterior"]) == (2, 1, 1, 0)
    assert r["reembolsadas"] == 1
    assert "privado" not in json.dumps(r)


def test_data_digitada_nao_substitui_data_de_liberacao(janela):
    r = resumir_escola([ficha(virou_aluno_em=None, comprou_em="2026-10-12"), ficha(email="")], "s", janela)
    assert r["sem_data"] == 1 and r["sem_identidade"] == 1 and r["estado"] == "parcial"


def test_contato_direto_associa_pessoa_sem_inventar_pedido(crm, janela):
    r = resumir_ligacao(crm, [ficha(contato_crm_id="p1"), ficha(), ficha(site_id="outro", contato_crm_id="p1")], "s", janela)
    assert r["com_matricula"] == 1 and r["compradores_observados"] == 1
    assert r["matriculas_sem_contato"] == 1 and "tempo compra" in r["limite"]


def test_quiz_conta_sessoes_da_mesma_populacao():
    r = resumir_quiz("q", {"funil": {"visitas_elegiveis": 10,
        "versoes": [{"conclusoes": 3, "saidas_reais": 2}],
        "conclusoes_sem_visita": 7, "teste": {"visitas": 4, "conclusoes": 1}}})
    assert r["taxa"] == 30 and r["orfas"] == 7 and r["teste_visitas"] == 4
    assert duracoes([])["mediana_s"] is None


def test_falha_de_fonte_nao_derruba_as_demais(crm, janela):
    with patch("apps.core.conteudos.pedir_por_host", return_value=(503, None)), \
         patch("apps.core.clients.LeadsClient._pedir", return_value=("ok", crm)), \
         patch("apps.core.clients.AlunosClient.alunos", return_value=[ficha()]):
        r = coletar("s", "meshcraft.top", janela)
    assert r["inventario"]["estado"] == "indisponivel" and r["escola"]["matriculas"] == 1
    assert "privado@" not in json.dumps(r)


def test_sem_site_nao_consulta_outra_escola(janela):
    with patch("apps.core.clients.AlunosClient.alunos") as fonte:
        r = coletar(None, "meshcraft.top", janela)
    fonte.assert_not_called()
    assert r["escola"]["estado"] == "indisponivel"


def test_leituras_concorrentes_preservam_contexto_do_modulo(crm, janela):
    contexto = ContextVar("modulo_do_ensaio", default=None)
    token = contexto.set("admin")
    vistos = []
    def quiz(*args, **kwargs):
        vistos.append(contexto.get())
        return (200, {"items": [{"slug": "q"}]}) if len(args) == 3 else (503, None)
    def ler_crm(*args, **kwargs):
        vistos.append(contexto.get())
        return "ok", crm
    def escola(*args):
        vistos.append(contexto.get())
        return []
    try:
        with patch("apps.core.conteudos.pedir_por_host", side_effect=quiz), \
             patch("apps.core.clients.LeadsClient._pedir", side_effect=ler_crm), \
             patch("apps.core.clients.AlunosClient.alunos", side_effect=escola):
            r = coletar("s", "meshcraft.top", janela)
        assert len(vistos) == 4 and set(vistos) == {"admin"}
        assert r["crm"]["pedidos"] == 2
    finally:
        contexto.reset(token)


@pytest.mark.parametrize("admin", [None, {"equipe_apenas": True}])
def test_view_rejeita_antes_de_ler(admin):
    request = RequestFactory().get("/super-equipe/percurso-comercial/")
    request.admin = admin
    with patch("apps.agentes.super_equipe_percurso.coletar") as fonte:
        assert super_equipe_percurso(request).status_code == 403
    fonte.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("papel", ["anonimo", "aluno", "professor", "membro", "admin"])
@pytest.mark.parametrize("formato", ["html", "json"])
def test_porta_real_com_identidades_simuladas(settings, monkeypatch, papel, formato, janela):
    settings.ADMIN_EMAILS = "admin@ensaio.invalid"
    monkeypatch.setenv("ADMIN_EMAILS", "admin@ensaio.invalid")
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "somente-ensaio-isolado")
    MembroDaEquipe.objects.create(nome="Admin do ensaio", email="admin@ensaio.invalid")
    MembroDaEquipe.objects.create(nome="Membro", email="membro@ensaio.invalid")
    cliente = Client()
    if papel != "anonimo":
        cliente.cookies["meshcraft_sessao"] = "somente-sessao-isolada"
    with respx.mock(assert_all_called=False) as mock, \
         patch("apps.agentes.views_super_equipe._site", return_value=("meshcraft.top", "s")), \
         patch("apps.agentes.super_equipe_percurso.coletar", return_value={"periodo": janela, "prova": "AGREGADO_PRIVADO"}) as fonte:
        mock.get("http://identidade:8000/interno/sessao/completa").mock(return_value=httpx.Response(200, json={
            "autenticado": True, "id": "ensaio", "nome_exibido": "Ensaio", "email": f"{papel}@ensaio.invalid", "papel": papel}))
        resposta = cliente.get("/super-equipe/percurso-comercial/", {"formato": formato})
    assert resposta.status_code == (302 if papel == "anonimo" else 200 if papel == "admin" else 403)
    if papel != "admin":
        fonte.assert_not_called()
        assert b"AGREGADO_PRIVADO" not in resposta.content
    else:
        assert resposta["Cache-Control"] == "private, no-store"
