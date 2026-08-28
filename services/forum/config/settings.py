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
# variável nova e fail-hard aqui exigiria editar o workflow, que está fora do
# escopo desta gênese). Toda variável futura desta célula (o token do par da
# `identidade`, a lista de professores, a de moderadores…) é lida NO PONTO DE
# USO, com default inofensivo — e a razão está medida em `armadilhas/097`:
# cliente que lê env no `__init__` transforma env ausente em HTTP 500 em TODA
# página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# O fórum serve sob prefixo: meshcraft.top/forum
# (`DECISAO-forum-da-escola.md` §2). O Traefik NÃO remove o prefixo — quem o
# conhece é esta variável, nunca o `urls.py`. Ver `armadilhas/029` e
# `tests/test_healthz_script_name.py`.
#
# E o prefixo é CAMINHO, não subdomínio, por uma razão que não é estética: o
# cookie de sessão do site é de host. Em `forum.meshcraft.top` ele não viaja, e
# o fórum passaria a exigir um segundo login — exatamente o que a lei §2 proíbe.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik. Esta célula responde em qualquer host servido pela
# plataforma (Lei 9 — um deploy, N domínios); a defesa de host, se um dia for
# preciso prendê-la a um só, mora no gateway, não aqui.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem
# esta linha o Django trata toda requisição como insegura, e a conferência
# estrita de Referer do CSRF — a que vai proteger os formulários de postar e
# responder — não roda. Custa uma linha agora; descobrir depois custa um
# formulário quebrado só em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # A busca do PostgreSQL (lei §4.4). Entra junto com o modelo de dados, e
    # não depois, porque `SearchVectorField` numa tabela que já cresceu é
    # migração na maior tabela do sistema.
    "django.contrib.postgres",
    "apps.core",
    # O modelo de dados do fórum: área → tópico → mensagem, mais a marca de
    # leitura. A forma é deliberadamente comum — é o que mantém aberta a porta
    # de migrar para o Discourse um dia (lei §4.2).
    "apps.forum",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A porta desta célula ainda NÃO existe — ela nasce junto com as permissões
    # por área. Quando nascer, vem por último (como a da `admin`), e a isenção
    # do `/healthz` compara `request.path_info`, NUNCA `request.path`
    # (`armadilhas/029`; o guarda já está plantado em
    # `tests/test_healthz_script_name.py`).
]

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei ([INV-P12];
# `DECISAO-celula-de-identidade.md` §6.4; `DECISAO-forum-da-escola.md` §3), não
# esquecimento: quem assina o cookie `meshcraft_sessao` é a célula `identidade`,
# e só ela. O fórum **repassa** o cookie recebido e pergunta quem é — nunca o
# lê, nunca o escreve.
#
# Duas células assinando o MESMO cookie com chaves diferentes produzem um
# cabo-de-guerra invisível: entrar no fórum deslogaria do site, e vice-versa,
# **sem erro em lugar nenhum, sem log, sem alarme** (`armadilhas/143`).
#
# A tentação concreta que isto mata: quando as permissões por área nascerem, o
# caminho mais curto para guardar "esta pessoa já foi conferida" é
# `request.session[...]`. Funciona em dev, passa em teste de unidade, e só
# quebra em produção. Guarda: `tests/test_inv_forum_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — a Caixa, a identidade e a admin já fazem o
# mesmo.
CSRF_COOKIE_NAME = "forum_csrf"
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

USE_TZ = True

# O fuso em que o fórum MOSTRA hora — o armazenamento continua em UTC. Sem esta
# linha vale o default de fábrica do Django, `America/Chicago`: cinco horas
# atrás, sem nada indicando a troca (`armadilhas/099`). Num fórum, onde cada
# mensagem carrega "há 3 minutos", isso apareceria na primeira tela e seria
# lido como bug de dado.
TIME_ZONE = "America/Sao_Paulo"
