<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.11  ·  referencias antigas "ARMADILHAS §4.11" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.11 Worker do Huey não executa nada: `TaskRegistry` vazio ou `AppRegistryNotReady`

**Sintoma:** o `huey_consumer.py` sobe e loga
`The following commands are available:` **sem nada listado** — e nenhuma task jamais
roda. Trocando o caminho do módulo para o das tasks, o processo nem sobe:
`django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.`
**Causa:** duas peças que precisam acontecer **nesta ordem** e que o
`huey_consumer.py` não faz sozinho:
1. `huey_consumer.py <caminho>` importa **só** o módulo que você nomeou. Apontando
   para `config.huey.huey`, ele acha a instância do Huey — mas `apps/eventos/tasks.py`
   nunca é importado, então o `@huey.task` nunca se registra. Registro vazio ⇒ o
   worker não reconhece nenhuma mensagem da fila.
2. Apontando para `apps.eventos.tasks.huey` o registro seria preenchido, mas o import
   estoura antes: `tasks.py` importa models, e model fora de `django.setup()` é
   `AppRegistryNotReady`. `DJANGO_SETTINGS_MODULE` sozinho **não** resolve — ele
   configura as settings, não o registro de apps.

Isso só não aparece antes porque `huey.contrib.djhuey` (que traria `manage.py
run_huey`, que faz o setup e o autodiscover) **não** está em `INSTALLED_APPS`.
Medido em 21/08/2026, dentro da imagem de `mensageria`; `grep -rn
"run_huey\|huey_consumer\|djhuey" .` no repositório inteiro não devolve nada — não
havia comando canônico a copiar.

**Solução (a definitiva):** `huey.contrib.djhuey` em `INSTALLED_APPS` e
`python manage.py run_huey` — uma linha de `command:`. Enquanto isso não entra
(ARMADILHAS §1/H10), o contorno que **funciona e está medido** é fazer o bootstrap no
próprio `command:` do compose, nesta ordem:

```python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
import apps.eventos.tasks              # é este import que popula o TaskRegistry
from huey.bin.huey_consumer import consumer_main
consumer_main()                        # lê o caminho da instância de sys.argv[1:]
```

Sinal de que deu certo, no log do worker: a linha
`+ apps.eventos.tasks.enviar_notificacao` logo abaixo de
`The following commands are available:`. Se essa linha não aparecer, o worker está
de pé e inútil — e nada no `docker compose ps` vai dizer isso.
**Origem:** despacho infra/consumers — ao subir o worker Huey de `mensageria`.
