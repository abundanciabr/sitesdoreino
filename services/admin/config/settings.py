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
    # A auditoria append-only (DECISAO-celula-admin §3). Entrou junto com a
    # PRIMEIRA escrita desta área — liberar e recusar quem está na fila —, e
    # nunca depois: um botão que muda a vida de alguém sem deixar rastro é o
    # tipo de coisa que ninguém consegue reconstruir mais tarde.
    "apps.auditoria",
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
# Tokens do PAR consumidor->provedor (R1), um por par: TOKENS_ACEITOS_<PAR>
# ---------------------------------------------------------------------------
# Env ausente => conjunto VAZIO => toda chamada a `/interno` e recusada com 401.
# Fail-closed por construcao, e sem derrubar o boot: a celula sobe, o `/healthz`
# segue respondendo, e so a porta de maquina fica fechada ate o token existir no
# env. E o mesmo desenho de `identidade`, `forum`, `cursos` e `pages`.
#
# **Aqui o conjunto vazio e o UNICO cadeado.** Esta celula roda sob
# `SCRIPT_NAME=/admin`, e o corte do prefixo e do Django, nao do Traefik: a
# porta e alcancavel pela borda publica em `meshcraft.top/admin/interno/...`
# (`armadilhas/186`). Nao ha topologia por baixo para segurar o que este
# conjunto deixar passar, e o middleware fail-closed de `apps/core/porta.py`
# isenta `/interno` de proposito (`config/api.py` explica por que).
#
# O conjunto e PLANO porque a porta so LE (`armadilhas/318`). Operacao de
# escrita aqui exigiria um segundo grau de token antes de nascer.
TOKENS_ACEITOS = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_ACEITOS_") and valor
}

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
                # As DUAS peças do site nas páginas PÚBLICAS desta célula
                # (`/docs/`), 02/09/2026. São processadores, e não inclusões
                # escritas em cada template, porque "em todas as páginas" não
                # pode depender de alguém lembrar da peça (`armadilhas/242`).
                #
                # Aqui a regra é INVERTIDA em relação às outras células: o
                # padrão é NÃO mostrar, e as duas rotas públicas são a exceção
                # declarada. Esta célula é bastidor com duas janelas para a rua,
                # e o bastidor tem molde e navegação próprios. Ver o cabeçalho
                # de `apps/core/rodape.py`.
                "apps.core.rodape.rodape_do_contexto",
                "apps.core.barra_do_site.menu_do_contexto",
                # E a MOLDURA das telas de administração (o menu do topo e o
                # rodapé de `/admin`), pela mesma razão e com o desenho
                # espelhado: aqui o padrão é MOSTRAR, e a exceção é não haver
                # crachá. Ver o cabeçalho de `apps/core/moldura.py` — em
                # especial por que ela some para quem a porta recusa.
                "apps.core.moldura.moldura_do_contexto",
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
