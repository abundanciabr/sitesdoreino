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
# `.github/workflows/ci-celula.yml` fornece a TODA célula (`armadilhas/037` —
# variável nova e fail-hard aqui exigiria editar o workflow). Toda variável
# futura desta célula (`ADMIN_EMAILS`, `IDENTIDADE_API_URL`, o token do par…) é
# lida NO PONTO DE USO, com default inofensivo — e a razão está medida em
# `armadilhas/097`: cliente que lê env no `__init__` transforma env ausente em
# HTTP 500 em TODA página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A área administrativa serve sob prefixo: meshcraft.top/admin/
# (`DECISAO-celula-admin.md` §2). O Traefik NÃO remove o prefixo — quem o
# conhece é esta variável, nunca o `urls.py`. Ver `armadilhas/029` e
# `tests/test_healthz_script_name.py`.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik. A rota desta célula é presa a `Host(meshcraft.top)` no
# gateway (§2 da lei) — a defesa de host mora lá, não aqui.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem
# esta linha o Django trata toda requisição como insegura, e a conferência
# estrita de Referer do CSRF — a que protege os formulários da fase 4 — não
# roda. Custa uma linha agora; descobrir depois custa um formulário quebrado só
# em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A PORTA. Vem por ULTIMO de proposito: quando ela roda, o CommonMiddleware
    # ja normalizou o caminho (APPEND_SLASH) e o CSRF ja rejeitou o que tinha de
    # rejeitar. E ela e o UNICO ponto de autorizacao da celula — nenhuma view
    # confere cracha por conta propria (apps/core/views.py explica por que).
    "apps.core.porta.PortaAdministrativa",
]

# ---------------------------------------------------------------------------
# As duas variaveis que a PORTA le (apps/core/porta.py)
# ---------------------------------------------------------------------------
# Lidas com `.get()` e default inofensivo, NUNCA fail-hard no import
# (`armadilhas/097`): env ausente fecha a area, mas nao derruba o container —
# o `/healthz` continua respondendo e o deploy nao entra em crashloop.
#
# ADMIN_EMAILS e a UNICA fonte de "pode entrar" (DECISAO-celula-admin par.2).
# Vazia ⇒ ninguem entra. Fail-closed por construcao.
ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "")

# Para onde mandar quem nao tem sessao. E o mesmo endereco publico que o
# `funil` usa — a tela de login mora la, nos tres idiomas, e esta celula nunca
# serve caminho com forma de idioma.
URL_DE_ENTRADA = os.environ.get("URL_DE_ENTRADA", "/entrar/google")

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei, não esquecimento: quem assina
# o cookie `meshcraft_sessao` é a célula `identidade`, e só ela
# (`DECISAO-celula-de-identidade.md` §6.4). A área admin **repassa** o cookie
# recebido para a `identidade` e pergunta quem é — nunca o lê, nunca o escreve.
#
# Um `request.session` funcionando aqui seria a porta para a área admin assinar
# a própria sessão em paralelo, e duas células assinando o MESMO cookie com
# chaves diferentes é o cabo-de-guerra que a `DECISAO-celula-de-identidade` §5
# descreve: entrar num lugar desloga do outro, sem erro em lugar nenhum.
# Guarda: `tests/test_inv_admin_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — a Caixa e a identidade já fazem o mesmo.
CSRF_COOKIE_NAME = "admin_csrf"
# O token de CSRF protege os `<form>` DESTA célula, que vivem todos sob o
# prefixo dela. Diferente da SESSÃO (que é do site inteiro e mora na
# `identidade`), ele não tem por que viajar para "/".
CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"
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
STATICFILES_DIRS = [BASE_DIR / "static"]

USE_TZ = True

# O fuso em que a área admin MOSTRA hora — o armazenamento continua em UTC.
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`: cinco
# horas atrás, sem nada indicando a troca (`armadilhas/099`). Numa célula cujo
# produto inteiro é painel com data — métricas, auditoria, linha do tempo —
# isso apareceria na primeira tela e seria lido como bug de dado, não de fuso.
TIME_ZONE = "America/Sao_Paulo"
