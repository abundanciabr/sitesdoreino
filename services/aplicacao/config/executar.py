"""Executa uma operação Python existente no contexto de um módulo incorporado.

Uso na VPS: ``python -m config.executar catalogo - < sincronizar_sites.py``.
O código de operação continua vindo da versão aprovada da infraestrutura.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("servico")
    parser.add_argument("script", help="arquivo Python ou '-' para stdin")
    args = parser.parse_args(argv)

    import django
    from preparar import _reescrever
    from .registry import SERVICES
    from .runtime import install_contextual_settings, load_original_settings, serving

    if args.servico not in SERVICES:
        parser.error(f"módulo desconhecido: {args.servico}")
    django.setup()
    load_original_settings()
    install_contextual_settings()
    from internal import instalar
    instalar()
    fonte = (sys.stdin.read() if args.script == "-"
             else Path(args.script).read_text(encoding="utf-8"))
    raiz = Path(__file__).resolve().parent.parent / "modules" / args.servico
    apps_root = raiz / ("pagamentos" if args.servico == "pagamentos" else "apps")
    apps = {item.name for item in apps_root.iterdir() if item.is_dir()}
    configs = {item.stem for item in (raiz / "config").glob("*.py")}
    codigo = _reescrever(fonte, args.servico, apps, configs)
    with serving(args.servico):
        exec(compile(codigo, args.script, "exec"), {"__name__": "__main__"})


if __name__ == "__main__":
    main()
