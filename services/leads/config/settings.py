# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import json
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

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {
    v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v
}


def _comerciais_do_crm() -> dict:
    """Quem é a PESSOA por trás de cada token, no acompanhamento comercial.

    O Bearer das outras portas desta casa responde só "qual par chama". O CRM
    humano precisa de mais: o contrato congelado autoriza por `titular`, e
    nenhuma operação dele carrega o ator no corpo nem em cabeçalho. Então a
    conta comercial vem do único lugar que o contrato já tem: a credencial.
    Um token por conta, declarado fora do código:

        COMERCIAIS_DO_CRM='{"<token>": {"titular_id": "com-ana", "site_id": "meshcraft"}}'

    Ausente é conjunto VAZIO, e conjunto vazio recusa toda operação de
    oportunidade com 403 — fail-closed. Malformado é erro de partida, nunca
    conjunto vazio silencioso: "ninguém autorizado" e "eu não consegui ler quem
    está autorizado" são coisas diferentes, e só a primeira é uma decisão.
    """
    bruto = os.environ.get("COMERCIAIS_DO_CRM", "").strip()
    if not bruto:
        return {}
    try:
        declarado = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ImproperlyConfigured(
            f"COMERCIAIS_DO_CRM não é JSON válido ({erro}). Esperado um objeto "
            'como {"<token>": {"titular_id": "...", "site_id": "..."}}.'
        ) from erro
    if not isinstance(declarado, dict):
        raise ImproperlyConfigured(
            "COMERCIAIS_DO_CRM precisa ser um objeto de token para conta, não "
            f"{type(declarado).__name__}."
        )
    contas = {}
    for token, conta in declarado.items():
        if (
            not isinstance(conta, dict)
            or not conta.get("titular_id")
            or not conta.get("site_id")
        ):
            raise ImproperlyConfigured(
                f"COMERCIAIS_DO_CRM: a conta do token {token[:4]}... precisa de "
                "titular_id e site_id preenchidos."
            )
        contas[token] = {
            "titular_id": str(conta["titular_id"]),
            "site_id": str(conta["site_id"]),
        }
    return contas


COMERCIAIS_DO_CRM = _comerciais_do_crm()

# O token da conta comercial também abre a porta: declarar a conta e esquecer
# de repetir o mesmo token em TOKENS_ACEITOS_* custaria um 401 sem explicação
# (a lição que a `encomendas` pagou em armadilhas/318).
TOKENS_ACEITOS |= set(COMERCIAIS_DO_CRM)

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
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

# O fuso em que datas seriam MOSTRADAS — o armazenamento continua em UTC
# (USE_TZ). Sem esta linha vale o default de fábrica do Django,
# `America/Chicago`: cinco horas atrás, e sem nada na tela indicando a troca.
# É falha silenciosa até a primeira página renderizar uma data — foi assim que
# a `sugestoes` foi pega em 24/08/2026 (EVO-21; dívida em
# ARMADILHAS-OPERACAO.md §9). Guarda: tests/test_fuso_horario.py.
TIME_ZONE = "America/Sao_Paulo"
