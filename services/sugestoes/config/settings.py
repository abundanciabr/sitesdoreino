# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor


# Só estas duas são fail-hard no import, e de propósito: são as únicas que o
# .github/workflows/ci-celula.yml já fornece a TODA célula (armadilha §5.3 —
# variável nova e fail-hard aqui exigiria editar o workflow, que está fora do
# escopo desta célula). Toda variável futura desta célula
# (SUGESTOES_STAFF_EMAILS, ALUNOS_API_URL…) é lida NO PONTO DE USO, com default
# inofensivo — convenção do lote de Huey.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A Caixa serve sob prefixo: meshcraft.top/forms/sugestoes/ (DECISAO-EVO-01 §2).
# O Traefik NÃO remove o prefixo — quem o conhece é esta variável, nunca o
# urls.py. Ver armadilhas/029 e tests/test_healthz_script_name.py.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; a resolução de site (Host) é responsabilidade do middleware
# CONV-SITE, ainda não instanciado neste esqueleto (sem regra de negócio).
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem esta
# linha, `request.build_absolute_uri()` juraria `http://` e o `redirect_uri`
# mandado ao Google não bateria com o cadastrado no console — `redirect_uri_mismatch`
# em produção, e SÓ em produção (em dev não há proxy, e o endereço é http mesmo).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # [RECEITA:R8 v1] dá o entrypoint `python manage.py run_huey` (django.setup
    # + autodiscover de tasks.py — sem isso o worker sobe com registro vazio e
    # não executa nada, `armadilhas/030` §4.11). É o comando do serviço
    # `sugestoes-relay` no compose.
    "huey.contrib.djhuey",
    "apps.core",
    "apps.sugestoes",  # modelo de dados + outbox da Caixa (EVO-11, EVO-20)
]

# O run_huey do djhuey consome a MESMA instância onde as tasks se registram
# (config/huey.py — leitura de HUEY_REDIS_URL nunca fail-hard no import).
from config.huey import huey as HUEY  # noqa: E402

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

# ---------------------------------------------------------------------------
# Sessão da Caixa (DECISAO-EVO-01 §7: "a sugestoes cuida da própria sessão")
# ---------------------------------------------------------------------------
# Cookie assinado, e não tabela: o único conteúdo é um `Identidade.id` opaco que
# já é reconferido no banco a cada requisição (`apps/core/sessao.py`). A tabela
# `django_session` custaria uma escrita por login e um SELECT por requisição em
# troca de nada — e por isso `django.contrib.sessions` NÃO entra em
# INSTALLED_APPS: este backend não tem model. Trocar por sessão em banco no dia
# em que a Caixa precisar revogar sessão de longe é mudar esta linha.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# Nome próprio, não o `sessionid` de fábrica: `meshcraft.top` serve o `funil` na
# raiz e a Caixa sob /forms/sugestoes. Duas células no MESMO domínio com o mesmo
# nome de cookie é uma sobrescrevendo a sessão da outra.
SESSION_COOKIE_NAME = "sugestoes_sessao"

# E o cookie nem sequer sai para o resto do domínio: o navegador só o envia sob
# o prefixo da Caixa. Sem SCRIPT_NAME (dev) vira "/", que é o certo lá.
SESSION_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"

# `Lax` é OBRIGATÓRIO aqui, não preferência: a volta do Google é uma navegação
# de topo vinda de accounts.google.com. Com `Strict` o navegador NÃO manda o
# cookie nessa volta, o `state` guardado some, e todo login legítimo falha como
# se fosse falsificação.
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# O cookie de CSRF (o `<form>` do /sair) leva o mesmo tratamento e pelo mesmo
# motivo: `csrftoken` genérico no domínio compartilhado é colisão entre células.
CSRF_COOKIE_NAME = "sugestoes_csrf"
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
CSRF_COOKIE_SECURE = not DEBUG

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
