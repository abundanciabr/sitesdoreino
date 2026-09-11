"""A receita local precisa executar a mesma validação em qualquer shell."""

import os
from pathlib import Path
import shutil
import subprocess


RAIZ_DA_CELULA = Path(__file__).resolve().parents[1]


def executar_make(diretorio, *alvos, ambiente=None):
    sobreposicoes = ambiente or {}
    ambiente_final = os.environ | sobreposicoes
    shell = (
        ambiente_final.get("ComSpec")
        or ambiente_final.get("COMSPEC")
        or ambiente_final.get("SHELL")
        or "sh"
    )
    return subprocess.run(
        [
            "make",
            f"SHELL={shell}",
            *(f"{chave}={valor}" for chave, valor in sobreposicoes.items()),
            *alvos,
        ],
        cwd=diretorio,
        env=ambiente_final,
        capture_output=True,
        text=True,
        check=False,
    )


def preparar_receita_temporaria(tmp_path, comando):
    receita = (RAIZ_DA_CELULA / "Makefile").read_text(encoding="utf-8")
    (tmp_path / "Makefile").write_text(
        receita.replace(comando, f"{comando} /c exit 19", 1), encoding="utf-8"
    )


def ferramenta_que_falha(tmp_path, nome):
    unix = tmp_path / nome
    unix.write_text("#!/bin/sh\nexit 19\n", encoding="utf-8")
    unix.chmod(0o755)
    comspec = os.environ.get("ComSpec") or os.environ.get("COMSPEC")
    if comspec:
        shutil.copy(comspec, tmp_path / f"{nome}.exe")


def pacote_de_teste(tmp_path):
    pacote = tmp_path / "aplicacao"
    pacote.mkdir()
    (pacote / "__init__.py").touch()


def ambiente_com_ferramentas_em(tmp_path):
    chave_do_path = next(chave for chave in os.environ if chave.upper() == "PATH")
    return {chave_do_path: f"{tmp_path}{os.pathsep}{os.environ[chave_do_path]}"}


def test_receitas_de_validacao_executam_sem_shell_posix():
    resultado = executar_make(RAIZ_DA_CELULA, "lint", "type", "contrato-check")

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, saida
    assert "black --check ." in saida
    assert "sem mypy" in saida
    assert "RESULTADO  PASS" in saida


def test_lint_executa_importlinter_quando_a_configuracao_existe(tmp_path):
    preparar_receita_temporaria(tmp_path, "lint-imports")
    pacote_de_teste(tmp_path)
    (tmp_path / ".importlinter").write_text(
        "[importlinter]\nroot_package = aplicacao\n", encoding="utf-8"
    )
    ferramenta_que_falha(tmp_path, "lint-imports")

    resultado = executar_make(
        tmp_path,
        "lint",
        ambiente=ambiente_com_ferramentas_em(tmp_path),
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert "lint-imports" in saida


def test_type_executa_mypy_quando_a_configuracao_existe(tmp_path):
    preparar_receita_temporaria(tmp_path, "mypy .")
    pacote_de_teste(tmp_path)
    (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")
    ferramenta_que_falha(tmp_path, "mypy")

    resultado = executar_make(
        tmp_path,
        "type",
        ambiente=ambiente_com_ferramentas_em(tmp_path),
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert "mypy" in saida
