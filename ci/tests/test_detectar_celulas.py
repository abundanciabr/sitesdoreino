"""O detector de células do deploy: autônomo e fiel ao mapa `celulas.yml`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import detectar_celulas

CELULAS_YML = """\
celulas:
  alunos:
    caminhos: [services/alunos]
    consome: []
    compartilhados: [packages/site_errors]
  quiz:
    caminhos: [services/quiz]
    consome: [alunos]
    compartilhados: [packages/site_errors]
"""


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=raiz,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(raiz: Path, *caminhos: str) -> None:
    for c in caminhos:
        arq = raiz / c
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(arq.read_text() + "x" if arq.exists() else "x")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-m", "m")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "celulas.yml").write_text(CELULAS_YML, encoding="utf-8")
    _commit(tmp_path, "services/alunos/a.py", "services/quiz/q.py", "README.md")
    return tmp_path


def _base(raiz: Path) -> str:
    return _git(raiz, "rev-parse", "HEAD")


def test_mudanca_em_um_servico(repo: Path) -> None:
    base = _base(repo)
    _commit(repo, "services/quiz/q.py")
    assert detectar_celulas.celulas_tocadas(repo, base) == ["quiz"]


def test_mudanca_em_dois_servicos(repo: Path) -> None:
    base = _base(repo)
    _commit(repo, "services/quiz/q.py", "services/alunos/a.py")
    assert detectar_celulas.celulas_tocadas(repo, base) == ["alunos", "quiz"]


def test_dependencia_fora_de_services_toca_as_celulas_que_a_compartilham(
    repo: Path,
) -> None:
    base = _base(repo)
    _commit(repo, "packages/site_errors/e.py")
    assert detectar_celulas.celulas_tocadas(repo, base) == ["alunos", "quiz"]


def test_nenhuma_celula_tocada(repo: Path) -> None:
    base = _base(repo)
    _commit(repo, "README.md")
    assert detectar_celulas.celulas_tocadas(repo, base) == []


def test_cli_imprime_uma_por_linha_e_sai_zero(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _base(repo)
    _commit(repo, "services/quiz/q.py", "services/alunos/a.py")
    monkeypatch.setattr(detectar_celulas, "raiz_do_repo", lambda: repo)
    assert detectar_celulas.main(["--base", base]) == 0
    assert capsys.readouterr().out == "alunos\nquiz\n"


def test_cli_sem_base_recusa_com_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert detectar_celulas.main([]) == 2
    assert "exige --base <ref>" in capsys.readouterr().err


def test_cli_base_invalida_e_erro_nao_lista_vazia(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(detectar_celulas, "raiz_do_repo", lambda: repo)
    assert detectar_celulas.main(["--base", "ref-que-nao-existe"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "NÃO concluiu" in captured.err


def test_nao_importa_fiscalizacao() -> None:
    codigo = (
        "import sys; sys.path.insert(0, %r); import detectar_celulas; "
        "proibidos = {'contract_freeze','guarda_dos_guardas','resumo_de_teste','ci'}; "
        "print(sorted(proibidos & set(sys.modules)))"
    ) % str(Path(detectar_celulas.__file__).parent)
    saida = subprocess.run(
        [sys.executable, "-c", codigo], check=True, capture_output=True, text=True
    ).stdout.strip()
    assert saida == "[]"
