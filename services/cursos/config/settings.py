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
# `identidade`, o da `alunos`, a lista `CURSOS_PROFESSORES` do plantão, a chave
# da Anthropic do Assistente de laudo, o endereço do sininho…) é lida NO PONTO
# DE USO, com default inofensivo — e a razão está medida em `armadilhas/097`:
# cliente que lê env no `__init__` transforma env ausente em HTTP 500 em TODA
# página, com o deploy verde. A chave da Anthropic, em especial: sem ela quem
# falha é só o botão "Rascunhar laudo", em português, e a sala de aula inteira
# continua de pé (o molde é `services/forum/apps/core/agente.py`).
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"

# A sala de aula serve sob prefixo: meshcraft.top/cursos
# (`PLANO-CELULA-CURSOS.md` §6). O Traefik NÃO remove o prefixo — quem o
# conhece é esta variável, nunca o `urls.py`. Ver `armadilhas/029` e
# `tests/test_healthz_script_name.py`.
#
# `/cursos`: seis letras, longe de qualquer forma de código de idioma, e o
# inventário de rotas (`ci/tests/test_rotas_sem_forma_de_locale.py`) entra no
# MESMO PR do Traefik (`armadilhas/089`, degrau 1.7 da escada), não neste.
# Nome da célula = nome da rota, de propósito: o par `/conquistas` ↔
# `gamificacao` já custa uma tradução mental a cada leitura. E `/cursos` está
# livre: o `funil` só o cita num exemplo de teste de roteamento (medido em
# 04/09/2026, `PLANO-CELULA-CURSOS.md` §2).
#
# E o prefixo é CAMINHO, não subdomínio, pela mesma razão do fórum: o cookie
# de sessão do site é de host. Em `cursos.meshcraft.top` ele não viaja, e a
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
# estrita de Referer do CSRF — a que vai proteger o registro de pausa, o envio
# do checkpoint e o formulário do laudo — não roda. Custa uma linha agora;
# descobrir depois custa um formulário quebrado só em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# `dj_database_url.parse` entrega `CONN_MAX_AGE = 0`, e a ausência do ajuste é
# uma DECISÃO, não esquecimento: sob ASGI, `conn_max_age > 0` vaza uma conexão
# de banco por requisição, e nem a suíte nem o `/healthz` nem o deploy acusam
# (`armadilhas/170`). Quando a porta de máquina (degrau 1.3) e o relógio da
# fila de revisão (degrau 2.1) chegarem, a resposta certa para reaproveitar
# conexão é o POOL nativo do Django 5.1 (`OPTIONS["pool"]` +
# `psycopg[binary,pool]`, o desenho que a `identidade` já roda), nunca
# `conn_max_age`.
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # [RECEITA:R8 v1] dá o entrypoint `python manage.py run_huey` (django.setup
    # + autodiscover de tasks.py — sem isso o worker sobe com registro vazio e
    # não executa nada, `armadilhas/030` §4.11). É o comando do serviço
    # auxiliar desta célula no compose (degrau 1.7): o relay da outbox e o
    # tique do prazo de revisão, os dois em `apps/cursos/tasks.py`.
    "huey.contrib.djhuey",
    "apps.core",
    # O conteúdo do curso como dado: o curso, os blocos, as aulas com suas 16
    # peças, as pausas e os instrumentos (degrau 1.2, `PLANO-CELULA-CURSOS.md`
    # §4); o progresso (1.8); o envio e a outbox (2.1). O laudo e o rascunho
    # da IA vêm nos degraus 2.2 e 2.3.
    "apps.cursos",
]

