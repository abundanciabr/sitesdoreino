---
schema_version: 2
armadilha: 500
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_fila_do_deploy.py
sinal:
  - terminou 'cancelled' sem job nenhum
gatilho:
  - .github/workflows/deploy-celula.yml
  - .github/workflows/deploy-infra.yml
  - .github/workflows/rollback.yml
licao: Grupo de concorrência compartilhado por deploys usa `queue: max`. Sem a chave vale o padrão `queue: single`: a vaga de espera é única e o pendente anterior é cancelado pelo merge seguinte, sem vermelho e sem alarme. Antes de declarar a fila inviável, releia a documentação do `concurrency`: a chave existe desde 07/05/2026.
---

# Grupo de deploy sem `queue: max` guarda uma vaga só, e o pendente anterior morre

Três workflows publicam na VPS pelo mesmo `docker compose` e por isso dividem o
grupo `deploy`: `deploy-celula`, `deploy-infra` e `rollback`. Separar os grupos
foi medido e recusado em 30/08/2026, e a medição continua certa: os dois
scripts que rodam dentro da VPS escrevem no mesmo `docker-compose.yml`.

O que estava errado não era o grupo único, era o padrão dele. Sem a chave
`queue`, o `concurrency` vale `queue: single`: uma vaga de pendente. Quando
dois merges chegavam perto, o que esperava era expulso e terminava
`cancelled`. `cancelled` não é `failure`, então o `alarme-main` não dispara,
nada fica vermelho e nenhuma issue nasce: o merge fica na `main` sem chegar ao
ar. Em 20/09/2026 a linha de base era 5 cancelados em 400 runs.

Desde 07/05/2026 o `concurrency` aceita `queue: max`, que guarda até 100 runs
pendentes no grupo, atendidos em ordem de chegada. Ela é inválida apenas junto
com `cancel-in-progress: true`, combinação que o GitHub recusa na validação do
workflow, ou seja, no ar e não no PR. Os três blocos usam
`cancel-in-progress: false`, então a chave entra sem conflito.

## O que esta entrada encerra, o que continua valendo e o que espera o degrau B

- `173`, `188` e `245` descrevem a expulsão da vaga única. Este degrau encerra
  a causa delas: ninguém mais é expulso por um merge novo.
- `383` continua valendo. Um run cancelado por fila cheia ou à mão segue
  morrendo pendente, sem um único job, e a matrix dele nunca existiu para ser
  lida.
- `183`, `215` e `359` descrevem a decisão pelo diff do push, que a fila não
  toca. Só o degrau B do plano mestre as encerra, recusando publicar célula
  cuja última publicação não é ancestral do run.

## A categoria da retrospectiva

Afirmar inviabilidade sem reler a configuração. O cabeçalho de
`deploy-infra.yml` concluía, em 30/08/2026, que acabar com a expulsão exigiria
fundir as duas esteiras numa só. A conclusão nasceu de uma medição correta
sobre os scripts da VPS e de uma suposição não conferida sobre o que o
`concurrency` aceitava. A chave que resolve o caso em uma linha já existia
havia três meses.

## O preço declarado

Numa rajada de dez merges em dez minutos o último espera perto de trinta
minutos, e run pendente não consome minuto de runner. Fila acima de 100
pendentes cancela quem chega depois, e por isso a issue de
`.github/workflows/vacina-do-deploy.yml` passa a dizer que um `cancelled` tem
duas causas: fila cheia ou cancelamento à mão.

Fontes: `docs/decisoes/PLANO-MESTRE-FILA-DE-DEPLOY.md`, itens 4, 7.1, 7.2 e
7.9, e o changelog do GitHub de 07/05/2026 sobre `concurrency`.
