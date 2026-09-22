"""Aviso para chamadas antigas do comando encerrado."""

import sys


if __name__ == "__main__":
    print(
        "ERROR: O comando foi encerrado. Remova a chamada a ci/radio.py do seu fluxo de trabalho.",
        file=sys.stderr,
    )
    raise SystemExit(2)
