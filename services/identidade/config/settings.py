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
# .github/workflows/ci-celula.yml já fornece a TODA célula (armadilha §5.3).
# Toda variável futura desta célula (GOOGLE_CLIENT_ID, IDENTIDADE_STAFF_EMAILS…)
# é lida NO PONTO DE USO, com falha fechada e nomeada — convenção da casa.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# Esta célula serve caminhos de RAIZ (/entrar/google, /entrar/google/retorno):
# o endereço de retorno cadastrado no console do Google em 24/08/2026 é
# `https://meshcraft.top/entrar/google/retorno`, SEM prefixo — foi cadastrado
# naquele dia exatamente para o dia desta célula (DECISAO-onde-mora-a-sessao
# §5.2). Por isso NÃO há FORCE_SCRIPT_NAME aqui, ao contrário da Caixa.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem esta
# linha, `request.build_absolute_uri()` juraria `http://` e o `redirect_uri`
# mandado ao Google não bateria com o cadastrado no console —
# `redirect_uri_mismatch` em produção, e SÓ em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `conn_max_age=60`: a conexão de banco é REAPROVEITADA por até 60s em vez
# de aberta e fechada a cada requisição (o default 0 do Django). Medido pela
# auditoria de 25/08/2026 contra o Postgres real: conexão nova + SELECT custa
# ~24ms; o MESMO SELECT numa conexão reaproveitada custa ~0,2ms — o handshake
# TCP + a autenticação SCRAM-SHA-256 dominam, e nenhum dos dois fica barato
# só porque a rede é rápida. Esta célula responde "quem é você" no caminho de
# toda página logada do site, então é onde esse custo mais aparece.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"), conn_max_age=60)}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.identidade",  # a linha da pessoa: e-mail, nome, id opaco
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

# ---------------------------------------------------------------------------
# A sessão do SITE (DECISAO-celula-de-identidade — antes era da Caixa)
# ---------------------------------------------------------------------------
# Cookie assinado, e não tabela: o único conteúdo é um `Identidade.id` opaco que
# já é reconferido no banco a cada leitura (`apps/core/sessao.py`). A tabela
# `django_session` custaria uma escrita por login e um SELECT por requisição em
# troca de nada — e por isso `django.contrib.sessions` NÃO entra em
# INSTALLED_APPS: este backend não tem model. Trocar por sessão em banco no dia
# em que for preciso revogar sessão de longe é mudar esta linha.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# O MESMO nome que a Caixa usava (`meshcraft_sessao`, Path=/): a partir da
# DECISAO-celula-de-identidade quem emite e lê este cookie é SÓ esta célula.
# A Caixa deixa de escrevê-lo no mesmo corte (há guarda lá para isso). Cookies
# assinados pela chave antiga falham a assinatura aqui e viram visitante —
# efeito aceito e anunciado: todo mundo é deslogado UMA vez na virada, e
# reentra com um clique.
SESSION_COOKIE_NAME = "meshcraft_sessao"

# ALCANCE DE SITE: o cookie acompanha a pessoa por todo o domínio, e qualquer
# célula pode PERGUNTAR quem é (config/api.py) — nunca ler o cookie.
# Não é `SESSION_COOKIE_DOMAIN`: alcance de CAMINHO (um host, todas as páginas)
# é o que o site precisa; alcance de DOMÍNIO espalharia o cookie por
# subdomínios que não são desta plataforma (Lei 9: cada host tem a sua sessão).
SESSION_COOKIE_PATH = "/"

# `Lax` é OBRIGATÓRIO aqui, não preferência: a volta do Google é uma navegação
# de topo vinda de accounts.google.com. Com `Strict` o navegador NÃO manda o
# cookie nessa volta, o `state` guardado some, e todo login legítimo falha como
# se fosse falsificação.
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# O cookie de CSRF leva nome próprio pelo mesmo motivo de sempre: `csrftoken`
# genérico no domínio compartilhado é colisão entre células. E fica sob o
# prefixo desta célula — os únicos formulários dela morariam ali.
CSRF_COOKIE_NAME = "identidade_csrf"
CSRF_COOKIE_PATH = "/entrar"
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# Tokens do PAR consumidor→provedor (R1), um por par: TOKENS_ACEITOS_FUNIL etc.
# ---------------------------------------------------------------------------
# Env ausente ⇒ conjunto VAZIO ⇒ toda chamada é recusada com 401. Fail-closed
# por construção, e sem derrubar o boot: a célula sobe, o login segue
# funcionando, e só a API interna fica fechada até o token existir no env.
TOKENS_ACEITOS = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_ACEITOS_") and valor
}

# O degrau A MAIS da resposta completa (`/sessao/completa`, que devolve e-mail):
# além de estar em TOKENS_ACEITOS_<PAR>, o par precisa estar TAMBÉM em
# TOKENS_COMPLETOS_<PAR>. É o que impede o e-mail — o dado pessoal que a
# EVO-01 §3 concentrou numa linha só — de vazar para uma célula que só precisa
# de um nome para escrever no canto da página (o `funil` tem o primeiro
# conjunto e NÃO tem o segundo). Conjunto vazio ⇒ ninguém recebe e-mail.
TOKENS_COMPLETOS = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_COMPLETOS_") and valor
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que datas seriam MOSTRADAS — o armazenamento continua em UTC
# (USE_TZ). Nasce certo, ao contrário das oito células antigas (dívida
# registrada em ARMADILHAS-OPERACAO.md §9): sem esta linha vale o default de
# fábrica do Django, `America/Chicago`.
TIME_ZONE = "America/Sao_Paulo"
