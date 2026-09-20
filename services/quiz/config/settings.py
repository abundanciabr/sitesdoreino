# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from config.huey import huey as _huey

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik. Quem decide se um Host é legítimo é o middleware CONV-SITE
# (cadastro LOCAL — [INV-P11], ver LICOES.md), não esta lista.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn a requisição chega em http. Sem esta
# linha o CSRF recusa TODO envio honesto do formulário — o navegador manda
# `Origin: https://<site>`, o Django monta `http://<site>` para comparar, e as
# duas diferem por uma letra. As outras nove células com CSRF desta casa já a
# têm; ela não custa variável de ambiente nova (o Traefik sempre emite
# `X-Forwarded-Proto`). Guarda: tests/test_superficie_publica.py.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# O formulário do Crivo coleta e-mail e telefone, e emite `{% csrf_token %}`
# desde o primeiro dia — mas sem `CsrfViewMiddleware` (abaixo) o token era
# decoração e qualquer página da internet podia gravar leads aqui.
#
# `CSRF_TRUSTED_ORIGINS` NÃO entra: ele existe para aceitar origens DIFERENTES
# do host da requisição, e aqui formulário e POST são sempre do mesmo host
# (Lei 9: um deploy, N domínios, cada um falando consigo mesmo).
#
# Nome próprio, e não o `csrftoken` de fábrica: no mesmo domínio moram várias
# células sob prefixos, e o navegador guarda cookie por (nome, domínio,
# caminho). Duas células publicando `csrftoken` deixam qual delas o servidor lê
# na mão da precedência por caminho — mesma decisão da `sugestoes`.
CSRF_COOKIE_NAME = "quiz_csrf"

# Alcance = o prefixo desta célula. O token protege os formulários que moram
# aqui; mandá-lo para "/" seria um cookie viajando em toda página do site para
# proteger formulário que não está lá.
CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"
CSRF_COOKIE_SECURE = not DEBUG

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # [RECEITA:R8 v1] traz `manage.py run_huey` (o worker de produção sobe com
    # esse comando) e o autodiscover de apps/*/tasks.py — sem isso o worker
    # subiria com o TaskRegistry VAZIO (ARMADILHAS §4.11).
    "huey.contrib.djhuey",
    "apps.core",
    "apps.quiz",
]

# [RECEITA:R8 v1] djhuey lê settings.HUEY; sendo a INSTÂNCIA de config/huey.py
# (não um dict), worker e web compartilham exatamente o mesmo registro de
# tasks — `run_huey` executa o que apps/quiz/tasks.py registra.
HUEY = _huey

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Depois do CommonMiddleware e ANTES de tudo que é desta célula: o POST do
    # formulário tem de ser recusado antes de a view gravar lead e enfileirar
    # evento. Esta célula não tem sessão, e o CSRF do Django não precisa de uma
    # — o token vai no cookie `quiz_csrf`.
    "django.middleware.csrf.CsrfViewMiddleware",
    # [RECEITA:CONV-SITE v1] logo após os middlewares de segurança do Django.
    "apps.core.middleware.SiteResolutionMiddleware",
    # Espelho do APPEND_SLASH: `/quiz/<slug>/resultado/` deixa de ser 404 e leva
    # a `/quiz/<slug>/resultado`. Vai por ÚLTIMO — ele só age sobre resposta que
    # JÁ saiu 404. Nesta célula o urlconf MISTURA as convenções (o formulário é
    # canônico COM barra, o resultado SEM), e é a regra 1 do middleware ("não age
    # se a forma com barra resolve") que impede um laço com o APPEND_SLASH do
    # Django. Regra e guardas na docstring do módulo.
    "apps.core.barra_no_final.BarraNoFinal",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que o quiz MOSTRA hora — o armazenamento continua em UTC (USE_TZ).
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`: a tela
# de resultado mostraria a um usuário brasileiro um horário cinco horas atrás,
# capaz de trocar até o DIA, sem nada indicando a troca. Foi assim que a célula
# `sugestoes` foi pega em 24/08/2026 (EVO-21). Guarda: tests/test_fuso_horario.py.
TIME_ZONE = "America/Sao_Paulo"
