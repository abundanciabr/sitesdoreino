---
schema_version: 2
armadilha: 198
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/mergear.py
sinal:
  - `n[ãa]o reportaram: muralhas`
  - `mergeStateStatus.*DIRTY`
---

# PR com CONFLITO não dispara os workflows de `pull_request` — os checks obrigatórios não ficam pendentes, eles não existem

**Sintoma.** O PR está aberto, o push chegou, e `gh pr checks <N>` lista **um
check só** — nenhum dos obrigatórios:

```
$ gh pr checks 576
conferir o toca declarado   pass   6s   https://github.com/.../runs/...
```

`python ci/mergear.py <N> --conferir` traduz certo, e é ele quem salva:

```
  conflitos              FAIL    o PR conflita com a base
  checks obrigatórios    ERROR   não reportaram: muralhas, ci-celula-gate
```

A leitura natural — *"os runners estão ocupados, já já aparecem"* — está errada:
eles **nunca** vão aparecer. E a espera fica muda esperando um check que não
existe, que é a `armadilhas/161` de novo.

**Causa.** O GitHub monta um **merge ref** (a fusão hipotética do PR com a base)
para rodar workflows de `on: pull_request`. Com o PR em conflito, essa fusão não
existe — e sem ela não há o que fazer checkout, então **nenhum run é criado**.
Não há erro: não há evento.

Os workflows de `pull_request_target` **continuam rodando**, porque eles usam a
definição e o código da **base**, que sempre existe. É essa assimetria que
engana: `conferencia-do-toca` e `pouso` (os dois `pull_request_target` desta
casa) aparecem verdes, e o PR parece vivo enquanto os portões que importam nunca
chegam.

Medido em 30/08/2026 no PR #576: três pushes seguidos, três runs de
`conferencia-do-toca`, **zero** de `muralhas` e `ci-celula`. Um `git merge
origin/main` resolvendo o conflito e um push depois, `mergeable` virou
`MERGEABLE` e os cinco checks nasceram em 33 segundos.

**Solução.** Antes de esperar check nenhum, pergunte se o PR pode ser fundido:

```bash
gh pr view <N> --json mergeable,mergeStateStatus --jq '{mergeable,mergeStateStatus}'
# CONFLICTING / DIRTY  => nenhum workflow de pull_request vai rodar
git fetch origin && git merge origin/main   # resolva, commite, push
```

`python ci/mergear.py <N> --conferir` já faz as duas perguntas na ordem certa —
e é por isso que o veredito de um PR se lê nele, e não em `gh pr checks`, que
mostra o que existe sem dizer o que **deveria** existir. Ausência de evidência
não é evidência de sucesso (INV-CI01).

**De quebra: `ci/esperar.py --checks <PR>` dá falso-verde nesse estado.** Ele
declara "todos os N checks verdes" quando **todos os checks que existem naquele
instante** estão verdes — com um único check nascido, isso é verdade e é inútil:
no PR #576 ele anunciou "todos os 1 checks verdes · levou 0s". A espera está
certa sobre o que mediu; quem decide se aquilo era o suficiente é
`ci/mergear.py --conferir`, que conhece a lista de obrigatórios. Espere o que
quiser, **decida com o portão**.

**Onde este conflito nasce quase sempre nesta casa:** `armadilhas/INDICE.md` e
`armadilhas/GUARDAS.json` são **gerados** e viajam no Git, então dois PRs que
acrescentam entradas colidem sempre — é a `armadilhas/156` (os gerados do
painel) na pasta das armadilhas. Ao resolver, **não edite o conflito**: pegue a
versão da base e regenere.

```bash
git checkout --theirs armadilhas/GUARDAS.json armadilhas/INDICE.md
python ci/indice_de_armadilhas.py
git add -A && git commit --no-edit
```
