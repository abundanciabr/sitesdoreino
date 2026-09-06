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
# `identidade`, o endereço do sininho, a lista de quem confere portfólio) é
# lida NO PONTO DE USO, com default inofensivo — e a razão está medida em
# `armadilhas/097`: cliente que lê env no `__init__` transforma env ausente em
# HTTP 500 em TODA página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# ---------------------------------------------------------------------------
# O PREFIXO — e nesta célula ele tem uma pergunta em aberto, escrita na cara
# ---------------------------------------------------------------------------
# A casa das Páginas do aluno serve sob prefixo, como as vizinhas: o Traefik
# NÃO remove o prefixo, e quem o conhece é esta variável, nunca o `urls.py`
# (`armadilhas/029`, `tests/test_healthz_script_name.py`). Nome da célula =
# nome da rota (`/pages`), de propósito: o par `/conquistas` ↔ `gamificacao`
# já custa uma tradução mental a cada leitura, e não se cria um segundo
# (`PLANO-PORTFOLIO-DO-ALUNO.md` §4).
#
# **A pergunta que esta gênese NÃO responde, e não deve responder.** Esta
# célula tem DOIS endereços públicos, decisão do mantenedor de 02/09/2026
# (plano §4): `meshcraft.top/pages/...` para o aluno logado e
# `meshcraft.top/estudio/<apelido>` para o link que ele manda ao cliente. E
# `FORCE_SCRIPT_NAME` carrega UM prefixo só. Como os dois entram é decisão do
# degrau 05 (o PR do compose e do Traefik), tomada com o inventário de rotas
# na mão, e escrevê-la aqui hoje seria inventar desenho num PR que não tem
# como prová-lo. As duas mecânicas possíveis, nomeadas para quem chegar lá não
# começar do zero: (a) `SCRIPT_NAME=/pages` e o Traefik removendo `/estudio`
# com StripPrefix, de modo que a vitrine chegue ao Django na raiz do urlconf;
# (b) `SCRIPT_NAME` vazio, os dois prefixos declarados no urlconf e roteados
# sem remoção. A (b) contraria `armadilhas/029` (o urlconf passaria a conhecer
# o próprio endereço) e por isso não é a favorita, mas a medição é de lá.
#
# E o prefixo é CAMINHO, não subdomínio, pela mesma razão do fórum e da
# `encomendas`: o cookie de sessão do site é de host. Em `pages.meshcraft.top`
# ele não viaja, e a célula passaria a exigir um segundo login — que é
# exatamente o que o [INV-P12] existe para impedir.
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik. Esta célula responde em qualquer host servido pela
# plataforma (Lei 9 — um deploy, N domínios); a defesa de host, se um dia for
# preciso prendê-la a um só, mora no gateway, não aqui.
ALLOWED_HOSTS = ["*"]

