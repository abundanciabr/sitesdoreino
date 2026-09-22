# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import json
import os
from pathlib import Path
from typing import Any

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

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

# Atrás do Traefik; única rota pública é /api/pagamentos/webhooks/mp/* (sem
# resolução de site — os webhooks vivem num domínio de operações único, Lei 9).
ALLOWED_HOSTS = ["*"]

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {
    v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v
}


def _instalacoes_appmax(bruto: str) -> dict[str, dict[str, Any]]:
    """[INV-P8] Lê APPMAX_INSTALACOES do env: quais app_id da Appmax são
    nossos, com que nome de loja responder a cada um e quais site_id internos
    a instalação está autorizada a cobrar. Formato:

        {"<app_id numérico>": {"alias": "Loja", "sites": ["site-a"]}}

    Fail closed sem exceção: env ausente, JSON inválido, forma errada ou
    entrada sem alias resultam em NENHUMA instalação autorizada, e a rota de
    instalação recusa tudo. O contrário (aceitar qualquer app_id quando a
    configuração falta) deixaria um desconhecido criar vínculo na célula do
    dinheiro. Nada de client_secret entra aqui: o segredo fica só no env.
    """
    if not bruto:
        return {}
    try:
        lido = json.loads(bruto)
    except ValueError:
        return {}
    if not isinstance(lido, dict):
        return {}
    catalogo: dict[str, dict[str, Any]] = {}
    for app_id, dados in lido.items():
        if not isinstance(dados, dict):
            continue
        alias = str(dados.get("alias", "")).strip()
        if not alias:
            continue
        sites = dados.get("sites", [])
        catalogo[str(app_id)] = {
            "alias": alias,
            "sites": (
                [str(s) for s in sites if str(s).strip()]
                if isinstance(sites, list)
                else []
            ),
        }
    return catalogo


APPMAX_INSTALACOES = _instalacoes_appmax(os.environ.get("APPMAX_INSTALACOES", ""))

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

# [INV-P8] Em dev/CI/worktrees é sempre TEST-... — a credencial de produção
# (APP_USR-...) só existe em /opt/plataforma/env/pagamentos.env na VPS.
MP_ACCESS_TOKEN = env("MP_ACCESS_TOKEN")

# [INV-P10] Segredo do HMAC de x-signature — nunca tem default, fail-hard.
MP_WEBHOOK_SECRET = env("MP_WEBHOOK_SECRET")

# Appmax permanece inativa sem credenciais; Pix não depende desta integração.
APPMAX_MERCHANT_CLIENT_ID = os.environ.get("APPMAX_MERCHANT_CLIENT_ID", "")
APPMAX_MERCHANT_CLIENT_SECRET = os.environ.get("APPMAX_MERCHANT_CLIENT_SECRET", "")
APPMAX_AUTH_URL = os.environ.get(
    "APPMAX_AUTH_URL", "https://auth.sandboxappmax.com.br/oauth2/token"
)
APPMAX_API_URL = os.environ.get("APPMAX_API_URL", "https://api.sandboxappmax.com.br")

# [RECEITA:R3 v1] Redis Streams — destino do relay da outbox (pagamentos.core.
# models.relay_outbox). Já provisionado em .github/workflows/ci-celula.yml e em
# infra/env/pagamentos.env.exemplo por convenção da plataforma.
REDIS_STREAMS_URL = env("REDIS_STREAMS_URL")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "pagamentos.core",
    "pagamentos.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que a célula MOSTRA hora — o armazenamento continua em UTC (USE_TZ),
# e é o UTC que vai para o banco, para o webhook e para o Mercado Pago. Sem esta
# linha vale o default de fábrica do Django, `America/Chicago`: cinco horas
# atrás, capaz de trocar até o DIA perto da virada, sem nada acusando a troca.
# Aqui isso morde na hora de LER um caso: expiração de Pix e horário de webhook
# num relatório ou numa investigação de suporte saindo em Chicago fazem duas
# pessoas conferindo o mesmo pagamento chegarem a conclusões diferentes.
# Guarda: tests/test_fuso_horario.py (armadilhas/099).
TIME_ZONE = "America/Sao_Paulo"
