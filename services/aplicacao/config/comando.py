"""Run a former cell's management command in the unified application.

    python -m config.comando catalogo criar_curso ...
    python -m config.comando catalogo shell -c 'from apps.sites.models import Site; ...'
    python -m config.comando --env SITE_ID gamificacao reconciliar_perfis ...

``--env KEY`` uses a value passed with ``docker compose exec -e KEY=...`` even
when the service's mounted env file also defines KEY.
"""

from __future__ import annotations

import argparse
from importlib import import_module
import os
from pathlib import Path
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _local_command(service: str, name: str):
    from django.core.management import get_commands, load_command_class

    root = Path(__file__).resolve().parent.parent / "modules" / service
    apps_root = root / ("pagamentos" if service == "pagamentos" else "apps")
    for app in sorted(apps_root.iterdir()):
        source = app / "management" / "commands" / f"{name}.py"
        if source.is_file():
            package = "pagamentos" if service == "pagamentos" else "apps"
            return import_module(
                f"modules.{service}.{package}.{app.name}.management.commands.{name}"
            ).Command()
    provider = get_commands().get(name)
    if provider and provider.startswith("django."):
        return load_command_class(provider, name)
    raise ValueError(f"comando {name!r} não pertence a {service}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", action="append", default=[], metavar="KEY")
    parser.add_argument("servico")
    parser.add_argument("comando")
    parser.add_argument("argumentos", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    import django
    from preparar import _reescrever
    from .registry import SERVICES
    from .runtime import (
        install_contextual_settings, load_original_settings, serving,
    )

    if args.servico not in SERVICES:
        parser.error(f"módulo desconhecido: {args.servico}")
    from .settings import SERVICE_ENV
    for key in args.env:
        if key not in os.environ:
            parser.error(f"variável passada ao contêiner ausente: {key}")
        SERVICE_ENV[args.servico][key] = os.environ[key]
    django.setup()
    load_original_settings()
    install_contextual_settings()
    from internal import instalar
    instalar()

    with serving(args.servico):
        if args.comando == "env":
            if len(args.argumentos) != 1:
                parser.error("env requer o nome de uma variável")
            print(os.environ.get(args.argumentos[0], ""))
            return
        if args.comando == "shell" and args.argumentos[:1] == ["-c"]:
            if len(args.argumentos) != 2:
                parser.error("shell -c requer um programa Python")
            root = Path(__file__).resolve().parent.parent / "modules" / args.servico
            apps_root = root / ("pagamentos" if args.servico == "pagamentos" else "apps")
            apps = {item.name for item in apps_root.iterdir() if item.is_dir()}
            configs = {item.stem for item in (root / "config").glob("*.py")}
            codigo = _reescrever(args.argumentos[1], args.servico, apps, configs)
            exec(compile(codigo, "<shell -c>", "exec"), {"__name__": "__main__"})
            return
        command = _local_command(args.servico, args.comando)
        command.run_from_argv(["manage.py", args.comando, *args.argumentos])


if __name__ == "__main__":
    main()
