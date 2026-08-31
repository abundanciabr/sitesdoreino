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

# POOL DE CONEXÕES (28/08/2026) — o reaproveitamento que o `conn_max_age=60`
# buscava, sem o vazamento que ele causava.
#
# O que o `conn_max_age=60` acertava, e continua valendo: medido pela auditoria
# de 25/08/2026 contra o Postgres real, conexão nova + SELECT custa ~24ms e o
# MESMO SELECT numa conexão reaproveitada custa ~0,2ms — o handshake TCP e a
# autenticação SCRAM-SHA-256 dominam. Esta célula responde "quem é você" no
# caminho de toda página logada do site, então é onde esse custo mais aparece.
#
# O que ele ERRAVA, e ninguém tinha medido: sob ASGI, o Django abre um
# `ThreadSensitiveContext` POR REQUISIÇÃO (django/core/handlers/asgi.py,
# `ASGIHandler.__call__`), e o asgiref cria um executor de UMA thread para cada
# um. A conexão de banco do Django é THREAD-LOCAL. No fim da requisição o
# `request_finished` chama `close_old_connections`, que só fecha a conexão se
# ela estiver obsoleta — com `conn_max_age=60` ela NÃO está, então a conexão
# fica aberta e a thread dona dela é descartada. Ninguém mais tem como fechá-la.
# Nas outras células o `conn_max_age` é o default 0 do `dj_database_url`, então
# a conexão fecha ao fim da requisição e o vazamento não existe: esta célula era
# a única. Foi o que estourou o limite do Postgres (100 conexões para a
# plataforma inteira) no incidente do painel em 27/08/2026, quando 86 pedidos
# quase simultâneos passaram todos por aqui.
#
# A saída que preserva as DUAS coisas é o pool nativo do Django 5.1
# (`OPTIONS["pool"]`, exige `psycopg[pool]`): as conexões são reaproveitadas
# como antes, mas vivem num pool de PROCESSO — `_connection_pools` é atributo de
# CLASSE do DatabaseWrapper, não thread-local — então thread descartada devolve
# a conexão em vez de abandoná-la. E `max_size` põe um TETO: esta célula nunca
# passa de 8 conexões, aconteça o que acontecer do lado de fora. O Django exige
# `CONN_MAX_AGE == 0` junto com o pool (levanta ImproperlyConfigured caso
# contrário) — é por isso que o argumento sumiu daqui, e não por descuido.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    # min_size=1: uma conexão quente desde o primeiro pedido — é o que devolve
    # os ~0,2ms. max_size=8: o teto. timeout=10: em vez de esperar para sempre
    # por uma vaga, a requisição falha em 10s com erro nomeado (fail-closed na
    # borda, RETROSPECTIVA-FASE-D §4) — silêncio indefinido seria pior.
    "pool": {"min_size": 1, "max_size": 8, "timeout": 10},
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.identidade",  # a linha da pessoa: e-mail, nome, id opaco
    # A fila intra-célula. Está aqui, e não só no worker, porque é esta linha
    # que dá o `python manage.py run_huey` com autodiscover de `tasks.py` —
    # subir o `huey_consumer` direto deixa o registro VAZIO, e o worker fica de
    # pé sem executar nada e sem reclamar de nada (`armadilhas/030`).
    "huey.contrib.djhuey",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # Espelho do APPEND_SLASH: `/entrar/google/` deixa de ser 404 e leva a
    # `/entrar/google`. Vai por ÚLTIMO de propósito — ele só age sobre resposta
    # que JÁ saiu 404, e daqui enxerga o 404 de qualquer um acima dele. Como o
    # CSRF recusa com 403 (não 404), os dois não se cruzam. Regra e restrições
    # na docstring do módulo.
    "apps.core.barra_no_final.BarraNoFinal",
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

# A instância única do Huey desta célula (config/huey.py). O relay da outbox é
# uma `periodic_task` dela: sem esta linha o djhuey procuraria uma configuração
# de fábrica e o worker rodaria noutra fila que ninguém alimenta.
from config.huey import huey as _huey  # noqa: E402  (depois de INSTALLED_APPS)

HUEY = _huey