# O run_huey do djhuey consome a MESMA instância onde as tasks se registram
# (config/huey.py — leitura de HUEY_REDIS_URL nunca fail-hard no import).
from config.huey import huey as HUEY  # noqa: E402

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # A porta desta célula ainda NÃO existe — ela nasce com a porta de máquina
    # (degrau 1.3, o reconhecimento de sessão repassado à `identidade`).
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
# `DECISAO-celula-de-identidade.md` §6.4; `PLANO-CELULA-CURSOS.md` §9), não
# esquecimento: quem assina o cookie `meshcraft_sessao` é a célula
# `identidade`, e só ela. A sala de aula **repassa** o cookie recebido e
# pergunta quem é — nunca o lê, nunca o escreve.
#
# Duas células assinando o MESMO cookie com chaves diferentes produzem um
# cabo-de-guerra invisível: abrir a aula deslogaria do site, e vice-versa,
# **sem erro em lugar nenhum, sem log, sem alarme** (`armadilhas/143`).
#
# A tentação concreta que isto mata tem nome aqui, e são duas. A CERIMÔNIA DO
# BOSS: quando a última aula de um Bloco abre a porta, a tela cheia celebra,
# uma vez só, e toda tela assim precisa saber "esta pessoa já viu?". E o LAUDO
# RECEBIDO: "o aluno já leu a devolução?" decide se a data aparece de novo em
# destaque. O caminho mais curto para as duas é `request.session[...]`, que
# funciona em dev, passa em teste de unidade e desloga a plataforma inteira em
# produção. O estado mora no MODELO (o `Progresso` guarda a cerimônia pendente
# e a leitura do laudo), como a gamificação faz com `celebracoes_pendentes`.
# Guarda: `tests/test_inv_cursos_nao_assina_sessao.py`.

# O cookie de CSRF leva nome próprio: `csrftoken` genérico num domínio que
# serve várias células é colisão — o fórum, a Caixa, a identidade, a admin, a
# gamificação e as encomendas já fazem o mesmo.
CSRF_COOKIE_NAME = "cursos_csrf"
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
# conhece. Com PADRÃO, de propósito: o provisionamento não escreve estas
# chaves, e a trava de deriva dele reprova env com variável que ele não sabe
# gerar. Molde: `services/gamificacao/config/settings.py`.
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
                # O RODAPÉ e o MENU DO TOPO em TODA página (`apps/core/rodape.py`
                # e `apps/core/menu.py`). Processadores de contexto, e não uma
                # inclusão escrita em cada template, porque "em todas as
                # páginas" não pode depender de alguém lembrar da peça: tela
                # nova nasce com as duas (`armadilhas/242`), e
                # `ci/tests/test_pecas_comuns_em_toda_celula_publica.py` mede
                # esta fiação. Quem desenha é `cursos/moldura.html`.
                "apps.core.rodape.rodape_do_contexto",
                "apps.core.menu.menu_do_contexto",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Tokens do PAR consumidor->provedor (R1), um por par: TOKENS_ACEITOS_ADMIN etc.
# ---------------------------------------------------------------------------
# Env ausente => conjunto VAZIO => toda chamada a `/api/cursos` é recusada com
# 401. Fail-closed por construção, e sem derrubar o boot: a célula sobe, o
# `/healthz` segue respondendo, e só a porta de máquina fica fechada até o
# token existir no env. É o mesmo desenho de `identidade`, `alunos`, `forum` e
# `gamificacao`. O primeiro par é o editor do Admin (degrau 1.5), que lê
# `TOKENS_ACEITOS_ADMIN` daqui e o mesmo valor em `CURSOS_API_TOKEN` de lá.
#
# **Aqui o conjunto vazio é o ÚNICO cadeado**, e isso é diferente da
# `identidade`: esta célula roda sob `SCRIPT_NAME=/cursos`, e o corte do
# prefixo é do Django, não do Traefik — a porta é alcançável pela borda pública
# (`armadilhas/186`). Não há topologia por baixo para segurar o que este
# conjunto deixar passar.
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
# Aqui o DIA é a unidade da promessa ao aluno: um envio devolvido leva uma
# data de retorno, e ela é "amanhã ou depois" no dia de São Paulo
# ([INV-CUR-L1]); o prazo de 24 horas da fila de revisão é mostrado à
# professora em hora local, e o estouro se registra no dia em que aconteceu
# ([INV-CUR-L3]); a Ficha de Série da semana fecha na sexta de São Paulo. Com o
# default de fábrica, um laudo emitido à 1h da manhã de terça em São Paulo
# ainda seria "segunda" para o sistema, e a data de retorno "terça" passaria
# como se fosse amanhã, sem ninguém ver. Guarda: `tests/test_fuso_horario.py`.
TIME_ZONE = "America/Sao_Paulo"
