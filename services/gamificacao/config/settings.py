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
# `identidade`, a lista de monitores da fila de validação, o endereço do
# sininho…) é lida NO PONTO DE USO, com default inofensivo — e a razão está
# medida em `armadilhas/097`: cliente que lê env no `__init__` transforma env
# ausente em HTTP 500 em TODA página, com o deploy verde.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A gamificação serve sob prefixo: meshcraft.top/conquistas
# (`DECISAO-gamificacao.md` §4; `PLANO-CELULA-GAMIFICACAO.md` §5). O Traefik
# NÃO remove o prefixo — quem o conhece é esta variável, nunca o `urls.py`.
# Ver `armadilhas/029` e `tests/test_healthz_script_name.py`.
#
# `/conquistas` e não `/xp`: dez letras, longe de qualquer forma de código de
# idioma, e o inventário de rotas (`ci/tests/test_rotas_sem_forma_de_locale.py`)
# entra no MESMO PR do Traefik (`armadilhas/089`), não neste.
#
# E o prefixo é CAMINHO, não subdomínio, pela mesma razão do fórum: o cookie de
# sessão do site é de host. Em `conquistas.meshcraft.top` ele não viaja, e a
# célula passaria a exigir um segundo login — que é exatamente o que o
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
# estrita de Referer do CSRF — a que vai proteger o "marquei como resolvido",
# o "vi a celebração" e o equipar cosmético — não roda. Custa uma linha agora;
# descobrir depois custa um formulário quebrado só em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `dj_database_url.parse` entrega `CONN_MAX_AGE = 0`, e a ausência do ajuste é
# uma DECISÃO, não esquecimento: sob ASGI, `conn_max_age > 0` vaza uma conexão
# de banco por requisição, e nem a suíte nem o `/healthz` nem o deploy acusam
# (`armadilhas/170`). A tentação chega junto com a porta de máquina do §5 do
# plano — `getPublicProfiles` decora N autores de toda página do fórum, e
# reaproveitar conexão economiza ~24 ms por chamada. A resposta certa naquele
# dia é o POOL nativo do Django 5.1 (`OPTIONS["pool"]` + `psycopg[binary,pool]`,
# o desenho que a `identidade` já roda), nunca `conn_max_age`.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "apps.core",
    # O ledger de XP, os Cristais, a Sequência, a Forja, as medalhas e os
    # Marcos — o §3 do `PLANO-CELULA-GAMIFICACAO.md`, entregue no PR 3 da
    # escada. Entra junto com os três testes-invariante da economia, que são a
    # lei desta célula e nascem como teste que reprova a publicação — nunca
    # como promessa em documento.
    "apps.gamificacao",
    # A memória de quais eventos já foram vistos (a receita R4 v1, igual nas
    # cinco células que consomem). A unicidade de `event_id` é o guarda de
    # idempotência da ENTREGA; a do ledger é a do CRÉDITO, e as duas precisam
    # existir: a primeira impede o handler de rodar de novo, a segunda impede o
    # mesmo fato de pagar duas vezes por caminhos diferentes.
    "apps.eventos",
    # A fila intra-célula, que entrou com a VOZ desta célula (degrau 9): é ela
    # que dá o entrypoint canônico `python manage.py run_huey` — o único que faz
    # `django.setup()` + autodiscover de `tasks.py`. Sem esta linha o worker
    # sobe com o registro VAZIO, não executa nada e não reclama de nada
    # (`armadilhas/030`), e as cartas ficariam paradas na outbox sem ninguém
    # acusar.
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
    # A porta desta célula ainda NÃO existe — ela nasce com o `/conquistas` do
    # PR 7. Quando nascer, vem por último (como a da `admin`), e a isenção do
    # `/healthz` compara `request.path_info`, NUNCA `request.path`
    # (`armadilhas/029`; o guarda já está plantado em
    # `tests/test_healthz_script_name.py`).
]

