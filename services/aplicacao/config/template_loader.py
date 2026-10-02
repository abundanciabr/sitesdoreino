"""Resolve template names only inside the active former cell."""

from django.apps import apps
from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader

from .runtime import current_service

# Apps de todas as células (as páginas de erro do site). Vêm depois das
# pastas da célula, que podem sobrescrever; sem elas um 404 virava 500.
COMPARTILHADOS = ("site_errors",)


class ServiceLoader(FilesystemLoader):
    def get_dirs(self):
        service = current_service()
        directories = []
        if service:
            root = settings.MODULES_ROOT / service
            directories.append(root / "templates")
            prefix = service + "_"
            directories.extend(
                app.path + "/templates"
                for app in apps.get_app_configs()
                if app.label.startswith(prefix)
            )
        directories.extend(
            app.path + "/templates"
            for app in apps.get_app_configs()
            if app.label in COMPARTILHADOS
        )
        return tuple(directories)
