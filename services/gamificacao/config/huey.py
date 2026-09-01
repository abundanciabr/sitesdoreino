# config/huey.py
"""A instância única do Huey desta célula — a fila intra-célula.

Cópia do PADRÃO das vizinhas (`alunos`, `sugestoes`, `checkout`, `quiz`,
`mensageria`), nunca do arquivo (Lei 7): `settings.HUEY` aponta para cá e
`huey.contrib.djhuey` está em `INSTALLED_APPS`. É essa dupla que dá o
entrypoint canônico `python manage.py run_huey`, o único que faz
`django.setup()` e o autodiscover de `tasks.py`. Subir o `huey_consumer`
direto dá um worker de pé com o registro VAZIO, que não executa nada e não
reclama de nada (`armadilhas/030`).

Fila intra-célula = Huey. Comunicação ENTRE células = eventos — nunca uma
célula enfileirando task na outra.
"""

import os

from huey import RedisHuey

# NUNCA fail-hard no import. O container **web** importa este módulo via
# INSTALLED_APPS (djhuey) e não pode morrer no boot se `HUEY_REDIS_URL` faltar
# no env — a célula inteira sairia do ar por causa da fila (`armadilhas/097`).
# O default é inofensivo: a conexão do Huey é preguiçosa e só o worker
# (`run_huey`) de fato conecta; faltando a variável de verdade, quem falha alto
# é o worker, no log dele.
#
# E aqui a ausência tem um segundo motivo, próprio desta célula: o env real é
# escrito na VPS por `infra/provisionar-gamificacao.sh`, que rodou em
# 31/08/2026, ANTES de existir relay. Ele não escreveu esta chave, e voltar
# para escrevê-la custaria um passo manual do mantenedor por um valor que não é
# segredo. Quem a entrega é o `infra/docker-compose.yml`, no serviço
# `gamificacao-relay`, exatamente como já faz com `REDIS_STREAMS_URL` do
# consumidor.
HUEY_REDIS_URL = os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/1")

# O nome é o namespace das chaves no Redis: com o nome de fábrica, duas células
# dividindo o mesmo Redis dividiriam também a fila.
huey = RedisHuey("gamificacao", url=HUEY_REDIS_URL)
