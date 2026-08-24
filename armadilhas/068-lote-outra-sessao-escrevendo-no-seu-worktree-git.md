<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §7 — Coordenação (humano, painéis, outros agentes)
     ID historico: §7.7  ·  referencias antigas "ARMADILHAS §7.7" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 7.7 LOTE: outra sessão escrevendo no SEU worktree — `git stash pop` devolve o arquivo SEM a sua edição

**Sintoma:** durante um lote paralelo, `git status` no seu worktree mostra arquivos
de OUTRA célula modificados (que você nunca tocou); e um `git stash push -- <arq>` /
`git stash pop` seu, usado para a evidência vermelho→verde (§6.1), termina "com
sucesso" (`Dropped refs/stash@{0}`) mas o arquivo volta **sem a sua edição** — ela
simplesmente evapora, sem erro nenhum.
**Causa:** duas sessões operando no MESMO diretório de worktree. A pilha de stash é
uma só por worktree: se a outra sessão empilha/desempilha entre o seu `push` e o seu
`pop`, o `stash@{0}` que você desempilha pode ser o dela (foi assim que arquivos de
checkout "apareceram" aqui), e o seu se perde na corrida. Nada valida que o stash
desempilhado é o que você empilhou.
**Solução:** (1) **commite cedo e commite para proteger** — arquivo commitado no seu
branch sobrevive a qualquer corrida; a evidência vermelha via stash deve ser feita
o mais perto possível do commit, conferindo `git stash list` antes e depois;
(2) antes de qualquer stash/rebase, `git status --porcelain` — arquivo alheio
modificado no seu worktree é sinal de colisão: **não** o commite, **não** o
descarte (é trabalho de outra sessão), siga com `git add` só dos SEUS caminhos e
`git rebase --autostash`, e **reporte a colisão no relatório final** para a
sessão-maestro resolver quem está no worktree errado; (3) se a sua edição sumiu,
reaplique-a do contexto/histórico da conversa — o Edit da ferramenta não deixa
reflog, mas o conteúdo está na sessão.
**Origem:** despacho quiz/relay-outbox (lote de 22/08/2026) — o `on_commit` de
`views.py` evaporou num stash pop; arquivos da célula checkout apareceram
modificados no worktree wt-quiz-relay, que era exclusivo do quiz.