# O TLS termina no Traefik: para o uvicorn, a requisição chega em http. Sem
# esta linha o Django trata toda requisição como insegura, e a conferência
# estrita de Referer do CSRF — a que vai proteger o marcar item da Prancheta,
# o colar link de peça, o pedir conferência e o ligar e desligar a vitrine —
# não roda. Custa uma linha agora; descobrir depois custa um formulário
# quebrado só em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `dj_database_url.parse` entrega `CONN_MAX_AGE = 0`, e a ausência do ajuste é
# uma DECISÃO, não esquecimento: sob ASGI, `conn_max_age > 0` vaza uma conexão
# de banco por requisição, e nem a suíte nem o `/healthz` nem o deploy acusam
# (`armadilhas/170`). Quando a medição periódica de link quebrado chegar
# (degrau 08, critério AC-09), ela roda em processo próprio (`run_huey`,
# síncrono), onde o problema do ASGI não existe. E se um dia for preciso
# reaproveitar conexão nas telas, a resposta certa é o POOL nativo do Django
# 5.1 (`OPTIONS["pool"]` + `psycopg[binary,pool]`, o desenho que a
# `identidade` já roda), nunca `conn_max_age`.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    # O portfólio, a peça, o item de conferência e o estado do aluno, nascidos
    # no degrau 02 da escada (`PLANO-PORTFOLIO-DO-ALUNO.md` §5, TAR-178), numa
    # app própria dentro desta casa. Não há tela, porta de máquina nem evento:
    # eles são os degraus 06, 03 e 12.
    #
    # A fronteira de site e a de aluno moram numa tabela só (`Portfolio`), e as
    # três filhas chegam às duas pela chave estrangeira local. Nenhuma chave
    # estrangeira sai deste banco (critério AC-02), e o isolamento por aluno
    # tem uma porta só, o `do_aluno` dos gerenciadores (AC-07), com guarda
    # provado por mutação em `tests/test_isolamento_por_aluno.py`.
    "apps.portfolio",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A porta desta célula ainda NÃO existe — ela nasce no degrau 06, com o
    # reconhecimento de sessão repassado à `identidade`. Quando nascer, vem por
    # último (como a da `admin`), e a isenção do `/healthz` compara
    # `request.path_info`, NUNCA `request.path` (`armadilhas/029`; o guarda já
    # está plantado em `tests/test_healthz_script_name.py`).
    #
    # E ela tem uma segunda isenção a acertar, que nenhuma célula vizinha tem:
    # `/estudio/<apelido>` é a VITRINE PÚBLICA, para um cliente que nunca vai
    # entrar na plataforma. A porta fail-closed do critério AC-05 vale para
    # `/pages`; a vitrine é opt-in do aluno e aberta a quem tem o link
    # (`noindex` não negociável, plano §7). Uma porta escrita sem essa
    # distinção fecha a vitrine e a única prova disso seria o cliente do aluno
    # vendo um pedido de login.
]

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei ([INV-P12];
# `DECISAO-celula-de-identidade.md` §6.4; `CS-PAGES-0001` e
# `PLANO-PORTFOLIO-DO-ALUNO.md` §5, degrau 06), não esquecimento: quem assina o
# cookie `meshcraft_sessao` é a célula `identidade`, e só ela. Esta célula
# **repassa** o cookie recebido e pergunta quem é — nunca o lê, nunca o
# escreve.
#
# Duas células assinando o MESMO cookie com chaves diferentes produzem um
# cabo-de-guerra invisível: abrir a Prancheta deslogaria do site, e vice-versa,
# **sem erro em lugar nenhum, sem log, sem alarme** (`armadilhas/143`).
#
# A tentação concreta que isto mata tem nome aqui: a PRANCHETA GUARDA
# PROGRESSO. O critério AC-06 exige que o aluno marque um item, feche o
# navegador, abra em OUTRO APARELHO e encontre a marcação no lugar — e o
# caminho mais curto para lembrar de uma marcação é `request.session[...]`, que
# funciona em dev, passa em teste de unidade, reprova o próprio AC-06 (sessão
# não atravessa aparelho) e desloga a plataforma inteira em produção. O estado
# mora no MODELO, por aluno, do degrau 02 em diante. Guarda:
# `tests/test_inv_pages_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — o fórum, a Caixa, a identidade, a admin, a
# gamificação, a `encomendas` e a `cursos` já fazem o mesmo.
CSRF_COOKIE_NAME = "pages_csrf"
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
# O FUSO
# ---------------------------------------------------------------------------
# O fuso em que a célula MOSTRA hora; o armazenamento continua em UTC (USE_TZ).
# Sem esta linha vale o default de fábrica do Django, `America/Chicago`: cinco
# horas atrás, capaz de trocar o DIA perto da virada, sem erro nenhum
# (`armadilhas/099`).
#
# Aqui a data é o que o aluno e o cliente dele leem: "conferido pela escola em
# 05/09/2026" no selo do critério AC-12, o prazo do pedido de conferência do
# AC-11 (pelo molde da tela de marcos) e a data de cada peça na vitrine do
# AC-13. Com o default de fábrica, um selo saído às 22h de São Paulo levaria a
# data do dia ANTERIOR na página que o aluno manda ao cliente pagante, e nada
# acusaria: CI verde, deploy verde, `/healthz` 200. Guarda:
# `tests/test_fuso_horario.py`.
TIME_ZONE = "America/Sao_Paulo"
