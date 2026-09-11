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
    comando_make = [
        shutil.which("make") or "make",
        f"SHELL={shell}",
        *(f"{chave}={valor}" for chave, valor in sobreposicoes.items()),
        *alvos,
    ]
    comspec = ambiente_final.get("ComSpec") or ambiente_final.get("COMSPEC")
    comando = (
        [comspec, "/d", "/s", "/c", subprocess.list2cmdline(comando_make)]
        if comspec
        else comando_make
    )
    return subprocess.run(
        comando,
        cwd=diretorio,
        env=ambiente_final,
        capture_output=True,
        text=True,
        check=False,
    )


def preparar_receita_temporaria(tmp_path):
    shutil.copy(RAIZ_DA_CELULA / "Makefile", tmp_path / "Makefile")


def ferramenta_de_teste(tmp_path, nome, codigo):
    mensagem = f"{nome} de teste encerrou com {codigo}"
    unix = tmp_path / nome
    unix.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{mensagem}' >&2\nexit {codigo}\n",
        encoding="utf-8",
    )
    unix.chmod(0o755)
    (tmp_path / f"{nome}.cmd").write_text(
        f"@echo {mensagem} 1>&2\r\n@exit /b {codigo}\r\n", encoding="utf-8"
    )
    return mensagem


def pacote_de_teste(tmp_path):
    pacote = tmp_path / "aplicacao"
    pacote.mkdir()
    (pacote / "__init__.py").touch()


def ambiente_com_ferramentas_em(tmp_path):
    chave_do_path = next(chave for chave in os.environ if chave.upper() == "PATH")
    raiz_do_sistema = Path(
        os.environ.get("SystemRoot") or os.environ.get("WINDIR") or "/"
    )
    diretorios = [tmp_path, raiz_do_sistema / "System32", raiz_do_sistema]
    return {chave_do_path: os.pathsep.join(map(str, diretorios))}


def test_receitas_de_validacao_executam_sem_shell_posix():
    resultado = executar_make(RAIZ_DA_CELULA, "lint", "type", "contrato-check")

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, saida
    assert "black --check ." in saida
    assert "sem mypy" in saida
    assert "RESULTADO  PASS" in saida


def test_lint_executa_black_no_cmd(tmp_path):
    preparar_receita_temporaria(tmp_path)
    mensagem = ferramenta_de_teste(tmp_path, "black", 19)

    resultado = executar_make(
        tmp_path,
        "lint",
        ambiente=ambiente_com_ferramentas_em(tmp_path),
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert mensagem in saida


def test_lint_executa_importlinter_quando_a_configuracao_existe(tmp_path):
    preparar_receita_temporaria(tmp_path)
    pacote_de_teste(tmp_path)
    (tmp_path / ".importlinter").write_text(
        "[importlinter]\nroot_package = aplicacao\n", encoding="utf-8"
    )
    ferramenta_de_teste(tmp_path, "black", 0)
    mensagem = ferramenta_de_teste(tmp_path, "lint-imports", 19)

    resultado = executar_make(
        tmp_path,
        "lint",
        ambiente=ambiente_com_ferramentas_em(tmp_path),
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert mensagem in saida


def test_type_executa_mypy_quando_a_configuracao_existe(tmp_path):
    preparar_receita_temporaria(tmp_path)
    pacote_de_teste(tmp_path)
    (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")
    mensagem = ferramenta_de_teste(tmp_path, "mypy", 19)

    resultado = executar_make(
        tmp_path,
        "type",
        ambiente=ambiente_com_ferramentas_em(tmp_path),
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode != 0
    assert mensagem in saida
