"""Detecta, uma por linha em stdout, as células que o diff contra --base toca.

Autônomo: o deploy lê daqui, sem depender do executor de CI (`ci/ci.py`) nem
de qualquer fiscalização. Quem responde "este arquivo é de quem" é `celulas.yml`,
lido por `ci/mapa_de_celulas.py`.

Exit codes: 0 detectou (lista vazia é resposta legítima) · 2 não consegui medir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mapa_de_celulas  # noqa: E402
from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)


def celulas_tocadas(raiz: Path, base: str) -> list[str]:
    """Quais células o diff contra `base` toca. Falha do git é ERROR, não lista vazia."""
    execucao = executar(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=raiz,
        descricao=f"detectar células tocadas contra '{base}'",
        exigir_stdout=False,
    )
    arquivos = [ln.strip() for ln in execucao.stdout.splitlines() if ln.strip()]
    mapa = mapa_de_celulas.carregar(raiz)
    if {".github/workflows/deploy-celula.yml", "ci/detectar_celulas.py"} & set(arquivos):
        return sorted(mapa)
    return mapa_de_celulas.celulas_do_diff(arquivos, mapa)


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Imprime as células tocadas pelo diff contra --base"
    )
    parser.add_argument(
        "--base", default=None, help="ref base do diff (ex.: origin/main, HEAD^)"
    )
    args = parser.parse_args(argv)

    if not args.base:
        print(
            "ERROR: a detecção exige --base <ref> (ex.: origin/main). Rode de novo com a ref base do diff.",
            file=sys.stderr,
        )
        return 2
    try:
        raiz = raiz_do_repo()
        for nome in celulas_tocadas(raiz, args.base):
            print(nome)
    except ErroDeInstrumentacao as erro:
        print(f"ERROR {erro.resumo}\n{erro.detalhe}", file=sys.stderr)
        print(
            "\nA detecção de escopo NÃO concluiu. Tratar isto como 'nenhuma "
            "célula tocada' seria aprovar sem saber o que deveria testar.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
