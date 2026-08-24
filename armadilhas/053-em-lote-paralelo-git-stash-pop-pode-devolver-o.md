<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.1.1  ·  referencias antigas "ARMADILHAS §6.1.1" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.1.1 Em LOTE paralelo, `git stash pop` pode devolver o stash de OUTRO agente

**Sintoma:** o `git stash pop` do protocolo acima devolve arquivos de OUTRA
célula (e o seu trabalho "some"), sem erro nenhum. Medido em 22/08/2026, no
primeiro lote paralelo: a pilha de stash é ÚNICA por repositório — todos os
worktrees a compartilham. Duas sessões usando §6.1 ao mesmo tempo intercalam
push/pop: cada uma popou o stash da outra (o trabalho de checkout apareceu
não-commitado no worktree do quiz, e vice-versa).
**Causa:** `git stash` guarda na ref global `refs/stash`, não por worktree nem
por branch. `pop` sem argumento pega o topo da pilha, seja de quem for.
**Solução:** em lote, NÃO use stash para o vermelho→verde — use patch, que é
local ao worktree por construção:

```bash
git diff -- <arquivo-do-fix> > "$SCRATCH/fix.patch"   # guarda o fix
git checkout -- <arquivo-do-fix>                       # tira o fix
python -m pytest tests/test_x.py -q                    # VERMELHO
git apply "$SCRATCH/fix.patch"                         # devolve o fix
python -m pytest tests/test_x.py -q                    # VERDE
```

Se precisar mesmo de stash, sempre por ref explícita (`git stash pop
'stash@{N}'` depois de conferir `git stash list`) — nunca `pop` seco. E se
popar o stash alheio por engano: devolva-o à pilha imediatamente
(`git stash push -m "RESGATE ..." -- <caminhos-da-outra-celula>`) antes de
qualquer outra coisa — o conteúdo é do outro agente, não seu.
**Origem:** lote de 22/08/2026 — corrida de stash entre as sessões checkout e
quiz; os dois conteúdos foram recuperados íntegros.
