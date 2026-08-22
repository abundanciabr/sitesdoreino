# config/huey.py  # [RECEITA:R8 v1]
# Instância única do Huey desta célula (fila intra-célula). `settings.HUEY`
# aponta para cá e `huey.contrib.djhuey` está em INSTALLED_APPS — é isso que
# dá o entrypoint canônico `python manage.py run_huey` (faz django.setup() e o
# autodiscover de tasks.py; sem ele o worker sobe com o registro vazio e não
# executa nada — ARMADILHAS §4.11).
import os

from huey import RedisHuey

# NUNCA fail-hard no import: o container web importa este módulo via
# INSTALLED_APPS (djhuey) e não pode morrer se HUEY_REDIS_URL faltar no env.
# O default é inofensivo — conexão do Huey é preguiçosa, só o worker
# (run_huey) de fato conecta; no CI e na VPS a variável existe de verdade.
HUEY_REDIS_URL = os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/1")

huey = RedisHuey("checkout", url=HUEY_REDIS_URL)
