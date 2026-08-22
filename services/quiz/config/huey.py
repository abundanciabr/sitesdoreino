# config/huey.py  # [RECEITA:R8 v1]
import os

from huey import RedisHuey

# HUEY_REDIS_URL lida com os.environ.get + default inofensivo DE PROPÓSITO —
# NUNCA fail-hard aqui (convenção do lote; ARMADILHAS §5.3): este módulo é
# importado pelo container WEB via INSTALLED_APPS (huey.contrib.djhuey →
# settings.HUEY), e o web não pode morrer no boot se a variável faltar em
# produção. O default localhost só afeta quem realmente consome a fila — o
# worker (`python manage.py run_huey`), que sem a variável certa falha ao
# conectar, alto e claro, no log dele. RedisHuey não conecta no import
# (pool preguiçoso), então instanciar aqui é seguro.
huey = RedisHuey(
    "quiz", url=os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/1")
)
