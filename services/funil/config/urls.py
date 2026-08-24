from django.urls import path

from apps.core.views import cadastro, capturar_lead, healthz, landing, sitemap_xml

# O urlconf NÃO conhece prefixo de idioma: o resolver (CONV-SITE, fase 1 do
# PLANO-I18N) decapa /en|pt-br|es de path_info ANTES da resolução de URL.
urlpatterns = [
    path("healthz", healthz),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),  # rota de máquina (D6)
    path("leads", capturar_lead, name="capturar_lead"),
    path("cadastro", cadastro, name="cadastro"),  # PLANO-I18N fase 2
    # [RECEITA:R6 v1] catch-all: funil serve a raiz de QUALQUER host cadastrado.
    path("", landing, name="landing"),
]