# ---------------------------------------------------------------------------
# ESTA CÉLULA NÃO ASSINA SESSÃO — e a ausência é a decisão
# ---------------------------------------------------------------------------
# Não há `SESSION_ENGINE`, não há `django.contrib.sessions` em INSTALLED_APPS,
# e não há `SessionMiddleware` acima. Isso é lei ([INV-P12];
# `DECISAO-celula-de-identidade.md` §6.4; `DECISAO-gamificacao.md` §5), não
# esquecimento: quem assina o cookie `meshcraft_sessao` é a célula
# `identidade`, e só ela. A gamificação **repassa** o cookie recebido e
# pergunta quem é — nunca o lê, nunca o escreve.
#
# Duas células assinando o MESMO cookie com chaves diferentes produzem um
# cabo-de-guerra invisível: abrir a página de conquistas deslogaria do site, e
# vice-versa, **sem erro em lugar nenhum, sem log, sem alarme**
# (`armadilhas/143`).
#
# A tentação concreta que isto mata é maior aqui do que em qualquer célula
# anterior, e tem nome: a CELEBRAÇÃO VISCERAL. Quando o aluno sobe de nível ou
# valida um marco, a tela precisa saber "esta pessoa já viu esta comemoração?"
# — e o caminho mais curto para guardar isso é `request.session[...]`. Funciona
# em dev, passa em teste de unidade, e desloga a plataforma inteira em
# produção. Por isso o plano põe `celebracoes_pendentes` no MODELO
# (`PLANO-CELULA-GAMIFICACAO.md` §3) e não na sessão. Guarda:
# `tests/test_inv_gamificacao_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — o fórum, a Caixa, a identidade e a admin já
# fazem o mesmo.
CSRF_COOKIE_NAME = "gamificacao_csrf"
# O token de CSRF protege os `<form>` DESTA célula, que vivem todos sob o
# prefixo dela. Diferente da SESSÃO (que é do site inteiro e mora na
# `identidade`), ele não tem por que viajar para "/".
CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# OS DOIS ENDEREÇOS QUE NÃO SÃO DESTA CÉLULA
# ---------------------------------------------------------------------------
# Para onde mandar quem chega sem sessão, e onde fica a capa do site. Os dois
# moram em OUTRAS células (`identidade` e `funil`), então `{% url %}` não os
# conhece — e cravá-los num template seria endereço alheio escondido dentro do
# HTML desta casa, longe de qualquer lugar onde alguém pensaria em procurar.
# Molde: `services/admin/config/settings.py`.
#
# Com PADRÃO, e isso importa: o `infra/provisionar-gamificacao.sh` não escreve
# estas chaves, e a trava de deriva dele reprova env com variável que ele não
# sabe gerar. Padrão aqui significa que o env não precisa declará-las.
URL_DE_ENTRADA = os.environ.get("URL_DE_ENTRADA", "/entrar/google")
URL_DA_CAPA = os.environ.get("URL_DA_CAPA", "/")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                # O RODAPÉ em TODA página (`apps/core/rodape.py`), 02/09/2026.
                # É processador de contexto, e não uma inclusão escrita em cada
                # template, porque "em todas as páginas" não pode depender de
                # alguém lembrar da peça: tela nova nasce com rodapé
                # (`armadilhas/242`). Quem desenha é `gamificacao/moldura.html`.
                "apps.core.rodape.rodape_do_contexto",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Tokens do PAR consumidor->provedor (R1), um por par: TOKENS_ACEITOS_FORUM etc.
# ---------------------------------------------------------------------------
# Env ausente => conjunto VAZIO => toda chamada a `/api/gamificacao` é recusada
# com 401. Fail-closed por construção, e sem derrubar o boot: a célula sobe, o
# `/healthz` segue respondendo, e só a porta de máquina fica fechada até o token
# existir no env. É o mesmo desenho de `identidade`, `alunos` e `forum`.
#
# **Aqui o conjunto vazio é o ÚNICO cadeado**, e isso é diferente da
# `identidade`: esta célula roda sob `SCRIPT_NAME=/conquistas`, e o corte do
# prefixo é do Django, não do Traefik — a porta é alcançável pela borda pública
# (`armadilhas/186`). Não há topologia por baixo para segurar o que este
# conjunto deixar passar.
#
# Não há `TOKENS_COMPLETOS` aqui, e a ausência é a decisão: aquele degrau existe
# na `identidade` para liberar E-MAIL a pares autorizados. Esta porta não
# devolve dado pessoal nenhum — só id opaco, número e slug (invariante 1 do
# `contracts/gamificacao.openapi.yaml`) —, então não há segundo degrau a
# conceder.
TOKENS_ACEITOS = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_ACEITOS_") and valor
}

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
# Em toda outra célula isso seria uma data errada na tela. Aqui é o contrário:
# o "dia" é a UNIDADE da mecânica. `dia_local` no ledger de XP, o dia ativo da
# Sequência semanal, a janela das missões diárias e o teto suave de pontos por
# dia se decidem todos por esta linha (`PLANO-CELULA-GAMIFICACAO.md` §3). Com o
# default de fábrica, o aluno que estuda às 22h de terça em São Paulo teria o
# esforço contado na terça — e quem estuda às 23h30 veria a Sequência quebrar
# num dia em que ele não faltou. Guarda: `tests/test_fuso_horario.py`.
TIME_ZONE = "America/Sao_Paulo"
