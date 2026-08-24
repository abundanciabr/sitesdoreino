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
# .github/workflows/ci-celula.yml já fornece a TODA célula (armadilha §5.3 —
# variável nova e fail-hard aqui exigiria editar o workflow, que está fora do
# escopo desta célula). Toda variável futura desta célula
# (SUGESTOES_STAFF_EMAILS, ALUNOS_API_URL…) é lida NO PONTO DE USO, com default
# inofensivo — convenção do lote de Huey.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A Caixa serve sob prefixo: meshcraft.top/forms/sugestoes/ (DECISAO-EVO-01 §2).
# O Traefik NÃO remove o prefixo — quem o conhece é esta variável, nunca o
# urls.py. Ver armadilhas/029 e tests/test_healthz_script_name.py.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; a resolução de site (Host) é responsabilidade do middleware
# CONV-SITE, ainda não instanciado neste esqueleto (sem regra de negócio).
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem esta
# linha, `request.build_absolute_uri()` juraria `http://` e o `redirect_uri`
# mandado ao Google não bateria com o cadastrado no console — `redirect_uri_mismatch`
# em produção, e SÓ em produção (em dev não há proxy, e o endereço é http mesmo).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # [RECEITA:R8 v1] dá o entrypoint `python manage.py run_huey` (django.setup
    # + autodiscover de tasks.py — sem isso o worker sobe com registro vazio e
    # não executa nada, `armadilhas/030` §4.11). É o comando do serviço
    # `sugestoes-relay` no compose.
    "huey.contrib.djhuey",
    "apps.core",
    "apps.sugestoes",  # modelo de dados + outbox da Caixa (EVO-11, EVO-20)
]

# O run_huey do djhuey consome a MESMA instância onde as tasks se registram
# (config/huey.py — leitura de HUEY_REDIS_URL nunca fail-hard no import).
from config.huey import huey as HUEY  # noqa: E402

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

# ---------------------------------------------------------------------------
# Sessão da Caixa (DECISAO-EVO-01 §7: "a sugestoes cuida da própria sessão")
# ---------------------------------------------------------------------------
# Cookie assinado, e não tabela: o único conteúdo é um `Identidade.id` opaco que
# já é reconferido no banco a cada requisição (`apps/core/sessao.py`). A tabela
# `django_session` custaria uma escrita por login e um SELECT por requisição em
# troca de nada — e por isso `django.contrib.sessions` NÃO entra em
# INSTALLED_APPS: este backend não tem model. Trocar por sessão em banco no dia
# em que a Caixa precisar revogar sessão de longe é mudar esta linha.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

# Nome próprio, não o `sessionid` de fábrica: `meshcraft.top` serve o `funil` na
# raiz e a Caixa sob /forms/sugestoes. Duas células no MESMO domínio com o mesmo
# nome de cookie é uma sobrescrevendo a sessão da outra.
#
# O nome mudou de `sugestoes_sessao` para `meshcraft_sessao` em 24/08/2026
# (DECISAO-onde-mora-a-sessao §5.1), e a troca é OBRIGATÓRIA junto com a do
# PATH logo abaixo — não é cosmética. O navegador guarda cookie por
# (nome, domínio, **caminho**): publicar o mesmo `sugestoes_sessao` em "/" sem
# renomear deixaria DOIS cookies de mesmo nome convivendo — o velho ainda em
# /forms/sugestoes, o novo em / — e qual deles o servidor lê passa a depender
# de regra de precedência por caminho. Nome novo faz o velho ser simplesmente
# ignorado (e expirar sozinho). Preço aceito e anunciado: quem estava logado no
# momento do deploy é deslogado UMA vez, e reentra com um clique — sessão
# ausente já responde 302 para a porta, nunca erro.
SESSION_COOKIE_NAME = "meshcraft_sessao"

