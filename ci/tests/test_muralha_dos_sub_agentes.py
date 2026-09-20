"""O Claude Code não dispara sub-agente que escreva, nem sub-agente fora de sonnet ou opus.

A trava mora no ato de criação, porque o roteador de briefs não vê esse ato:
em 12/09/2026 nasceram 45 sub-agentes sem passar por
`ci/economia_da_fabrica.py`. A lei está em CLAUDE.md, seção "Todo pedido do
mantenedor é um lote", e em `docs/decisoes/DECISAO-triade-de-ias.md`.

A régua do guarda é a própria ficha: quem declara `tools` sem Edit, Write ou
NotebookEdit passa; quem herda tudo, ou pede escrita, é recusado e o trabalho
vai para a fila. Lista fixa de nomes envelheceria a cada ficha nova, e cinco
leitoras entraram em 18/09/2026 pela TAR-464.

O modelo é declarado na chamada, nunca herdado: em 19/09/2026 uma sessão em
Fable disparou 26 sub-agentes que herdaram o modelo dela e consumiram 163
milhões de tokens. A lei está em CLAUDE.md, seção "O que uma chamada custa".
Só `sonnet` e `opus` passam; ausente, Fable ou qualquer outro é recusa.

INV-CI01: ausência de evidência não é evidência de acerto. Entrada ilegível,
ficha ausente ou nome estranho são recusa, nunca passagem.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = RAIZ / "ci" / "muralha_dos_sub_agentes.py"


def chamar(entrada: str, raiz: Path | None = None) -> subprocess.CompletedProcess[str]:
    ambiente = dict(os.environ, CLAUDE_PROJECT_DIR=str(raiz or RAIZ))
    return subprocess.run(
        [sys.executable, str(GUARDA)],
        input=entrada,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=RAIZ,
        env=ambiente,
    )


def agente(tipo: str, modelo: str | None = "sonnet") -> subprocess.CompletedProcess[str]:
    entrada: dict[str, object] = {"subagent_type": tipo}
    if modelo is not None:
        entrada["model"] = modelo
    return chamar(json.dumps({"tool_name": "Agent", "tool_input": entrada}))


@pytest.mark.parametrize("tipo", ["despacho", "escrivao", "provador"])
def test_recusa_ficha_que_escreve(tipo: str) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:81
    resultado = agente(tipo)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "python ci/fila.py criar" in resultado.stderr


@pytest.mark.parametrize(
    "tipo", ["Explore", "revisor", "conferente", "maquinista", "procurador", "adversario"]
)
def test_permite_leitor(tipo: str) -> None:
    resultado = agente(tipo)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.parametrize("modelo", [None, "fable", "claude-fable-5-1", "haiku", "inherit", ""])
def test_recusa_modelo_que_nao_e_sonnet_nem_opus(modelo: str | None) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:70
    resultado = agente("Explore", modelo)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "sonnet" in resultado.stderr and "opus" in resultado.stderr
    assert "economia_da_fabrica" in resultado.stderr


@pytest.mark.parametrize("modelo", ["sonnet", "opus"])
def test_permite_sonnet_e_opus(modelo: str) -> None:
    resultado = agente("Explore", modelo)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_modelo_e_julgado_antes_da_ficha() -> None:
    """Leitor com ficha válida e modelo herdado é recusa pelo modelo, não passagem."""
    resultado = agente("revisor", None)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "herda" in resultado.stderr


def test_recusa_workflow() -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:68
    resultado = chamar(json.dumps({"tool_name": "Workflow", "tool_input": {}}))
    assert resultado.returncode == 2
    assert "Workflow" in resultado.stderr


def test_recusa_ficha_inexistente() -> None:
    resultado = agente("inventado")
    assert resultado.returncode == 2
    assert "inventado" in resultado.stderr


@pytest.mark.parametrize("tipo", ["../escrivao", "a/b", "..", ""])
def test_recusa_nome_que_nao_e_ficha(tipo: str) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:79
    assert agente(tipo).returncode == 2


@pytest.mark.parametrize("entrada", ["", "não-json", "[]", '{"tool_name": "Agent"}'])
def test_recusa_entrada_ilegivel(entrada: str) -> None:
    resultado = chamar(entrada)
    assert resultado.returncode == 2
    assert "ilegível" in resultado.stderr


def test_a_recusa_diz_o_que_fazer() -> None:
    erro = agente("despacho").stderr
    assert "python ci/fila.py criar" in erro
    assert "Explore" in erro


def test_recusa_quando_a_pasta_das_fichas_some(tmp_path: Path) -> None:
    """Sem a pasta, o guarda não pode medir ficha nenhuma, e recusa (INV-CI01)."""
    entrada = json.dumps(
        {"tool_name": "Agent", "tool_input": {"subagent_type": "revisor", "model": "sonnet"}}
    )
    resultado = chamar(entrada, raiz=tmp_path)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "não existe ficha" in resultado.stderr
