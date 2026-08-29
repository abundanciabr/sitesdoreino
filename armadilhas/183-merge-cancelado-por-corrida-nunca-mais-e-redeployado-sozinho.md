# 183 — Um merge cujo deploy foi CANCELADO por corrida nunca é redeployado sozinho

**Sintoma:** um PR mergeou, os testes passaram, mas dias (ou minutos) depois a
funcionalidade dele simplesmente não está no ar — sem nenhum run vermelho para
apontar o culpado. `gh run list --workflow=deploy-celula.yml` mostra o run
daquele merge como `conclusion: cancelled`, com `jobs: []` (cancelado antes
até de rodar `detectar`).

**Causa:** `deploy-celula.yml` deriva quais células deployar do diff
`event.before → event.after` **daquele push específico** (job `detectar`).
Quando dois merges chegam perto um do outro (comum neste repositório, com
várias sessões mergeando em paralelo), o `concurrency: cancel-in-progress`
do workflow cancela o run do primeiro merge assim que o segundo chega — e o
run do SEGUNDO merge só enxerga o diff `before→after` **dele próprio**, que
não inclui os arquivos do primeiro. Se os dois merges tocaram células
diferentes (ex.: primeiro mexeu em `services/sugestoes`, segundo só em
`services/admin`), a célula do primeiro fica **sem nenhum run futuro que a
alcance** — ela só seria redeployada por acidente, se uma célula QUALQUER
merge subsequente tocasse os mesmos arquivos.

Isto é primo do que o registro `20260829-111` descreveu (dois deploys do MESMO
merge, um vizinho vermelho barrando o outro) — mas aqui não há vermelho
nenhum: `cancelled` não é `failure`, e nenhum portão hoje distingue "cancelado
por corrida legítima" de "cancelado e a célula ficou órfã".

**Sinal de alerta:** depois de confirmar um merge, `gh run list
--workflow=deploy-celula.yml --limit 10` mostrando `cancelled` na linha
daquele merge — sobretudo se a célula que ele tocava não aparece em nenhum
`deploy (<celula>)` de um run **posterior** e bem-sucedido.

**Solução, medida:** `gh run rerun <id-do-run-cancelado>` funciona — o
GitHub reexecuta o workflow do zero, com o MESMO payload de evento (o mesmo
`before`/`after` daquele push), então `detectar` recalcula o diff certo e a
célula certa entra na matriz de deploy. Não é preciso um novo commit nem
`workflow_dispatch` (que este workflow não tem, de propósito — ver o
comentário no topo do `.github/workflows/deploy-celula.yml`).

**Checklist depois de qualquer sequência de merges rápidos (lote, ou várias
sessões em paralelo):** para CADA merge que tocou `services/**`, confira que
existe um `deploy (<celula>)` com `conclusion: success` cobrindo aquele
commit OU um commit posterior — nunca assuma que "o próximo deploy verde
resolveu", porque só resolve se tocar a MESMA célula.

**Origem:** achado ao verificar (regra do `CLAUDE.md` — "merge confirmado ⇒
conferir o run disparado") os PRs #521/#522/#526 (`DECISAO-arquivar-ideia.md`
e `DECISAO-ocultar-nao-planejado.md`, 29/08/2026): o deploy de `sugestoes`
do PR #526 foi cancelado pela corrida com o merge seguinte, e ficou 15+
minutos sem nenhum run que o alcançasse até este achado.
