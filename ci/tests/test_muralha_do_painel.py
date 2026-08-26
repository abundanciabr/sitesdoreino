"""A muralha do painel, testada nos três estados (INV-CI01).

Um portão que nunca foi visto reprovando é um portão que ninguém sabe se
reprova. Aqui a muralha roda de verdade, como processo, em três cenários:
contra o repositório real (PASS), contra uma cópia com o manifesto sabotado
(FAIL 1) e contra uma raiz sem painel/ (FAIL 1 — apagar o livro não passa).
A suíte adversarial fina do gerador (sintaxe quebrada, nome errado, ERROR de
pasta ausente) mora em painel/testes/teste_gerador.js e roda DENTRO da própria
muralha — reprovar lá reprova aqui.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import BASH

RAIZ = Path(__file__).resolve().parents[2]
MURALHA = RAIZ / "ci" / "muralha-do-painel.sh"

pytestmark = pytest.mark.skipif(
    BASH is None or shutil.which("node") is None,
    reason="a muralha do painel precisa de bash utilizável E node no PATH",
)


def _roda(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(MURALHA)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def _copia_painel(tmp_path: Path) -> Path:
    """Uma raiz falsa com painel/ copiado do repositório real."""
    raiz_falsa = tmp_path / "repo"
    raiz_falsa.mkdir()
    shutil.copytree(RAIZ / "painel", raiz_falsa / "painel")
    return raiz_falsa


def test_passa_no_repositorio_real() -> None:
    proc = _roda(RAIZ)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_reprova_com_manifesto_desatualizado(tmp_path: Path) -> None:
    raiz_falsa = _copia_painel(tmp_path)
    registro_novo = raiz_falsa / "painel" / "registros" / "20260826-999-sabotagem-do-teste.js"
    registro_novo.write_text(
        '(function(){ (window.REGISTROS = window.REGISTROS || []).push({'
        'arquivo: "20260826-999-sabotagem-do-teste", tipo: "nota", quando: "2026-08-26",'
        'titulo: "t", detalhe: "d", autoridade: "sessao", evidencia: null,'
        'verificado_em: null, precisa_do_dono: false, responde_a: null,'
        'gravidade: "info", frente: null, vence_em_dias: null});})();\n',
        encoding="utf-8",
    )
    proc = _roda(raiz_falsa)
    assert proc.returncode == 1, "registro novo sem regenerar o manifesto TEM de reprovar"
    assert "gerar_manifesto" in (proc.stdout + proc.stderr)


def test_reprova_com_registro_invalido(tmp_path: Path) -> None:
    raiz_falsa = _copia_painel(tmp_path)
    algum = next((raiz_falsa / "painel" / "registros").glob("*.js"))
    algum.write_text(algum.read_text(encoding="utf-8").replace('tipo: "', 'tipo: "inventado-'),
                     encoding="utf-8")
    proc = _roda(raiz_falsa)
    assert proc.returncode == 1, "registro com tipo inventado TEM de reprovar"


def test_reprova_sem_o_livro(tmp_path: Path) -> None:
    raiz_sem_painel = tmp_path / "repo-vazio"
    raiz_sem_painel.mkdir()
    proc = _roda(raiz_sem_painel)
    assert proc.returncode == 1, "apagar/mover painel/registros não pode passar verde"
    assert "não existe" in proc.stdout
