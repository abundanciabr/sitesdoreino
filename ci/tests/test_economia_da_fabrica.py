from __future__ import annotations

from pathlib import Path

import pytest

from ci._nucleo import ErroDeInstrumentacao
from ci.economia_da_fabrica import (
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
    assert "armadilhas/367-sub-agente-sem-model.md" in brief
    assert "372" not in brief
    assert len(brief) < 8_000


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
