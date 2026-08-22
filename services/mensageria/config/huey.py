# config/huey.py  # [RECEITA:R8 v1]
import os

from huey import RedisHuey

# `os.environ.get` com default inofensivo, NÃO fail-hard: com `huey.contrib.djhuey`
# em INSTALLED_APPS, config/settings.py importa este módulo (settings.HUEY) — ou
# seja, o container WEB também passa por aqui no boot, e import de settings nunca
# pode estourar (ARMADILHAS §5.3). O default é inofensivo porque o pool do redis-py
# é preguiçoso: nada conecta no import. Em produção os três containers da célula
# (web, consumer, worker) compartilham infra/env/mensageria.env, que define o
# valor real (redis://redis:6379/7).
huey = RedisHuey(url=os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/0"))
