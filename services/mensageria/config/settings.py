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


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = (
    os.environ.get("SCRIPT_NAME") or None
)  # célula dona do próprio prefixo

# Atrás do Traefik; mensageria não expõe rota pública (constituicoes/AGENTS.mensageria.md)
# — sem middleware CONV-SITE aqui, sem regra de negócio neste esqueleto.
ALLOWED_HOSTS = ["*"]

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    # A instalação documentada do Django para os campos de `contrib.postgres` —
    # aqui, o `ArrayField` de `apps.jornadas.Passo.canais`. Não cria tabela, não
    # tem migração própria, e não vira dependência nova: esta célula já é
    # Postgres em produção, em dev e no CI.
    "django.contrib.postgres",
    "huey.contrib.djhuey",  # entrypoint oficial do worker: manage.py run_huey (§4.11)
    "apps.core",
    "apps.eventos",
    # O motor das sequências (`PLANO-SEQUENCIAS-DE-MENSAGENS.md` §4.1: o
    # mantenedor escolheu em 30/08/2026 que ele mora DENTRO desta célula, e não
    # numa célula nova). App separado, banco compartilhado: ele lê e escreve as
    # próprias tabelas e toca `apps.eventos` num ponto só — criando a linha de
    # `EnvioRegistrado`. Ler ou escrever qualquer outra tabela de lá é o
    # critério de morte §10.7 do plano.
    "apps.jornadas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# ---------------------------------------------------------------------------
# Tokens do PAR consumidor->provedor (R1) da porta de máquina, em DOIS graus.
# ---------------------------------------------------------------------------
# O sufixo é sempre o PAR que consome, nunca o nome desta célula:
# `TOKENS_SOMENTE_LEITURA_ADMIN` é "o par `admin` pode ler". É a convenção que
# as dez células com porta já seguem, e é ela que o provisionamento escreve.
#
# Env ausente => conjunto VAZIO => toda chamada a `/api/mensageria` é recusada
# com 401. Fail-closed por construção, e sem derrubar o boot: a célula sobe, o
# `/healthz` segue respondendo, o motor das jornadas segue mandando mensagem, e
# só a porta de máquina fica fechada até o token existir no env.
#
# POR QUE SÃO DOIS CONJUNTOS, E NÃO UM `TOKENS_ACEITOS` plano: esta porta tem
# uma operação que PUBLICA VERSÃO NOVA de uma sequência que escreve para alunos
# de verdade. Conjunto plano daria essa escrita a qualquer par que só precisasse
# desenhar uma tela de consulta. A `identidade` já separou o grau assim com
# `TOKENS_SENHA_*` (gravar a senha de alguém é mais que perguntar quem alguém
# é); aqui a diferença é que o grau de publicação JÁ CONTÉM a leitura, para o
# mantenedor não ter de pôr o mesmo par nos dois envs.
#
# Quem lê os dois conjuntos é `apps/core/auth.py`, no ponto de uso.
TOKENS_SOMENTE_LEITURA = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_SOMENTE_LEITURA_") and valor
}

TOKENS_PUBLICACAO = {
    valor
    for chave, valor in os.environ.items()
    if chave.startswith("TOKENS_PUBLICACAO_") and valor
}

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

USE_TZ = True

# O fuso em que a mensageria MOSTRA hora — o armazenamento continua em UTC
# (USE_TZ). Sem esta linha vale o default de fábrica do Django,
# `America/Chicago`: cinco horas atrás, capaz de trocar até o DIA perto da
# virada, sem nada acusando a troca. Aqui o estrago não é só tela: o corpo de
# um e-mail renderizado por template converte `datetime` aware em silêncio.
# Foi assim que a `sugestoes` foi pega em 24/08/2026 (EVO-21).
# Guarda: tests/test_fuso_horario.py (armadilhas/099).
TIME_ZONE = "America/Sao_Paulo"

# ---------------------------------------------------------------------------
# O E-MAIL DE VERDADE (02/09/2026) — SMTP, e a escolha do transporte é decisão
# ---------------------------------------------------------------------------
# O mantenedor escolheu o BREVO como provedor, entre três opções com o custo de
# cada uma na mesa. Mas o que entra aqui é **SMTP**, e não a API HTTP do Brevo,
# de propósito: SMTP é o denominador comum de todo provedor sério (Brevo, SES,
# Resend, Postmark), então trocar de fornecedor um dia vira mudança de env — não
# um PR reescrevendo o cliente. A escolha dele fica no arquivo de env da VPS,
# que é onde ela pertence.
#
# `os.environ.get` com padrão vazio, nunca `env()`: o `env()` desta casa é
# fail-hard, e derrubaria os TRÊS containers da célula no boot enquanto o passo
# do mantenedor não estiver feito. Ausência aqui não é erro de configuração — é
# o estado normal até ele criar a conta. Quem falha alto é o ENVIO, no ponto de
# uso (`apps/eventos/tasks.py`), que é onde a falha significa alguma coisa.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
# 587 com STARTTLS é o que o Brevo documenta e o que todo provedor aceita. A
# porta 465 (SSL direto) existiria com EMAIL_USE_SSL — as duas juntas o Django
# recusa, e por isso a escolha é uma linha só e não duas variáveis.
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.environ.get("SMTP_FROM", "")

# djhuey lê `settings.HUEY`. Precisa ser a MESMA instância que as tasks decoram
# (config/huey.py) — uma instância nova aqui criaria uma SEGUNDA fila: o handler
# enfileira numa, o `run_huey` escuta a outra, e nenhum e-mail sai (ARMADILHAS
# §4.11). O import é seguro: config/huey.py não é fail-hard (default inofensivo).
from config.huey import huey as HUEY  # noqa: E402
