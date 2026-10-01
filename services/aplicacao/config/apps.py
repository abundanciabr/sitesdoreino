"""Bootstrap checks for the single registry and its separate databases."""

from django.apps import AppConfig


class ApplicationConfig(AppConfig):
    name = "config"

    def ready(self):
        from .checks import install_database_aware_model_checks

        install_database_aware_model_checks()
