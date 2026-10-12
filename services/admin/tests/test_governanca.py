import datetime as dt
from types import SimpleNamespace

import pytest
from django.template.loader import render_to_string

from apps.core import governanca

HOJE = dt.date(2026, 10, 13)


def compra(**campos):
    return {
        "site_id": "mesh",
        "email": "pessoa@example.com",
        "origem": "comprou",
        "status": "ativa",
        "virou_aluno_em": "2026-10-12T03:00:00Z",
        **campos,
    }


def test_compras_low_mid_e_venda_manual_contam_uma_pessoa():
    fichas = [
        compra(product_id="low"),
        compra(product_id="mid", email=" PESSOA@example.com "),
        compra(contato_crm_id="crm", venda_origem="outros", product_id="high"),
    ]
    resultado = governanca.contar_alunos(fichas, "mesh", HOJE)
    assert resultado["total"] == 1
    assert resultado["vendas"] == 3


@pytest.mark.parametrize(
    "campos",
    [
        {"origem": "liberado"},
        {"origem": "administrativo"},
        {"origem": "teste"},
        {"status": "aguardando"},
        {"status": "reembolsada"},
        {"site_id": "outra"},
        {"virou_aluno_em": "2026-10-12T02:59:59Z"},
        {"virou_aluno_em": "2026-10-14T03:00:00Z"},
    ],
)
def test_exclui_base_antiga_testes_e_entradas_inelegiveis(campos):
    assert governanca.contar_alunos([compra(**campos)], "mesh", HOJE)["total"] == 0


def test_compra_nova_de_cadastro_antigo_entra_sem_somar_base():
    fichas = [compra(virou_aluno_em="2026-09-01T12:00:00Z"), compra(status="encerrada")]
    assert governanca.contar_alunos(fichas, "mesh", HOJE)["total"] == 1


def test_nao_exige_contato_crm_para_compra_do_checkout():
    assert governanca.contar_alunos([compra()], "mesh", HOJE)["total"] == 1


def test_fim_da_janela_em_sao_paulo():
    fichas = [
        compra(virou_aluno_em="2028-01-01T02:59:59Z"),
        compra(email="outra@example.com", virou_aluno_em="2028-01-01T03:00:00Z"),
    ]
    assert governanca.contar_alunos(fichas, "mesh", dt.date(2028, 2, 1))["total"] == 1


@pytest.mark.parametrize(
    "fichas", [None, [compra(virou_aluno_em=None)], [compra(email="")]]
)
def test_fonte_incompleta_nao_vira_zero(fichas):
    assert governanca.contar_alunos(fichas, "mesh", HOJE)["total"] is None


def test_ciclos_sucessivos_preservam_metas_e_nao_inventam_futuras():
    primeiro = governanca.calendario(HOJE)
    assert sum(s["low"] or 0 for s in primeiro["semanas"]) == 10000
    assert sum(s["mid"] or 0 for s in primeiro["semanas"]) == 500
    assert primeiro["fim"] == dt.date(2026, 12, 27)
    segundo = governanca.calendario(dt.date(2026, 12, 28))
    assert segundo["numero"] == 2
    assert segundo["inicio"] == primeiro["proximo"]
    assert all(s["low"] is None and s["mid"] is None for s in segundo["semanas"])


def test_orientacao_nao_aparece_para_visitante_ou_equipe_restrita():
    for admin in (None, {"equipe_apenas": True}):
        assert governanca.contexto(SimpleNamespace(admin=admin)) == {}


def test_painel_mostra_contagem_falha_e_fluxo_sem_dados_pessoais():
    contexto = {
        "governanca": governanca.resumo(HOJE),
        "alunos_2027": governanca.contar_alunos([compra()], "mesh", HOJE),
    }
    html = render_to_string("admin/_motor_perpetuo.html", contexto)
    assert "pessoa@example.com" not in html
    assert 'value="1"' in html
    assert "Low · Mid · High ticket" in html
    contexto["alunos_2027"] = governanca.contar_alunos(None, "mesh", HOJE)
    html = render_to_string("admin/_motor_perpetuo.html", contexto)
    assert "Não foi possível consultar" in html
    assert "<progress" not in html


def test_robo_comercial_e_analista_recebem_a_orientacao(monkeypatch):
    from apps.comercial import papeis
    from apps.core import analista

    monkeypatch.setattr(
        papeis, "trecho_das_instrucoes", lambda site: "Identidade da Meshcraft"
    )
    instrucoes = papeis.instrucoes_completas(
        SimpleNamespace(instrucoes="Instruções do papel"), "mesh"
    )
    assert governanca.orientacao_dos_robos() in instrucoes
    dossie = analista.dossie_do_placar({"alunos_2027": {"total": 7}}, HOJE)
    assert "META CENTRAL DE ALUNOS ATÉ 2027" in dossie
    assert "medido hoje: 7" in dossie
