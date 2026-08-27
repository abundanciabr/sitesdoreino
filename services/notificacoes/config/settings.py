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


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

ALLOWED_HOSTS = ["*"]  # rede Docker interna; célula não tem rota pública direta

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_FUNIL etc.).
# Hoje o conjunto nasce VAZIO e isso é o desenho: esta célula ainda não tem
# superfície de máquina — quem for consumi-la passa pela Fase 4 do
# `docs/notificacoes/PLANO-MESTRE.md`, que é Rito de Contrato (RITOS §3).
TOKENS_ACEITOS = {
    v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v
}

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.eventos",
    "apps.notificacoes",
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

# O fuso em que a célula MOSTRA hora — o armazenamento continua em UTC (é isso
# que o USE_TZ acima garante). Sem esta linha vale o default de fábrica do
# Django, `America/Chicago`: cinco horas atrás, e dia virado perto da
# meia-noite. Esta célula nasce com a linha porque a dívida do fuso fechou em
# 26/08/2026 nas outras onze — nascer certo é mais barato que ser corrigida
# depois. Guarda de comportamento: tests/test_fuso_horario.py (armadilhas/099).
TIME_ZONE = "America/Sao_Paulo"

# Quantos dias uma notificação LIDA continua no caminho quente antes de ser
# arquivada. O arquivamento existe desde o primeiro dia por exigência da
# `DECISAO-notificacoes` §5.2: o sino aparece em TODA página, e uma tabela que
# só cresce fica lenta exatamente quando o produto der certo.
DIAS_ATE_ARQUIVAR = int(os.environ.get("NOTIFICACOES_DIAS_ATE_ARQUIVAR", "30"))
