import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str) -> str:  # [RECEITA:CONV v1]
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; a resolução de site (Host) é responsabilidade do middleware
# CONV-SITE, ainda não instanciado neste esqueleto (sem regra de negócio).
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "apps.core",
    # i18n da célula (PLANO-I18N fase 1): o AppConfig.ready() valida o
    # catálogo no BOOT (fail-closed) e o congela em memória.
    "apps.i18n",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # [RECEITA:CONV-SITE v1] logo após os middlewares de segurança do Django.
    "apps.core.middleware.SiteResolutionMiddleware",
    # Espelho do APPEND_SLASH: `/cadastro/` deixa de ser 404 e leva a
    # `/cadastro`. DEPOIS do CONV-SITE, e a ordem é a regra, não estilo: ele
    # precisa que o `path_info` já esteja sem o prefixo de idioma para resolver
    # a rota, e do `request.path` completo para devolver o destino COM idioma.
    # A matriz do PLANO-I18N D1 fica intacta porque ele não age quando a forma
    # com barra já resolve — que é o caso de todo prefixo de idioma.
    "apps.core.barra_no_final.BarraNoFinal",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

# funil é a única célula sem banco de dados (stateless) — CONTEXTO da célula.
# Vitrine pura: formulários postam em leads, compra redireciona para checkout.
DATABASES = {}

TEMPLATES = [  # [RECEITA:R6 v1] — landing (ilha Alpine)
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        # `request` no contexto: o base_mobile.html lê request.i18n_seo para a
        # emissão SEO de site registrado (D5). Site não registrado não referencia
        # a variável — saída byte-idêntica à anterior (teste de regressão).
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                # O RODAPÉ em TODA página (`apps/core/rodape.py`), pedido do
                # mantenedor em 31/08/2026. É processador de contexto, e não
                # `{% include %}` escrito em cada template, porque "em todas as
                # páginas" não pode depender de alguém lembrar de incluir a
                # peça: página nova nasce com rodapé sozinha.
                "apps.core.rodape.rodape_do_contexto",
                # O cartaz do aviso no celular (Fase 7), pela MESMA razão do
                # rodapé: ele precisa existir em toda página em que alguém
                # entrou, e "toda página" não pode depender de memória. Ele
                # devolve vazio na maioria das visitas — a decisão inteira
                # está em apps/core/avisos_no_celular.py.
                "apps.core.avisos_no_celular.avisos_do_contexto",
            ]
        },
    },
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Como esta célula GUARDA (aware, em UTC) e que hora ela MOSTRA. As duas
# perguntas são diferentes e as duas estavam sem resposta escrita aqui: valia o
# default de fábrica do Django para o fuso de exibição, `America/Chicago` —
# cinco horas atrás, capaz de trocar até o DIA perto da virada, sem erro nenhum
# (CI verde, deploy verde, /healthz 200, data errada na tela). `USE_TZ` vem
# escrito junto de propósito: no Django 5 ele já é `True` por default, e um
# guarda que depende de default calado é meio guarda.
# Guarda: tests/test_fuso_horario.py (armadilhas/099).
USE_TZ = True
TIME_ZONE = "America/Sao_Paulo"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
