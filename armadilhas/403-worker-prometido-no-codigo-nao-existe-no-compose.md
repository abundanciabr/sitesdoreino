---
schema_version: 2
armadilha: 403
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - infra/docker-compose.yml
  - services/identidade/apps/identidade/tasks.py
guarda:
  tipo: CI
  dono: ci/tests/test_canario_fase_3_outbox.py
  detector: test_compose_declara_relay_periodico_da_identidade
sinal: 'o codigo cita um worker periodico, mas o compose nao tem o servico'
licao: 'Quando a celula ganha outbox periodica, prove a topologia viva tambem: task.py prometendo `run_huey` nao basta. O compose precisa declarar o servico relay, as URLs do Redis e a dependencia da celula web, e o canario de producao deve falhar se esse executor nao existir.'
---

# 403: Worker prometido no codigo nao existe no compose

**Sintoma.** A auditoria da Fase 3 pedia o pacote usado pelos processos
executores. O codigo de `identidade` dizia que o worker periodico era
`identidade-relay`, mas `infra/docker-compose.yml` ainda declarava a celula
como "sem auxiliar" e nao subia esse servico.

**Causa.** A prova ficou no nivel da biblioteca e dos testes da celula. A
topologia de producao, que e outro contrato, nao entrou no aceite.

**Licao.** Sempre que uma outbox nova anuncia tarefa periodica, conferir tres
coisas juntas: o codigo que registra a task, o compose que sobe o worker e o
canario que falha se o processo executor nao estiver vivo.

**Guarda.** `ci/tests/test_canario_fase_3_outbox.py` exige
`identidade-relay`, `run_huey`, `HUEY_REDIS_URL`, `REDIS_STREAMS_URL` e o
workflow fechado que prova o canario F3 na VPS.
