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


def test_codex_usa_luna_high_em_todos_os_tipos(monkeypatch) -> None:
    from economia_da_fabrica import PERFIS

    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    # guarda: ci/economia_da_fabrica.py:45
    for tipo in PERFIS:
        perfil = perfil_por_tipo(tipo)
        assert (perfil.modelo, perfil.esforco) == ("gpt-6-luna", "high"), tipo
    perfil = classificar("trabalho sem categoria indicada")
    assert (perfil.modelo, perfil.esforco) == ("gpt-6-luna", "high")


def test_configuracao_codex_preserva_principal_e_nao_impoe_tetos():
    import tomllib
    raiz = Path(__file__).resolve().parents[2]
    config = tomllib.loads((raiz / ".codex/config.toml").read_text(encoding="utf-8"))
    assert "model" not in config and "model_reasoning_effort" not in config
    assert config["agents"] == {
        "enabled": True,
        "default_subagent_model": "gpt-6-luna",
        "default_subagent_reasoning_effort": "high",
    }


def test_fichas_codex_fixam_luna_high_sem_bloquear_descendentes(monkeypatch):
    import tomllib
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    assert auditar_fichas(raiz) == []
    for caminho in (raiz / ".codex/agents").glob("*.toml"):
        ficha = tomllib.loads(caminho.read_text(encoding="utf-8"))
        assert (ficha["model"], ficha["model_reasoning_effort"]) == ("gpt-6-luna", "high")
        texto = " ".join(ficha["developer_instructions"].split())
        assert "Não dispare subagentes" not in texto
        assert "gpt-6-luna" in texto and "high" in texto


@pytest.mark.parametrize("campo,valor", [("model", "gpt-6-sol"), ("model_reasoning_effort", "medium")])
def test_auditoria_recusa_ficha_que_sobrescreve_luna_high(tmp_path, monkeypatch, campo, valor):
    import shutil
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    shutil.copytree(raiz / ".codex", tmp_path / ".codex")
    caminho = tmp_path / ".codex/agents/revisor.toml"
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    linhas = [f'{campo} = "{valor}"' if linha.startswith(campo + " =") else linha for linha in linhas]
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    # guarda: ci/economia_da_fabrica.py:212
    # guarda: ci/economia_da_fabrica.py:214
    assert any(campo in falha for falha in auditar_fichas(tmp_path))


@pytest.mark.parametrize("campo,valor", [("default_subagent_model", "gpt-6-sol"), ("default_subagent_reasoning_effort", "medium"), ("enabled", False)])
def test_auditoria_recusa_padrao_de_descendentes_incorreto(tmp_path, monkeypatch, campo, valor):
    import shutil
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    shutil.copytree(raiz / ".codex", tmp_path / ".codex")
    caminho = tmp_path / ".codex/config.toml"
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    literal = "false" if valor is False else f'"{valor}"'
    linhas = [f'{campo} = {literal}' if linha.startswith(campo + " =") else linha for linha in linhas]
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    # guarda: ci/economia_da_fabrica.py:196
    assert any(campo in falha for falha in auditar_fichas(tmp_path))


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


@pytest.mark.parametrize("conteudo", [None, "[agents", "agents = []"])
def test_auditoria_configuracao_ausente_ou_ilegivel_nao_aprova(tmp_path, monkeypatch, conteudo):
    import shutil
    raiz = Path(__file__).resolve().parents[2]
    monkeypatch.setattr("economia_da_fabrica.harness_ativo", lambda raiz=None: "codex")
    shutil.copytree(raiz / ".codex", tmp_path / ".codex")
    config = tmp_path / ".codex/config.toml"
    if conteudo is None:
        config.unlink()
    else:
        config.write_text(conteudo, encoding="utf-8")
    if conteudo == "agents = []":
        assert auditar_fichas(tmp_path)
    else:
        with pytest.raises(ErroDeInstrumentacao, match="configuração de agentes indisponível"):
            auditar_fichas(tmp_path)
