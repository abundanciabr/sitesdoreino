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
# `identidade`, o da `alunos`, a lista de professores do plantão, o endereço
# do sininho…) é lida NO PONTO DE USO, com default inofensivo — e a razão está
# medida em `armadilhas/097`: cliente que lê env no `__init__` transforma env
# ausente em HTTP 500 em TODA página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A Fila do Primeiro Dólar serve sob prefixo: meshcraft.top/encomendas
# (`DECISAO-fila-do-primeiro-dolar.md` §3.9 e §4). O Traefik NÃO remove o
# prefixo — quem o conhece é esta variável, nunca o `urls.py`. Ver
# `armadilhas/029` e `tests/test_healthz_script_name.py`.
#
# `/encomendas`: dez letras, longe de qualquer forma de código de idioma, e o
# inventário de rotas (`ci/tests/test_rotas_sem_forma_de_locale.py`) entra no
# MESMO PR do Traefik (`armadilhas/089`, degrau 2.10 da escada), não neste.
# Nome da célula = nome da rota, de propósito: o par `/conquistas` ↔
# `gamificacao` já custa uma tradução mental a cada leitura.
#
# E o prefixo é CAMINHO, não subdomínio, pela mesma razão do fórum: o cookie
# de sessão do site é de host. Em `encomendas.meshcraft.top` ele não viaja, e
# a célula passaria a exigir um segundo login — que é exatamente o que o
# [INV-P12] existe para impedir.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik. Esta célula responde em qualquer host servido pela
# plataforma (Lei 9 — um deploy, N domínios); a defesa de host, se um dia for
# preciso prendê-la a um só, mora no gateway, não aqui.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem
# esta linha o Django trata toda requisição como insegura, e a conferência
# estrita de Referer do CSRF — a que vai proteger o Aceitar, o Passar, o
# Entregar e o Aprovar — não roda. Custa uma linha agora; descobrir depois
# custa um formulário quebrado só em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `dj_database_url.parse` entrega `CONN_MAX_AGE = 0`, e a ausência do ajuste é
# uma DECISÃO, não esquecimento: sob ASGI, `conn_max_age > 0` vaza uma conexão
# de banco por requisição, e nem a suíte nem o `/healthz` nem o deploy acusam
# (`armadilhas/170`). O tique de um minuto do degrau 2.4 JÁ CHEGOU, e continua
# sem ajuste aqui: ele roda em processo próprio (`run_huey`, síncrono), onde o
# problema do ASGI não existe. Quando a porta de máquina (degrau 2.7) chegar, a
# resposta certa para reaproveitar
# conexão é o POOL nativo do Django 5.1 (`OPTIONS["pool"]` +
# `psycopg[binary,pool]`, o desenho que a `identidade` já roda), nunca
# `conn_max_age`.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    # O perfil profissional, a fila, as ofertas, as encomendas e a tabela de
    # parâmetros com histórico. Nasceu no degrau 2.2 da escada
    # (`DECISAO-fila-do-primeiro-dolar.md` §7, TAR-120), com as máquinas de
    # estado da seção 7.2 do plano em `Encomenda.TRANSICOES` e num gatilho do
    # PostgreSQL que recusa a transição proibida.
    #
    # O MOTOR DE OFERTA entrou no degrau 2.3 (TAR-121), em
    # `apps/encomendas/motor.py`: os sete invariantes de justiça [INV-ENC-J1] a
    # [INV-ENC-J7] nasceram com ele, cada um com guarda próprio. O miolo é função
    # pura de (estado, `agora`) e a passada é reavaliação periódica, nunca timer
    # agendado — sobrevive a reinício, deploy e queda do Redis.
    #
    # OS RELÓGIOS entraram no degrau 2.4 (TAR-122), em `apps/encomendas/relogio.py`
    # (as horas úteis puras, [INV-ENC-J8]) e `apps/encomendas/tique.py` (a
    # reavaliação de um minuto, [INV-ENC-J9] e [INV-ENC-J10]). O relógio da
    # oferta corre só dentro da janela lida do banco; a encomenda que espera
    # demais na fila vira chamada aberta. **Nenhum timer agendado**: toda a
    # verdade está nas colunas, e por isso a fila sobrevive a reinício, deploy e
    # queda do Redis.
    "apps.encomendas",
    # O BATIMENTO do tique, e só isso. Diferente das vizinhas, aqui o Huey não
    # carrega trabalho nenhum na fila do Redis: ele chama, de minuto em minuto,
    # uma função que pergunta ao BANCO o que está vencido (`apps/encomendas/tasks.py`).
    # Entra em INSTALLED_APPS pelo autodiscover de `tasks.py`, que só o
    # `manage.py run_huey` faz (`armadilhas/030`).
    "huey.contrib.djhuey",
]

