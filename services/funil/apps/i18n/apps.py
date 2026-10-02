# apps/i18n/apps.py — na partida, carrega e instala o catálogo de traduções.
# Problema no catálogo vira linha de log; o processo sobe do mesmo jeito.
from django.apps import AppConfig


class I18NConfig(AppConfig):
    name = "apps.i18n"
    label = "i18n"

    def ready(self):
        from django.conf import settings

        from apps.i18n.validador import validar_e_instalar

        validar_e_instalar(settings.BASE_DIR)
