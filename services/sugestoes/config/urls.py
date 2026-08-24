from django.urls import path

from apps.core.views import healthz

# O urlconf da célula NÃO conhece o prefixo público (/forms/sugestoes): quem o
# aplica é FORCE_SCRIPT_NAME, lido do env em config/settings.py. Mover a Caixa
# de URL é editar Traefik + env, nunca cirurgia aqui.
urlpatterns = [
    path("healthz", healthz),
]
