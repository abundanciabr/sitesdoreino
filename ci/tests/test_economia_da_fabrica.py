from __future__ import annotations

from pathlib import Path

import pytest
import shutil

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

    assert "modelo_recomendado: gpt-5.6-sol" in brief
    assert "executor: codex" in brief
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
    shutil.copyfile(Path(__file__).resolve().parents[2] / ".claude/agents/despacho.md", pasta / "despacho.md")

    assert auditar_fichas(tmp_path) == []


def test_auditoria_recusa_despacho_claude_com_poder_de_executor(
    tmp_path: Path,
) -> None:
    pasta = tmp_path / ".claude" / "agents"
    pasta.mkdir(parents=True)
    (pasta / "despacho.md").write_text(
        "---\nname: despacho\n---\nExija modelo_recomendado no brief.\n",
        encoding="utf-8",
    )

    assert any("encaminhamento" in falha for falha in auditar_fichas(tmp_path))


@pytest.mark.parametrize("ferramenta", ["Bash", "Edit", "Write", "NotebookEdit", "Agent", "mcp__servidor__executar"])
def test_auditoria_recusa_capacidade_extra_no_encaminhamento(tmp_path, ferramenta):
    # guarda: ci/economia_da_fabrica.py:233
    pasta = tmp_path / ".claude/agents"
    pasta.mkdir(parents=True)
    (pasta / "despacho.md").write_text(
        "---\nname: despacho\nmodel: sonnet\neffort: medium\n"
        f"tools: Read, {ferramenta}\n"
        "disallowedTools: Bash, Edit, Write, NotebookEdit, Agent, AskUserQuestion\n"
        "---\nEncaminhar ao Codex.\n", encoding="utf-8",
    )
    assert any("encaminhamento" in falha for falha in auditar_fichas(tmp_path))


def test_auditoria_aceita_encaminhamento_claude_somente_leitura(tmp_path):
    pasta = tmp_path / ".claude/agents"
    pasta.mkdir(parents=True)
    (pasta / "despacho.md").write_text(
        "---\nname: despacho\nmodel: sonnet\neffort: medium\n"
        "tools: Read, Grep, Glob\n"
        "disallowedTools: Bash, Edit, Write, NotebookEdit, Agent, AskUserQuestion\n"
        "---\nEncaminhar ao Codex.\n", encoding="utf-8",
    )
    assert auditar_fichas(tmp_path) == []


@pytest.mark.parametrize("campo,valor", [("name", "executor"), ("model", "opus"), ("effort", "high"), ("tools", ""), ("tools", "Read"), ("tools", "Read, Grep"), ("tools", "Read, Glob"), ("tools", "Grep, Glob"), ("disallowedTools", "Agent, AskUserQuestion")])
def test_auditoria_recusa_identidade_custo_ou_permissoes_incorretas(tmp_path, campo, valor):
    pasta = tmp_path / ".claude/agents"
    pasta.mkdir(parents=True)
    campos = {"name": "despacho", "model": "sonnet", "effort": "medium",
              "tools": "Read, Grep, Glob",
              "disallowedTools": "Bash, Edit, Write, NotebookEdit, Agent, AskUserQuestion"}
    campos[campo] = valor
    texto = "---\n" + "\n".join(f"{k}: {v}" for k, v in campos.items()) + "\n---\nEncaminhar ao Codex.\n"
    (pasta / "despacho.md").write_text(texto, encoding="utf-8")
    assert any("encaminhamento" in falha for falha in auditar_fichas(tmp_path))


def test_auditoria_codex_tambem_confere_encaminhamento_claude(tmp_path, monkeypatch):
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    shutil.copytree(Path(__file__).resolve().parents[2] / ".codex/agents", tmp_path / ".codex/agents")
    pasta = tmp_path / ".claude/agents"
    pasta.mkdir(parents=True)
    (pasta / "despacho.md").write_text("---\nname: despacho\nmodel: sonnet\ntools: Bash\n---\nExecutar.\n", encoding="utf-8")
    assert any("encaminhamento" in falha for falha in auditar_fichas(tmp_path))


def test_auditoria_codex_recusa_ficha_claude_ausente(tmp_path, monkeypatch):
    # guarda: ci/economia_da_fabrica.py:225
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    shutil.copytree(Path(__file__).resolve().parents[2] / ".codex/agents", tmp_path / ".codex/agents")
    (tmp_path / ".claude/agents").mkdir(parents=True)
    assert any("falta a ficha de encaminhamento" in falha for falha in auditar_fichas(tmp_path))


def test_compilador_nao_despacha_espera_ao_executor(tmp_path):
    # guarda: ci/economia_da_fabrica.py:276
    with pytest.raises(ErroDeInstrumentacao, match="espera não é implementação"):
        compilar_brief(tmp_path, objetivo="Acompanhar a pista", tipo="espera",
                       celula="ci", alvos=["ci/esperar.py"], armadilhas=[])


@pytest.mark.parametrize("harness", ["claude", "codex"])
@pytest.mark.parametrize("tipo,modelo", [("texto", "gpt-5.6-sol"), ("contrato", "gpt-6-astra")])
def test_brief_de_implementacao_destina_modelo_ao_codex(tmp_path, monkeypatch, harness, tipo, modelo):
    # guarda: ci/economia_da_fabrica.py:278
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: harness)
    brief = compilar_brief(tmp_path, objetivo="Implementar decisão recebida", tipo=tipo,
                           celula="ci", alvos=["ci/alvo.py"], armadilhas=[])
    assert "executor: codex" in brief
    assert f"modelo_recomendado: {modelo}" in brief

@pytest.fixture(autouse=True)
def harness_claude_das_fixtures(monkeypatch):
    # Estas fixtures medem a compatibilidade das fichas Markdown do Claude.
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "claude")
