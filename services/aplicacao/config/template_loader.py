"""Resolve template names only inside the active former cell."""

from django.apps import apps
from django.conf import settings
from django.template.loaders.filesystem import Loader as FilesystemLoader

from .runtime import current_service


class ServiceLoader(FilesystemLoader):
    def get_dirs(self):
        service = current_service()
        if not service:
            return ()
        root = settings.MODULES_ROOT / service
        directories = [root / "templates"]
        prefix = service + "_"
        directories.extend(
            app.path + "/templates"
            for app in apps.get_app_configs()
            if app.label.startswith(prefix)
        )
        return tuple(directories)
