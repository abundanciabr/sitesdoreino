# config/huey.py
"""A instância única do Huey desta célula — o batimento do tique de um minuto.

Cópia do PADRÃO das vizinhas (`gamificacao`, `alunos`, `sugestoes`, `checkout`,
`quiz`, `mensageria`), nunca do arquivo (Lei 7): `settings.HUEY` aponta para cá
e `huey.contrib.djhuey` está em `INSTALLED_APPS`. É essa dupla que dá o
entrypoint canônico `python manage.py run_huey`, o único que faz
`django.setup()` e o autodiscover de `tasks.py`. Subir o `huey_consumer` direto
dá um worker de pé com o registro VAZIO, que não executa nada e não reclama de
nada (`armadilhas/030`).

**Aqui o Huey é só o BATIMENTO, e essa distinção é a alma do degrau 2.4.** Nas
outras células ele carrega o relay da outbox: o trabalho está na fila do Redis.
Nesta, o que ele faz a cada minuto é chamar uma função que lê o banco e
pergunta *"o que está vencido AGORA?"*. Nada de estado da fila mora no Redis, e
nenhuma oferta tem um agendamento próprio esperando por ela — se o Redis sumir
por seis horas, a primeira passada quando ele voltar faz exatamente o que as
seis passadas perdidas fariam. É o que a lei chama de *"reavaliação periódica,
nunca timer agendado"* (plano §7.4), e o que o cenário 15 do anexo B mede.

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
# Quem entrega a variável de verdade é o `infra/docker-compose.yml`, no serviço
# do tique — e ele nasce no degrau 2.10 da escada (TAR-128), que é o PR do
# compose e do Traefik. Até lá **o tique não roda em produção**, e isso é
# esperado: a célula inteira ainda não responde pela internet
# (`armadilhas/088`). O que existe deste degrau é a mecânica, com guarda.
HUEY_REDIS_URL = os.environ.get("HUEY_REDIS_URL", "redis://localhost:6379/1")

# O nome é o namespace das chaves no Redis: com o nome de fábrica, duas células
# dividindo o mesmo Redis dividiriam também a fila.
huey = RedisHuey("encomendas", url=HUEY_REDIS_URL)
