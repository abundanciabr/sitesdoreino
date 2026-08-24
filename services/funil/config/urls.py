from django.urls import path, re_path

from apps.core.views import (
    cadastro,
    capturar_lead,
    entrar,
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
    # A porta de entrada do site (DECISAO-onde-mora-a-sessao). Serve em
    # /{idioma}/login pelo mesmo resolver das outras: o urlconf não conhece o
    # prefixo de idioma. O nome `entrar` é o que a peça `_sessao.html` usa em
    # `{% url_i18n 'entrar' %}` — endereço à mão em template não gera prefixo.
    #
    # `login` e não `entrar` no CAMINHO, de propósito: o primeiro segmento de
    # uma URL não pode ter FORMA de idioma (2–3 letras), senão colide com a
    # matriz do resolver e com `ci/tests/test_rotas_sem_forma_de_locale.py`.
    # `login` tem 5 letras e é lido igual nos três idiomas.
    path("login", entrar, name="entrar"),
    # [RECEITA:R6 v1] catch-all: funil serve a raiz de QUALQUER host cadastrado.
    path("", landing, name="landing"),
]
