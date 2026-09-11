"""A receita local precisa executar a mesma validação em qualquer shell."""

from pathlib import Path
import subprocess


RAIZ_DA_CELULA = Path(__file__).resolve().parents[1]


def test_receitas_de_validacao_executam_sem_shell_posix():
    resultado = subprocess.run(
        ["make", "lint", "type", "contrato-check"],
        cwd=RAIZ_DA_CELULA,
        capture_output=True,
        text=True,
        check=False,
    )

    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, saida
    assert "black --check ." in saida
    assert "sem mypy" in saida
    assert "RESULTADO  PASS" in saida