# ALCANCE DE SITE, e é este o coração da DECISAO-onde-mora-a-sessao.
#
# Até 24/08/2026 esta linha era `FORCE_SCRIPT_NAME or "/"`, ou seja o cookie
# valia só dentro de /forms/sugestoes — o navegador NÃO o enviava para
# /pt-br/qualquer-coisa, e por isso o site não tinha como saber que a pessoa
# tinha entrado. Não era falta de tela: era o crachá não valer fora da sala.
#
# Com "/", o cookie acompanha a pessoa por todo o domínio, e o `funil` pode
# perguntar "quem é este?" (config/api.py). Quem CONTINUA lendo e assinando o
# cookie é esta célula, e só ela: o segredo e a tabela `Identidade` não saem
# daqui (Lei 2, Lei 3). O site nunca lê o cookie — ele pergunta.
#
# Não é `SESSION_COOKIE_DOMAIN`: alcance de CAMINHO (um host, todas as páginas)
# é o que o site precisa; alcance de DOMÍNIO espalharia o cookie por
# subdomínios que não são desta plataforma. Lei 9 serve N domínios, e cookie
# não atravessa domínio nenhum — cada host tem a sua sessão, como deve ser.
SESSION_COOKIE_PATH = "/"

# `Lax` é OBRIGATÓRIO aqui, não preferência: a volta do Google é uma navegação
# de topo vinda de accounts.google.com. Com `Strict` o navegador NÃO manda o
# cookie nessa volta, o `state` guardado some, e todo login legítimo falha como
# se fosse falsificação.
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# O cookie de CSRF (o `<form>` do /sair) leva o mesmo tratamento e pelo mesmo
# motivo: `csrftoken` genérico no domínio compartilhado é colisão entre células.
CSRF_COOKIE_NAME = "sugestoes_csrf"

# O CSRF NÃO acompanhou a sessão para "/" — ele fica onde estão os formulários.
# Até 24/08/2026 esta linha era `= SESSION_COOKIE_PATH` e as duas andavam
# juntas por acidente de escrita, não por decisão. Agora divergem de propósito:
# a SESSÃO precisa de alcance de site (o `funil` pergunta quem é a pessoa); o
# token de CSRF protege os `<form>` DESTA célula, que vivem todos sob o prefixo
# dela. Mandá-lo para "/" seria superfície a mais — um cookie viajando em toda
# página do site para proteger formulário que não está lá.
CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# Tokens do PAR consumidor→provedor (R1), um por par: TOKENS_ACEITOS_FUNIL etc.
# ---------------------------------------------------------------------------
# A Caixa passa a ser PROVEDORA a partir da DECISAO-onde-mora-a-sessao: o
# `funil` pergunta "quem é este?" pela API interna (config/api.py). O mesmo
# padrão que `alunos` já usa para aceitar a própria Caixa como consumidora.
#
# Env ausente ⇒ conjunto VAZIO ⇒ toda chamada é recusada com 401. Fail-closed
# por construção, e sem derrubar o boot: a célula sobe, as páginas seguem
# servindo, e só a API interna fica fechada até o token existir no env.
TOKENS_ACEITOS = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_ACEITOS_") and valor
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                # O sininho (EVO-21): a contagem de não-lidos fica disponível em
                # TODA página sem nenhuma view lembrar de pô-la no contexto —
                # Lei 1, porque um combinado desses é esquecido pela primeira
                # view escrita depois. O valor é preguiçoso (um callable que o
                # Django só executa se o template pedir), então página que não
                # mostra o sino não paga consulta. Ver apps/core/avisos.py.
                "apps.core.avisos.sino",
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

# O fuso em que a Caixa MOSTRA hora — o armazenamento continua em UTC (USE_TZ).
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`: até o
# EVO-21 nenhuma página desta célula renderizava data, então o erro não tinha
# como aparecer. A primeira que renderiza é a dos avisos, e ela mostrava a um
# aluno brasileiro o horário de Chicago — cinco horas antes, sem nada indicando
# a troca. É dívida das outras células também, não invenção desta.
TIME_ZONE = "America/Sao_Paulo"
