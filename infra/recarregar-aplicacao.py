#!/usr/bin/env python3
"""Recarrega o ambiente da aplicação ativa e prova as entradas do site."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def main() -> int:
    caminho = Path(__file__).with_name("ativar-aplicacao.py")
    spec = importlib.util.spec_from_file_location("ativar_aplicacao", caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError("ativador da aplicação ausente")
    ativador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ativador)

    if not ativador.JOURNAL.is_file():
        raise RuntimeError("a aplicação única ainda não foi ativada")
    estado = json.loads(ativador.JOURNAL.read_text(encoding="utf-8"))
    versao = estado["atual_versao"]
    ambiente = ativador.ambiente_da_aplicacao(
        versao["imagem"], Path(versao["codigo"])
    )
    ativador.compose(
        "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180",
        "aplicacao", arquivo=ativador.RAIZ / "docker-compose.yml",
        override=ativador.PUBLICACOES / "imagens.json", ambiente=ambiente,
    )
    ativador.provar_site()
    print("APLICACAO-RECARREGADA-E-PROVADA")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, RuntimeError) as erro:
        print(f"ERRO: aplicação não recarregada/provada: {erro}", file=sys.stderr)
        sys.exit(1)
