---
schema_version: 2
armadilha: 188
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: repetir ou nao depende de ancestralidade contra o SHA que a VPS serve, e nada guarda esse SHA hoje (o agente nao tem SSH, Lei 5); mecanizar e a TAR-017 — ensinar ci/rerun_de_deploy.py a tratar 'cancelled' de push medindo a ancestralidade contra o ultimo deploy verde do proprio Actions
sinal:
  - `terminou 'cancelled', não 'failure'`
---

# Deploy de PUSH cancelado pela cadeira musical fica fora do ar em silêncio — e a vacina manda não fazer nada

**Sintoma.** Você mergeia, o `deploy-celula` do seu commit entra como `queued`, e
minutos depois está `cancelled`. Sem log, sem step vermelho. A vacina concorda que
não há nada a fazer:

```
$ python ci/rerun_de_deploy.py --run <id> --so-diagnosticar
NADA: o run <id> terminou 'cancelled', não 'failure' — cancelamento tem causa
própria (veja a armadilhas/173) e não se cura repetindo
```

Você fecha a tarefa. **E o seu merge não está em produção.** O site segue no ar,
servindo a imagem anterior; nada quebra, nada alarma, e ninguém mais vai olhar.

**Causa.** É a `armadilhas/173` — `concurrency: {group: deploy, cancel-in-progress:
false}` guarda **um único run pendente** por grupo, e um deploy novo expulsa o
pendente anterior — mas com um desfecho que a 173 não cobre. Lá o expulso era um
`workflow_dispatch` manual, e a cura é dar grupo próprio ao workflow. **Aqui o
expulso é o deploy de push, que TEM de ficar no grupo `deploy`** — a própria 173
diz isso: "um workflow que de fato mexesse no `docker compose up` deve ficar no
grupo `deploy`". Grupo próprio não é opção, e "não fazer nada" deixa o merge órfão.

O agravante é a paridade de caminhos: se, depois do seu commit, só entrarem merges
que **não** casam com o `paths:` do `deploy-celula` (`services/**`, `painel/**`,
`fila/**`, `documentos/**`) — um PR de `infra/traefik/**` ou de `ci/**`, por
exemplo — **nenhum deploy novo nasce**, e o seu registro fica na `main` sem chegar
ao site indefinidamente.

**Solução: repetir É a cura aqui — depois de provar que não volta nada.** Um rerun
publica o SHA daquele run, não o topo da `main`. Antes de repetir, três medidas:

```bash
DEPLOY=$(gh run list --workflow deploy-celula.yml --branch main --limit 20 \
  --json headSha,conclusion --jq 'map(select(.conclusion=="success"))[0].headSha')
git merge-base --is-ancestor $DEPLOY <seu-sha> && echo "não volta nada"
git rev-list --count <seu-sha>..origin/main   # o que fica de fora
gh run rerun <id>
```

- **O que está publicado é ancestral do seu SHA?** Se sim, republicar só avança.
  Se não, você faria um rollback silencioso — pare e trate o caso à mão.
- **O que o seu SHA deixa de fora** só importa se esses commits tocarem os
  `paths:` do deploy: se tocarem, eles terão o próprio deploy; se não, não há o
  que perder.
- **Nunca repita o run FALHADO de um commit mais velho** para curar o seu: ele
  publica o mundo sem o seu merge.

**Distinção rápida das vizinhas.** `conclusion` decide:

| `conclusion` | Quem é | O que fazer |
|---|---|---|
| `failure` + `i/o timeout` | `armadilhas/127` | `python ci/rerun_de_deploy.py --run <id>` |
| `cancelled` de disparo manual | `armadilhas/173` | grupo de concorrência próprio |
| `cancelled` de push | **esta** | conferir ancestralidade e `gh run rerun` |

**Origem.** 30/08/2026, sessão de "atualize o painel". O deploy do merge do PR 558
foi expulso da vaga de pendente; o do PR 559, logo antes, tinha falhado no timeout
de SSH da `127`. Resultado: a última publicação verde era de 12 minutos antes, e
dois merges estavam na `main` sem estar no ar. Como o meu commit já continha o do
PR 559 e descendia do publicado, um único rerun curou os dois. O buraco da vacina
virou a TAR-017 na fila.
