"""A CATRACA DE TESTES — teste não some em silêncio (Onda 6, O11/B15).

A regra "teste não se deleta, desativa nem afrouxa" existe desde a fundação
(`RITOS.md` §2.3, Lei 6) e era **só texto**: a única parte mecanizada cobria os
testes de invariante declarados. Todo o resto dependia de alguém reparar numa
linha a menos no meio de um diff grande.

Estes testes cobrem as três formas de um teste sumir — e a forma de o próprio
portão falhar, que é a mais importante das quatro:

    apagar o arquivo          · reduzir a contagem  · desligar com skip
    e: não conseguir medir  ->  ERROR, nunca "nada sumiu"
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import catraca_de_testes as catraca  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402

UM_TESTE = "def test_a():\n    assert True\n"
DOIS_TESTES = UM_TESTE + "\n\ndef test_b():\n    assert True\n"


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(raiz), check=True, capture_output=True, timeout=120
    )


def _repo(tmp_path: Path, conteudo: str = DOIS_TESTES) -> Path:
    raiz = tmp_path / "repo"
    (raiz / "ci" / "tests").mkdir(parents=True)
    (raiz / "services" / "quiz" / "tests").mkdir(parents=True)
    (raiz / "contracts").mkdir()
    (raiz / "contracts" / "LEIA-ME.md").write_text("c", encoding="utf-8")
    for marca in ("CONSTITUICAO.md", "INVARIANTES.md"):
        (raiz / marca).write_text("cenario", encoding="utf-8")
    (raiz / "services" / "quiz" / "tests" / "test_algo.py").write_text(
        conteudo, encoding="utf-8"
    )
    _git(raiz, "init", "-q", "-b", "main")
    _git(raiz, "config", "user.email", "t@e")
    _git(raiz, "config", "user.name", "t")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "base")
    return raiz


def _commit(raiz: Path, mudanca) -> None:
    mudanca(raiz)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-qm", "mudanca")


ALVO = Path("services") / "quiz" / "tests" / "test_algo.py"


# --------------------------------------------------------------------------
# As três formas de sumir
# --------------------------------------------------------------------------


def test_arquivo_de_teste_apagado_reprova(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commit(raiz, lambda r: (r / ALVO).unlink())
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = catraca.rodar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "APAGADO" in relatorio.render()


def test_menos_testes_no_mesmo_arquivo_reprova(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commit(raiz, lambda r: (r / ALVO).write_text(UM_TESTE, encoding="utf-8"))
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = catraca.rodar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "2 → 1" in relatorio.render()


@pytest.mark.parametrize(
    "desligador",
    [
        "@pytest.mark.skip\ndef test_c():\n    assert True\n",
        "@pytest.mark.skipif(True, reason='x')\ndef test_c():\n    assert True\n",
        "@pytest.mark.xfail\ndef test_c():\n    assert True\n",
        "pytestmark = pytest.mark.skip\n\ndef test_c():\n    assert True\n",
    ],
)
def test_teste_desligado_reprova_mesmo_somando_testes(
    tmp_path: Path, monkeypatch, desligador: str
):
    """O caso mais escorregadio: a CONTAGEM sobe e a suíte encolhe.

    Quem só olhasse o número de `def test_` veria dois virarem três e diria que
    o PR acrescentou teste. Desligar é subtrair sem parecer.
    """
    raiz = _repo(tmp_path)
    _commit(
        raiz,
        lambda r: (r / ALVO).write_text(DOIS_TESTES + "\n\n" + desligador, encoding="utf-8"),
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    relatorio = catraca.rodar(raiz)
    assert relatorio.estado is Estado.FAIL, relatorio.render()
    assert "DESLIGADO" in relatorio.render()


# --------------------------------------------------------------------------
# O que passa
# --------------------------------------------------------------------------


def test_acrescentar_teste_passa(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commit(
        raiz,
        lambda r: (r / ALVO).write_text(
            DOIS_TESTES + "\n\ndef test_c():\n    assert True\n", encoding="utf-8"
        ),
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    assert catraca.rodar(raiz).estado is Estado.PASS


def test_arquivo_de_teste_NOVO_passa(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commit(
        raiz,
        lambda r: (r / "ci" / "tests" / "test_novo.py").write_text(
            UM_TESTE, encoding="utf-8"
        ),
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    assert catraca.rodar(raiz).estado is Estado.PASS


def test_mexer_em_codigo_que_nao_e_teste_passa(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    _commit(
        raiz,
        lambda r: (r / "services" / "quiz" / "app.py").write_text("x = 1\n", encoding="utf-8"),
    )
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.delenv("PR_LABELS", raising=False)
    assert catraca.rodar(raiz).estado is Estado.PASS


def test_a_etiqueta_autoriza_e_o_achado_fica_no_log(tmp_path: Path, monkeypatch, capsys):
    """Autorizar não é apagar — a perda continua listada, item por item."""
    raiz = _repo(tmp_path)
    _commit(raiz, lambda r: (r / ALVO).unlink())
    monkeypatch.setenv("BASE_REF", "HEAD~1")
    monkeypatch.setenv("PR_LABELS", f"algo,{catraca.ETIQUETA}")
    relatorio = catraca.rodar(raiz)
    impresso = capsys.readouterr().out
    assert relatorio.estado is Estado.PASS, relatorio.render()
    assert "test_algo.py" in impresso


# --------------------------------------------------------------------------
# O portão como instrumento
# --------------------------------------------------------------------------


def test_base_inalcancavel_e_ERROR_nunca_nada_sumiu(tmp_path: Path, monkeypatch):
    raiz = _repo(tmp_path)
    monkeypatch.setenv("BASE_REF", "nao-existe-esta-ref")
    with pytest.raises(ErroDeInstrumentacao):
        catraca.rodar(raiz)


@pytest.mark.parametrize(
    "caminho,esperado",
    [
        ("services/quiz/tests/test_x.py", True),
        ("ci/tests/test_x.py", True),
        ("painel/testes/teste_logica.js", True),
        ("e2e/painel_no_navegador.js", True),
        ("services/quiz/tests/conftest.py", False),
        ("services/quiz/app.py", False),
        ("RITOS.md", False),
    ],
)
def test_o_que_conta_como_arquivo_de_teste(caminho: str, esperado: bool):
    assert catraca.e_arquivo_de_teste(caminho) is esperado


def test_o_portao_esta_na_muralha():
    fonte = (RAIZ / "ci" / "ci.py").read_text(encoding="utf-8")
    assert "ci/catraca-de-testes.sh" in fonte


def test_a_muralha_reprova_de_verdade(tmp_path: Path):
    from conftest import BASH

    if BASH is None:
        pytest.skip("sem bash utilizável")
    raiz = _repo(tmp_path)
    _commit(raiz, lambda r: (r / ALVO).unlink())
    for arquivo in ("catraca_de_testes.py", "_nucleo.py", "catraca-de-testes.sh"):
        shutil.copy(RAIZ / "ci" / arquivo, raiz / "ci" / arquivo)
    proc = subprocess.run(
        [BASH, str(raiz / "ci" / "catraca-de-testes.sh")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env={**__import__("os").environ, "BASE_REF": "HEAD~1", "PR_LABELS": ""},
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "APAGADO" in proc.stdout
