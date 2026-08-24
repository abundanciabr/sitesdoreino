<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §8 — Ferramentas do agente (o harness também tem armadilha)
     ID historico: §8.1  ·  referencias antigas "ARMADILHAS §8.1" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 8.1 Agente delegado nasce num worktree diferente do que o despacho manda

**Sintoma:** as ferramentas de edição recusam mecanicamente qualquer caminho fora de
um worktree que o despacho nunca mencionou (`.claude/worktrees/agent-<id>`), inclusive
operações git contra o worktree que é claramente o alvo legítimo.
**Causa:** um agente disparado com `isolation: worktree` recebe um worktree **próprio**
criado pelo harness, e as ferramentas ficam confinadas a ele.
**Solução que funcionou:** não lute contra a ferramenta. Como os dois worktrees nascem
do mesmo commit, desenvolva e teste no worktree do agente e, no fim, copie os arquivos
prontos para o worktree do despacho (a ferramenta PowerShell não tem a mesma trava de
caminho), onde acontecem commit/push/PR.
**Melhor ainda:** se o despacho nomeia um worktree, dispare o agente **sem**
`isolation: worktree` — deixe-o criar o worktree do jeito que o RITOS §1 manda.
**Origem:** Prompt 3b (pagamentos, PR #19).
