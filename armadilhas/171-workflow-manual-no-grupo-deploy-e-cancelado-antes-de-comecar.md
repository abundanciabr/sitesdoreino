# Workflow manual posto no grupo `deploy` termina `cancelled` em segundos, sem uma linha de log

**Sintoma:** você dispara um `workflow_dispatch` à mão, ele entra como `pending`,
e meio minuto depois está `cancelled`. Não há erro, não há step vermelho, não há
log nenhum — o run nunca começou. `gh run view <id> --log-failed` não tem o que
mostrar, porque não houve falha: houve cancelamento.

A leitura errada e cara é *"deve ter sido um blip do Actions, vou disparar de
novo"* — e o segundo disparo é cancelado igual, pelo mesmo motivo, num dia
movimentado.

**Causa:** `concurrency: { group: deploy, cancel-in-progress: false }`.

O `cancel-in-progress: false` protege o run que **já está rodando** — e é isso, e
só isso, que ele promete. Ele **não** cria uma fila de tamanho ilimitado: o GitHub
guarda **um único run pendente por grupo**, e quando um novo chega, o **pendente
anterior é cancelado** para dar lugar a ele. A documentação chama isso de
"pending run", no singular, e é fácil ler `cancel-in-progress: false` como "nada
é cancelado".

Num repositório onde o grupo `deploy` recebe merge atrás de merge — aqui a `main`
recebe da ordem de 100 entregas por dia —, a vaga de pendente vira uma cadeira
musical. Um disparo manual quase nunca ganha: ele espera um deploy terminar, e
antes disso outro deploy chega e o expulsa.

**Como reconhecer em um comando** (o `conclusion` é a chave — `cancelled` não é
`failure`):

```bash
gh run view <id> --json status,conclusion,createdAt,updatedAt
```

`completed` + `cancelled` + uma diferença de dezenas de segundos entre criação e
atualização, com zero steps executados, fecha o caso.

**Solução: grupo próprio para o workflow manual.**

```yaml
concurrency:
  group: semear-caixa      # não `deploy`
  cancel-in-progress: false
```

O grupo próprio continua impedindo o que precisava ser impedido — duas execuções
do mesmo script ao mesmo tempo — sem pôr o run na fila mais disputada do projeto.

**Antes de sair do grupo compartilhado, pergunte o que ele protegia.** Aqui a
resposta foi "nada que importe": o script roda `docker compose exec` de leitura e
um `manage.py` idempotente — não faz `up -d`, não troca imagem, não toca env. No
pior caso o container reinicia no meio e basta disparar de novo. Um workflow que
de fato mexesse no `docker compose up` (deploy, rollback) **deve** ficar no grupo
`deploy`, e para ele a cadeira musical é o preço certo: melhor um disparo perdido
que dois donos do mesmo comando.

**A regra que fica:** grupo de concorrência compartilhado é para quem disputa o
mesmo recurso de escrita. Workflow manual que só lê, ou que é idempotente, merece
grupo próprio — senão ele é silenciosamente expulso pelo trânsito dos outros.

**Origem:** 29/08/2026, primeira execução real do `semear-caixa.yml` (inaugurar o
quadro da Caixa em produção, pedido `20260827-014` do livro). O run `33266900749`
foi criado às 17:56 e cancelado 31 segundos depois, com o workflow correto e o
script correto — o defeito estava em uma linha de `concurrency` escrita por
analogia com o `rollback.yml`, sem perguntar o que a analogia custava.
**Categoria** (`RETROSPECTIVA-FASE-D`): viabilidade sem ler a config · falso-verde
(um run que não roda não é um run que passou, e também não é um que falhou).
