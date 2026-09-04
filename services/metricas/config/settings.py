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
# `.github/workflows/ci-celula.yml` fornece a TODA célula (`armadilhas/037`).
# Toda variável futura desta célula (o token do par que a `admin` vai usar, o
# endereço do sininho) é lida NO PONTO DE USO, com default inofensivo — a razão
# está medida em `armadilhas/097`: cliente que lê env no `__init__` transforma
# env ausente em HTTP 500 em toda página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO TEM TELA, E ISSO É O DESENHO
# ---------------------------------------------------------------------------
# A `metricas` é o LIVRO DE FATOS da plataforma (plano do painel de gestão,
# §6.2): ela recebe eventos que as outras células publicam, guarda-os imutáveis
# e responde por API de leitura. Quem MOSTRA número é a `admin`, que já tem
# porta, crachá e a única leitora autorizada (o mantenedor).
#
# Por isso não há prefixo público de tela aqui. `FORCE_SCRIPT_NAME` continua
# lido do env porque a rota de máquina precisa responder nas duas formas de
# entrada (`/healthz` pelo healthcheck do compose e, se um dia houver borda,
# `/metricas/healthz`), e porque quem conhece o prefixo é a variável, nunca o
# `urls.py` (`armadilhas/029`; guarda em `tests/test_healthz_script_name.py`).
FORCE_SCRIPT_NAME = os.environ.get("SCRIPT_NAME") or None

# Atrás do Traefik. Esta célula responde em qualquer host servido pela
# plataforma (Lei 9 — um deploy, N domínios).
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `dj_database_url.parse` entrega `CONN_MAX_AGE = 0`, e a ausência do ajuste é
# uma DECISÃO: sob ASGI, `conn_max_age > 0` vaza uma conexão por requisição, e
# nem a suíte nem o `/healthz` nem o deploy acusam (`armadilhas/170`). Quando o
# volume pedir reaproveitamento, a resposta é o POOL nativo do Django 5.1
# (`OPTIONS["pool"]`, o desenho que a `identidade` já roda).
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    # `apps.fatos` — o evento imutável, a fila de eventos mortos e as fotos —
    # nasce no degrau 7.2 da escada. Esqueleto não inventa tabela.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A porta desta célula ainda NÃO existe: ela nasce com a API de leitura
    # (degrau 7.4) e é um Bearer de par entre células, não um crachá de pessoa.
    # Quando nascer, a isenção do `/healthz` compara `request.path_info`,
    # NUNCA `request.path` (`armadilhas/029`; o guarda já está plantado em
    # `tests/test_healthz_script_name.py`).
]

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei ([INV-P12];
# `DECISAO-celula-de-identidade.md` §6.4): quem assina o cookie
# `meshcraft_sessao` é a célula `identidade`, e só ela. Duas células assinando
# o MESMO cookie com chaves diferentes produzem um cabo-de-guerra invisível —
# sem erro, sem log, sem alarme (`armadilhas/143`).
#
# Aqui a tentação tem forma própria: esta célula vai guardar fatos SOBRE
# pessoas (quem se cadastrou, quem completou o quiz, quem escreveu no fórum), e
# o caminho curto para "de quem é este evento?" seria ler a sessão. Não é: o
# evento traz o identificador da pessoa no próprio corpo, pelo contrato, e é só
# isso que esta célula conhece. Guarda:
# `tests/test_inv_metricas_nao_assina_sessao.py`.
CSRF_COOKIE_NAME = "metricas_csrf"
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

USE_TZ = True

# ---------------------------------------------------------------------------
# O FUSO — e nesta célula ele não é cosmético, é A UNIDADE DA MEDIÇÃO
# ---------------------------------------------------------------------------
# O armazenamento continua em UTC (USE_TZ); isto é o fuso em que a célula
# DECIDE a que dia um fato pertence. Sem esta linha vale o default de fábrica
# do Django, `America/Chicago`: cinco horas atrás, capaz de trocar o DIA perto
# da virada, sem erro nenhum (`armadilhas/099`).
#
# Aqui isso corromperia a coisa medida, não a exibição. Tudo o que esta célula
# existe para responder é contagem por DIA de São Paulo: quantas pessoas
# viraram alunas neste mês (a barra que zera dia 1), a foto semanal do placar,
# as coortes D0/D7/D30, os marcos por pessoa. Uma matrícula liberada às 22h de
# São Paulo é 01h do dia seguinte em UTC: com o fuso errado, ela cai no mês
# errado e a meta do mantenedor mede outra coisa. A `admin` já conta assim
# (`placar.py::dia_em_sao_paulo`), e as duas contas precisam concordar.
# Guarda: `tests/test_fuso_horario.py`.
TIME_ZONE = "America/Sao_Paulo"