# A instância do Huey — importada, não nomeada por string: o djhuey lê
# `settings.HUEY` esperando o OBJETO. `config/huey.py` NÃO faz fail-hard no
# import, de propósito: o container web importa este módulo por causa da linha
# acima, e a célula inteira não pode sair do ar porque a fila ficou sem env
# (`armadilhas/097`).
from config.huey import huey as HUEY  # noqa: E402

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A porta desta célula ainda NÃO existe — ela nasce com a primeira tela
    # (degrau 2.7, o reconhecimento de sessão repassado à `identidade`).
    # Quando nascer, vem por último (como a da `admin`), e a isenção do
    # `/healthz` compara `request.path_info`, NUNCA `request.path`
    # (`armadilhas/029`; o guarda já está plantado em
    # `tests/test_healthz_script_name.py`).
]

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei ([INV-P12];
# `DECISAO-celula-de-identidade.md` §6.4; `DECISAO-fila-do-primeiro-dolar.md`
# §4), não esquecimento: quem assina o cookie `meshcraft_sessao` é a célula
# `identidade`, e só ela. A Fila **repassa** o cookie recebido e pergunta quem
# é — nunca o lê, nunca o escreve.
#
# Duas células assinando o MESMO cookie com chaves diferentes produzem um
# cabo-de-guerra invisível: abrir a fila deslogaria do site, e vice-versa,
# **sem erro em lugar nenhum, sem log, sem alarme** (`armadilhas/143`).
#
# A tentação concreta que isto mata tem nome aqui: a CERIMÔNIA DO PRIMEIRO
# DÓLAR. Na primeira aprovação a tela cheia diz "Você ganhou seu primeiro
# dólar com 3D", uma vez só (plano §5.8) — e toda tela assim precisa saber
# "esta pessoa já viu?". O caminho mais curto é `request.session[...]`, que
# funciona em dev, passa em teste de unidade e desloga a plataforma inteira em
# produção. O estado mora no MODELO (o perfil profissional guarda a cerimônia
# pendente), como a gamificação faz com `celebracoes_pendentes`. Guarda:
# `tests/test_inv_encomendas_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — o fórum, a Caixa, a identidade, a admin e a
# gamificação já fazem o mesmo.
CSRF_COOKIE_NAME = "encomendas_csrf"
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

# ---------------------------------------------------------------------------
# O FUSO — e nesta célula ele não é cosmético, é REGRA DE NEGÓCIO
# ---------------------------------------------------------------------------
# O fuso em que a célula MOSTRA hora; o armazenamento continua em UTC (USE_TZ).
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`: cinco
# horas atrás, capaz de trocar o DIA perto da virada, sem erro nenhum
# (`armadilhas/099`).
#
# Aqui a HORA é a unidade da mecânica: o relógio da oferta corre só das 8h às
# 22h de São Paulo e congela fora da janela (plano §6.3; [INV-ENC-J8]); a
# encomenda vira aberta em 24h na fila ([INV-ENC-J9]); o prazo de produção,
# a extensão de 48h, a aprovação tácita de 48h e o repasse "no próximo dia
# útil" contam todos neste fuso. Com o default de fábrica, uma oferta feita às
# 20h em São Paulo teria o relógio congelado às 17h, e o aluno perderia três
# horas de decisão sem ninguém ver. Guarda: `tests/test_fuso_horario.py`.
TIME_ZONE = "America/Sao_Paulo"
