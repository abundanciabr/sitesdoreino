from django.urls import path, re_path

from apps.core.views import (
    cadastro,
    capturar_lead,
    healthz,
    landing,
    servir_estatico,
    sitemap_xml,
)

# O urlconf NÃO conhece prefixo de idioma: o resolver (CONV-SITE, fase 1 do
# PLANO-I18N) decapa /en|pt-br|es de path_info ANTES da resolução de URL.
urlpatterns = [
    path("healthz", healthz),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),  # rota de máquina (D6)
    # Rota de máquina (D6) como o /healthz: o CONV-SITE já isentava `/static/`
    # de resolver Host, mas a isenção só entrega a requisição ao urlconf — e o
    # urlconf não tinha onde entregá-la. Daí o 404 de produção. O porquê de
    # cada detalhe está na docstring da view.
    re_path(r"^static/(?P<path>.*)$", servir_estatico, name="static"),
    path("leads", capturar_lead, name="capturar_lead"),
    path("cadastro", cadastro, name="cadastro"),  # PLANO-I18N fase 2
    # [RECEITA:R6 v1] catch-all: funil serve a raiz de QUALQUER host cadastrado.
    path("", landing, name="landing"),
]
