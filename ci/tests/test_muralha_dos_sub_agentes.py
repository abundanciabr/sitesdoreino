"""O sub-agente do Claude Code nasce em sonnet ou opus, e pode construir.

A trava mora no ato de criação, porque o roteador de briefs não vê esse ato:
em 12/09/2026 nasceram 45 sub-agentes sem passar por
`ci/economia_da_fabrica.py`. A lei está em CLAUDE.md, seção "Todo pedido do
mantenedor é um lote", e em `docs/decisoes/DECISAO-triade-de-ias.md`.

O modelo é declarado na chamada, nunca herdado: em 19/09/2026 uma sessão em
Fable disparou 26 sub-agentes que herdaram o modelo dela e consumiram 163
milhões de tokens. A lei está em CLAUDE.md, seção "O que uma chamada custa".
Só `sonnet` e `opus` passam, e `Workflow` não passa, porque o modelo dos
agentes dele fica dentro do roteiro.

Em 20/09/2026 o mantenedor levantou o banimento da escrita que a TAR-376 tinha
posto: ficha que escreve passa. O que a ficha ainda não pode é herdar `Agent`
ou `AskUserQuestion`, porque CLAUDE.md diz que nenhum subagente pergunta ao
mantenedor ou cria outro, e `ci/tests/test_fichas_de_robo.py` mede uma tupla
fixa de nomes, que uma ficha nova não atravessa.

INV-CI01: ausência de evidência não é evidência de acerto. Entrada ilegível,
ficha ausente, nome estranho e erro inesperado são recusa, nunca passagem.
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
FICHA_FECHADA = "---\nname: fechada\ndisallowedTools: Agent, AskUserQuestion\n---\ncorpo\n"
FICHA_ABERTA = "---\nname: aberta\ndescription: não declara tools nem disallowedTools\n---\ncorpo\n"


def chamar_bytes(bruto: bytes, raiz: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    ambiente = dict(os.environ, CLAUDE_PROJECT_DIR=str(raiz or RAIZ))
    return subprocess.run(
        [sys.executable, str(GUARDA)],
        input=bruto,
        capture_output=True,
        check=False,
        cwd=RAIZ,
        env=ambiente,
    )


def chamar(entrada: str, raiz: Path | None = None) -> subprocess.CompletedProcess[str]:
    bruto = chamar_bytes(entrada.encode("utf-8"), raiz)
    return subprocess.CompletedProcess(
        bruto.args,
        bruto.returncode,
        bruto.stdout.decode("utf-8", "replace"),
        bruto.stderr.decode("utf-8", "replace"),
    )


def agente(
    tipo: str, modelo: str | None = "sonnet", raiz: Path | None = None
) -> subprocess.CompletedProcess[str]:
    entrada: dict[str, object] = {"subagent_type": tipo}
    if modelo is not None:
        entrada["model"] = modelo
    return chamar(json.dumps({"tool_name": "Agent", "tool_input": entrada}), raiz)


def plantar(tmp_path: Path, nome: str, texto: str, encoding: str = "utf-8") -> Path:
    pasta = tmp_path / ".claude" / "agents"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.md").write_text(texto, encoding=encoding)
    return tmp_path


@pytest.mark.parametrize("tipo", ["despacho", "escrivao", "provador"])
def test_permite_ficha_que_escreve(tipo: str) -> None:
    """O banimento da escrita caiu em 20/09/2026: o construtor volta a nascer."""
    resultado = agente(tipo)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.parametrize(
    "tipo", ["Explore", "revisor", "conferente", "maquinista", "procurador", "adversario"]
)
def test_permite_leitor(tipo: str) -> None:
    resultado = agente(tipo)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_toda_ficha_da_pasta_passa_pelo_guarda() -> None:
    """Ficha nova entra na pasta sem passar pela tupla fixa de test_fichas_de_robo."""
    for ficha in sorted((RAIZ / ".claude" / "agents").glob("*.md")):
        if ficha.name == "LEIA-ME.md":
            continue
        resultado = agente(ficha.stem)
        assert resultado.returncode == 0, f"{ficha.name}: {resultado.stderr}"


@pytest.mark.parametrize("modelo", [None, "fable", "claude-fable-5-1", "haiku", "inherit", ""])
def test_recusa_modelo_que_nao_e_sonnet_nem_opus(modelo: str | None) -> None:
    # guarda: ci/muralha_dos_sub_agentes.py:100
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
    # guarda: ci/muralha_dos_sub_agentes.py:98
    resultado = chamar(json.dumps({"tool_name": "Workflow", "tool_input": {}}))
    assert resultado.returncode == 2
    assert "Workflow" in resultado.stderr


def test_recusa_ficha_que_herda_agent(tmp_path: Path) -> None:
    """Sem `tools` nem `disallowedTools`, a ficha pergunta ao mantenedor e cria outro."""
    # guarda: ci/muralha_dos_sub_agentes.py:111
    resultado = agente("aberta", raiz=plantar(tmp_path, "aberta", FICHA_ABERTA))
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "disallowedTools" in resultado.stderr


def test_permite_ficha_que_fecha_agent(tmp_path: Path) -> None:
    resultado = agente("fechada", raiz=plantar(tmp_path, "fechada", FICHA_FECHADA))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_acha_ficha_salva_com_bom(tmp_path: Path) -> None:
    """Ficha com BOM sumia da lista, e a recusa mandava criar uma ficha que já existe."""
    raiz = plantar(tmp_path, "combom", FICHA_FECHADA, encoding="utf-8-sig")
    assert agente("combom", raiz=raiz).returncode == 0


def test_recusa_ficha_inexistente() -> None:
    resultado = agente("inventado")
    assert resultado.returncode == 2
    assert "inventado" in resultado.stderr


@pytest.mark.parametrize("tipo", ["../escrivao", "a/b", "..", "", "LEIA-ME"])
def test_recusa_nome_que_nao_e_ficha(tipo: str) -> None:
    """`LEIA-ME.md` mora na pasta e não tem frontmatter: é documento, não ficha.

    A recusa precisa ser a do nome, não a rede de segurança do `main`: sem esta
    linha o nome estranho vira KeyError, que também sai com 2 e esconderia o furo.
    """
    # guarda: ci/muralha_dos_sub_agentes.py:109
    resultado = agente(tipo)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "não existe ficha" in resultado.stderr


@pytest.mark.parametrize("entrada", ["", "não-json", "[]", '{"tool_name": "Agent"}'])
def test_recusa_entrada_ilegivel(entrada: str) -> None:
    resultado = chamar(entrada)
    assert resultado.returncode == 2
    assert "ilegível" in resultado.stderr


@pytest.mark.parametrize(
    "bruto",
    [
        b'{"tool_name": "\\udfff", "tool_input": {}}',
        b"[" * 200_000,
        b'{"tool_name": ' + b"9" * 5_000 + b"}",
    ],
    ids=["substituto-solitario", "aninhamento-fundo", "inteiro-gigante"],
)
def test_entrada_hostil_barra_em_vez_de_deixar_passar(bruto: bytes) -> None:
    """Só o código 2 barra: exceção não tratada deixaria o sub-agente nascer."""
    assert chamar_bytes(bruto).returncode == 2


def test_a_recusa_diz_o_que_fazer() -> None:
    """Nome errado sem os nomes certos faz a próxima tentativa ser outro chute."""
    erro = agente("general-purpose").stderr
    assert "despacho" in erro and "revisor" in erro
    assert "LEIA-ME" not in erro


def test_recusa_quando_a_pasta_das_fichas_some(tmp_path: Path) -> None:
    """Sem a pasta, o guarda não pode medir ficha nenhuma, e recusa (INV-CI01)."""
    resultado = agente("revisor", raiz=tmp_path)
    assert resultado.returncode == 2, resultado.stdout + resultado.stderr
    assert "Nenhuma ficha legível" in resultado.stderr
