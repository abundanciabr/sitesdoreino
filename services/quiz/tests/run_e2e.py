"""Executa o E2E no navegador dentro do banco de teste isolado do Django."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
CHAVES = (
    "DJANGO_SECRET_KEY",
    "DATABASE_URL",
    "REDIS_STREAMS_URL",
    "HUEY_REDIS_URL",
)


def ler_env(caminho: Path) -> dict[str, str]:
    valores = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave.strip()] = valor.strip().strip("\"'")
    return valores


def carregar_env_da_sessao() -> None:
    worktree = str(REPO_ROOT.resolve())
    if (
        all(os.environ.get(chave) for chave in CHAVES)
        and os.environ.get("SESSAO_WORKTREE")
        and str(Path(os.environ.get("SESSAO_WORKTREE", "")).resolve()) == worktree
    ):
        return
    sessao_root = Path(tempfile.gettempdir()) / "sitesdoreino-sessoes"
    encontrados = []
    if sessao_root.exists():
        for caminho in sessao_root.glob("quiz-*/.env"):
            try:
                valores = ler_env(caminho)
            except OSError:
                continue
            if str(Path(valores.get("SESSAO_WORKTREE", "")).resolve()) == worktree:
                encontrados.append((caminho, valores))
    if len(encontrados) == 1:
        os.environ.update(encontrados[0][1])
    elif len(encontrados) > 1:
        raise SystemExit(
            "Há mais de um ambiente de sessão para esta bancada; defina as variáveis da sessão e SESSAO_WORKTREE antes de rodar o E2E."
        )
    faltantes = [chave for chave in CHAVES if not os.environ.get(chave)]
    if faltantes:
        lista = ", ".join(faltantes)
        raise SystemExit(
            f"Ambiente local incompleto ({lista}). Abra a bancada pelo rito do projeto ou forneça essas variáveis."
        )


def main() -> int:
    carregar_env_da_sessao()
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DEBUG"] = "1"
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    comando = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        str(ROOT / "tests" / "e2e_browser.py"),
    ]
    try:
        return subprocess.run(
            comando, cwd=ROOT, env=os.environ.copy(), timeout=600
        ).returncode
    except subprocess.TimeoutExpired:
        print("O E2E excedeu o limite de 10 minutos e foi encerrado.", file=sys.stderr)
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
