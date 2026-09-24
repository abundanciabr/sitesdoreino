from __future__ import annotations

from pathlib import Path

import pytest

from _nucleo import ErroDeInstrumentacao
from economia_da_fabrica import (
    MODELO_ROTINA,
    MODELO_TOPO,
    auditar_fichas,
    classificar,
    compilar_brief,
    perfil_por_tipo,
)


def test_roteador_reserva_modelo_de_topo_para_contrato_e_produto() -> None:
    assert perfil_por_tipo("contrato").modelo == MODELO_TOPO
    assert perfil_por_tipo("produto").modelo == MODELO_TOPO
    assert perfil_por_tipo("revisao").modelo == MODELO_ROTINA
    assert perfil_por_tipo("escrita").modelo == MODELO_ROTINA


def test_codex_usa_sol_por_padrao_e_luna_so_em_tarefas_delimitadas(monkeypatch) -> None:
    from economia_da_fabrica import MODELOS_CODEX

    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    assert MODELOS_CODEX == {"rotina": "gpt-6-sol", "delimitado": "gpt-6-luna"}
    assert perfil_por_tipo("geral").modelo == "gpt-6-sol"
    assert perfil_por_tipo("geral").esforco == "medium"
    assert classificar("trabalho sem categoria indicada").modelo == "gpt-6-sol"
    assert classificar("trabalho sem categoria indicada").esforco == "medium"
    # guarda: ci/economia_da_fabrica.py:46
    for tipo in (
        "arquitetura",
        "contrato",
        "produto",
        "revisao",
        "diagnostico",
        "teste",
        "texto",
    ):
        assert perfil_por_tipo(tipo).modelo == "gpt-6-sol"
    # guarda: ci/economia_da_fabrica.py:48
    for tipo in ("escrita", "espera"):
        assert perfil_por_tipo(tipo).modelo == "gpt-6-luna"
        assert perfil_por_tipo(tipo).esforco == "high"


def test_fichas_codex_fixam_sol_e_despacho_exige_brief_roteado(monkeypatch) -> None:
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")

    assert auditar_fichas(raiz) == []


def test_classificador_prefere_contrato_quando_o_texto_fala_de_freeze() -> None:
    perfil = classificar("congelar OpenAPI e ajustar freeze da célula cursos")

    assert perfil.tipo == "contrato"
    assert perfil.modelo == MODELO_TOPO


def test_brief_compilado_injeta_so_a_armadilha_citada(tmp_path: Path) -> None:
    raiz = tmp_path
    pasta = raiz / "armadilhas"
    pasta.mkdir()
    (pasta / "367-sub-agente-sem-model.md").write_text(
        "---\narmadilha: 367\n---\n# 367 — Sub-agente sem model\n\ncorpo longo\n",
        encoding="utf-8",
    )
    (pasta / "372-claude-md-engordou.md").write_text(
        "---\narmadilha: 372\n---\n# 372 — CLAUDE.md engordou\n\ncorpo longo\n",
        encoding="utf-8",
    )

    brief = compilar_brief(
        raiz,
        objetivo="Revisar PR sem herdar contexto caro",
        tipo="revisao",
        celula="ci",
        alvos=["ci/economia_da_fabrica.py"],
        armadilhas=["367"],
    )

    assert "modelo_recomendado: sonnet" in brief
    assert "teto_de_contexto" not in brief
    assert "armadilhas/367-sub-agente-sem-model.md" in brief
    assert "372" not in brief


def test_brief_sem_alvo_para_em_vez_de_abrir_exploracao(tmp_path: Path) -> None:
    with pytest.raises(ErroDeInstrumentacao, match="brief sem arquivos-alvo"):
        compilar_brief(
            tmp_path,
            objetivo="fazer economia",
            tipo="diagnostico",
            celula="ci",
            alvos=[],
            armadilhas=[],
        )


def test_auditoria_reprova_revisor_sem_model(tmp_path: Path) -> None:
    pasta = tmp_path / ".claude" / "agents"
    pasta.mkdir(parents=True)
    (pasta / "revisor.md").write_text(
        "---\nname: revisor\ntools: Read\n---\ntexto\n",
        encoding="utf-8",
    )

    falhas = auditar_fichas(tmp_path)

    assert ".claude/agents/revisor.md: revisor precisa declarar model" in falhas


def test_auditoria_aceita_revisor_com_modelo_de_rotina(tmp_path: Path) -> None:
    pasta = tmp_path / ".claude" / "agents"
    pasta.mkdir(parents=True)
    (pasta / "revisor.md").write_text(
        "---\nname: revisor\nmodel: sonnet\ntools: Read\n---\ntexto\n",
        encoding="utf-8",
    )

    assert auditar_fichas(tmp_path) == []


def test_auditoria_aceita_despacho_variavel_quando_exige_modelo_no_brief(
    tmp_path: Path,
) -> None:
    pasta = tmp_path / ".claude" / "agents"
    pasta.mkdir(parents=True)
    (pasta / "despacho.md").write_text(
        "---\nname: despacho\n---\nExija modelo_recomendado no brief.\n",
        encoding="utf-8",
    )

    assert auditar_fichas(tmp_path) == []

@pytest.fixture(autouse=True)
def harness_claude_das_fixtures(monkeypatch):
    # Estas fixtures medem a compatibilidade das fichas Markdown do Claude.
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "claude")
