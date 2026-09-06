# config/huey.py  # [RECEITA:R8 v1]
"""A instância única do Huey desta célula: a fila intra-célula.

`settings.HUEY` aponta para cá e `huey.contrib.djhuey` está em
`INSTALLED_APPS`: é essa dupla que dá o entrypoint canônico
`python manage.py run_huey`, o único que faz `django.setup()` e o autodiscover
de `tasks.py`. Sem ele, o worker sobe com o registro VAZIO, não executa nada e
não reclama de nada (`armadilhas/030`, §4.11).

São dois os trabalhos de fundo desta casa, os dois em `apps/portfolio/tasks.py`:
a reconferência diária dos links das peças (critério AC-09) e a rede de
segurança do relay da outbox, que republica de minuto em minuto o que o
`on_commit` não conseguiu publicar (degrau 12, critério AC-12). Os dois rodam
aqui, em processo próprio e síncrono, e NUNCA dentro do ASGI: a razão está por
extenso em `config/settings.py`, no bloco do `DATABASES` (`armadilhas/170`).

Fila intra-célula = Huey. Comunicação ENTRE células = eventos, nunca uma célula
enfileirando task na outra. Molde: `services/cursos/config/huey.py`, copiado e
nunca importado (Lei 3).
"""

import os

from huey import RedisHuey

# NUNCA fail-hard no import. O container **web** importa este módulo via
# INSTALLED_APPS (djhuey) e não pode morrer no boot se `HUEY_REDIS_URL` faltar
# no env: a Prancheta inteira sairia do ar por causa da fila
# (`armadilhas/097`). O default é inofensivo: a conexão do Huey é preguiçosa e
# só o worker (`run_huey`) de fato conecta; faltando a variável de verdade,
# quem falha alto é o worker, no log dele.
HUEY_REDIS_URL = os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/1")

# O nome é o namespace das chaves no Redis: com o nome de fábrica, duas células
# dividindo o mesmo Redis dividiriam também a fila.
huey = RedisHuey("pages", url=HUEY_REDIS_URL)
