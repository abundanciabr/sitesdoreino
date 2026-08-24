# apps/i18n/apps.py — entrada (b) do validador: BOOT fail-closed (D4).
# Catálogo/registro inválido ⇒ ImproperlyConfigured ⇒ o processo NÃO sobe.
# O CI protege o merge; ISTO protege a produção (merge sujo, drift).
from django.apps import AppConfig


class I18NConfig(AppConfig):
    name = "apps.i18n"
    label = "i18n"

    def ready(self):
        from django.conf import settings

        from apps.i18n.validador import validar_e_instalar

        validar_e_instalar(settings.BASE_DIR)
