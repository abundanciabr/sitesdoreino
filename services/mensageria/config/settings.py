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

# Atrás do Traefik; mensageria não expõe rota pública (constituicoes/AGENTS.mensageria.md)
# — sem middleware CONV-SITE aqui, sem regra de negócio neste esqueleto.
ALLOWED_HOSTS = ["*"]

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # A instalação documentada do Django para os campos de `contrib.postgres` —
    # aqui, o `ArrayField` de `apps.jornadas.Passo.canais`. Não cria tabela, não
    # tem migração própria, e não vira dependência nova: esta célula já é
    # Postgres em produção, em dev e no CI.
    "django.contrib.postgres",
    "huey.contrib.djhuey",  # entrypoint oficial do worker: manage.py run_huey (§4.11)
    "apps.core",
    "apps.eventos",
    # O motor das sequências (`PLANO-SEQUENCIAS-DE-MENSAGENS.md` §4.1: o
    # mantenedor escolheu em 30/08/2026 que ele mora DENTRO desta célula, e não
    # numa célula nova). App separado, banco compartilhado: ele lê e escreve as
    # próprias tabelas e toca `apps.eventos` num ponto só — criando a linha de
    # `EnvioRegistrado`. Ler ou escrever qualquer outra tabela de lá é o
    # critério de morte §10.7 do plano.
    "apps.jornadas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que a mensageria MOSTRA hora — o armazenamento continua em UTC
# (USE_TZ). Sem esta linha vale o default de fábrica do Django,
# `America/Chicago`: cinco horas atrás, capaz de trocar até o DIA perto da
# virada, sem nada acusando a troca. Aqui o estrago não é só tela: o corpo de
# um e-mail renderizado por template converte `datetime` aware em silêncio.
# Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Guarda: tests/test_fuso_horario.py (armadilhas/099).
TIME_ZONE = "America/Sao_Paulo"

# djhuey lê `settings.HUEY`. Precisa ser a MESMA instância que as tasks decoram
# (config/huey.py) — uma instância nova aqui criaria uma SEGUNDA fila: o handler
# enfileira numa, o `run_huey` escuta a outra, e nenhum e-mail sai (ARMADILHAS
# §4.11). O import é seguro: config/huey.py não é fail-hard (default inofensivo).
from config.huey import huey as HUEY  # noqa: E402
