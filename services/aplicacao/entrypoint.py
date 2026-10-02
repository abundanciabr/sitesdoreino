"""One process for HTTP, background work and the existing databases."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main() -> None:
    import django
    import uvicorn
    from django.core.management import call_command

    from config.registry import SERVICES
    from config.migracoes import preparar_migracoes
    from config.runtime import install_contextual_settings, load_original_settings, serving

    django.setup()
    load_original_settings()
    install_contextual_settings()
    preparar_migracoes()
    for service in SERVICES:
        if service == "funil":
            continue
        with serving(service):
            call_command("migrate", database=service, interactive=False, verbosity=1)

    from internal import instalar
    from workers import iniciar
    import config.asgi  # constrói os handlers antes das threads

    instalar()
    workers = iniciar()
    try:
        uvicorn.run("config.asgi:application", host="0.0.0.0", port=8000,
                    lifespan="off")
    finally:
        workers.encerrar()


if __name__ == "__main__":
    main()
