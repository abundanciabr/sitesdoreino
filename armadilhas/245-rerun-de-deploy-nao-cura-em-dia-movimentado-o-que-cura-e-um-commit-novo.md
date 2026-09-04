---
schema_version: 2
armadilha: 245
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão consegue medir "o repositório está movimentado agora"; o que existe é a decisão de quem está na frente, e ela precisa da regra escrita — a 127 e a 188 mandam repetir, e é essa instrução que precisa do complemento
sinal:
  - 'run_attempt.*[3-9]'
---

# `rerun` de deploy não cura em dia movimentado: o que cura é um commit novo

**Sintoma.** O `deploy-infra` (ou `deploy-celula`) do seu merge falhou, você segue
a receita da `armadilhas/127` (i/o timeout com a VPS viva) ou da `armadilhas/188`
(cancelado pela cadeira musical) e pede `gh run rerun`. O run volta como
`pending`, fica alguns segundos e morre `cancelled`. Você repete. Morre de novo.
Na terceira, a conta de tentativas do run já está em 4 e nada chegou à produção.

**Causa.** O rerun reexecuta o run daquele SHA, e o `concurrency` do workflow
cancela qualquer execução de deploy que não seja a do topo da `main`. Enquanto
outros PRs continuarem pousando, todo rerun do seu SHA nasce velho e é morto
antes de rodar. Não é a rede, não é a VPS: é a fila.

As duas armadilhas vizinhas mandam repetir, e estão certas **no cenário delas**
(o repositório parado, ou com um merge de vez em quando). Este arquivo é o
complemento para o outro cenário, que na prática é o do lote: em 31/08/2026 o
repositório recebia um merge a cada poucos minutos.

**Solução: um commit NOVO que toque os `paths:` do deploy.** Ele cria uma
execução própria, com o topo da `main` dentro — que é o que você queria publicar
de qualquer forma. Não precisa ser um commit vazio: aproveite para escrever, ao
lado da peça afetada, por que aquele deploy custou duas voltas. Foi o que curou
o `gamificacao-consumer` (PR #730), e aplicou **na primeira** das três tentativas
internas.

```bash
# depois de duas tentativas de rerun morrerem em `cancelled`:
git worktree add ../wt-forcar -b agent/infra/forcar origin/main
# edite infra/docker-compose.yml (um comentário útil basta) e abra o PR
```

**Como distinguir dos vizinhos, em uma consulta:**

```bash
gh api "repos/<owner>/<repo>/actions/workflows/<wf>.yml/runs?per_page=1" \
  --jq '.workflow_runs[] | "\(.status)/\(.conclusion) tentativa=\(.run_attempt)"'
```

| o que você vê | quem é | o que fazer |
|---|---|---|
| `failure` + `i/o timeout`, VPS viva | `armadilhas/127` | rerun (funciona se o repo estiver calmo) |
| `cancelled`, um rerun só | `armadilhas/188` | rerun, com as três medidas de lá |
| `cancelled` em DOIS ou mais reruns seguidos | **esta** | commit novo tocando `paths:` |

**A regra de parada continua valendo, e ganha um segundo andar.** A 127 diz:
três reruns vermelhos, pare e registre a pendência no livro. Acrescente: se os
reruns morrem `cancelled` em vez de `failure`, não gaste os três — o segundo já
prova que é a fila, e o commit novo é mais barato que o terceiro.

**O que salvou a verdade no caminho.** O passo
`A infraestrutura foi mesmo sincronizada? (verde sem ter trocado nada é o pior
verde)` reprovou os runs em que a VPS não executou linha nenhuma, com a frase
que importa: *"nada foi trocado, a plataforma segue no ar, mas o que foi
mergeado NÃO está em produção"*. Sem ele, três reruns cancelados teriam passado
por deploy feito, e a descoberta viria semanas depois, pelo sintoma errado.

**Origem:** 31/08/2026, TAR-067/075 (a gamificação indo ao ar). O
`gamificacao-consumer` entrou no compose no PR #719 e ficou fora da VPS por
quatro tentativas: uma cancelada pela cadeira musical, uma vermelha com
`dial tcp ***:22: i/o timeout`, duas canceladas em rerun. O PR #730, um commit
que tocou `infra/docker-compose.yml` de propósito, resolveu de primeira.
