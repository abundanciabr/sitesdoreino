# Suas edições sumiram e o `git status` mostra um ramo que você não criou — duas sessões na MESMA pasta

**Sintoma:** no meio do trabalho, `git status` mostra um ramo que você nunca
criou (`agent/<outra-area>/...`) e as modificações que você tinha feito em
arquivos rastreados **não estão mais lá**. Arquivos novos (untracked)
sobrevivem; edições, não. Nenhum erro, nenhum aviso, em lugar nenhum.

**Causa:** duas sessões de agente usando o MESMO diretório — o clone
principal. O `git switch`/`checkout` de uma sessão troca o estado debaixo dos
pés da outra: edições em arquivos rastreados se perdem ou mudam de ramo, e o
ramo "muda sozinho". A lei que impede isso sempre existiu (RITOS.md §1:
worktree por agente), mas era **garantia sem mecanismo**
(RETROSPECTIVA-FASE-D §2) — e em 26/08/2026 custou o retrabalho de uma sessão
inteira da área admin.

**Solução (o mecanismo, desde 26/08/2026): a muralha da pasta compartilhada.**
`ci/muralha_pasta_compartilhada.py`, ligada por hooks do harness em
`.claude/settings.json` (PreToolUse + SessionStart). O clone principal virou
**espelho**: lá a muralha recusa `Edit`/`Write`/`NotebookEdit` e git de estado
(`switch`/`checkout`/`reset`/`rebase`/`merge`/`stash`/`clean`/`commit`/
`cherry-pick`/`revert`/`restore`/`am`/`apply`/`mv`/`rm`/`pull`/`add`), com o
motivo e o rito escritos na própria recusa. Continuam livres no principal:
leituras, `git fetch`, `git worktree`, `gh` — e, com a árvore limpa,
`git switch main` e `git pull` na main (é assim que o espelho se mantém
fresco depois dos merges). Trabalho de verdade acontece em worktree
(RITOS §1); os worktrees do harness em `.claude/worktrees/` também contam —
o `.git` deles é ARQUIVO, e é por isso que a muralha os reconhece como
worktree e não como principal.

**A fronteira honesta (o que a muralha NÃO cobre):** shell que escreve
arquivo no principal sem passar pelo git nem pelas ferramentas de edição
(um `Set-Content`, um `>`). Ela é cerca, não jaula: cobre o caminho por onde
as colisões reais aconteceram. Se um dia houver colisão por fora, a resposta
é alargar a muralha com teste — nunca vigiar no olho.

**Duas notas de implementação que custaram rodada:**

- O PowerShell 5.1 acrescenta **BOM UTF-8** ao canalizar texto para o stdin
  de um processo. Guarda fail-closed que lê JSON do stdin precisa tolerar o
  BOM (`lstrip(chr(0xFEFF))`) — senão toda decisão vinda desse caminho vira
  "PAROU POR SEGURANÇA", inclusive as permissões.
- Teste de hook se escreve contra repositório DESCARTÁVEL com worktrees
  reais (inclusive um dentro de `.claude/worktrees/`, o caso sutil), e a
  suíte tem de ficar vermelha com a muralha sabotada — provado por mutação
  em 26/08/2026: lista de subcomandos esvaziada ⇒ 11 vermelhos
  (`armadilhas/132`).

**Origem:** colisão real entre duas sessões no clone principal em 26/08/2026 —
a sessão do sininho trocou o ramo e apagou as edições da sessão do painel
admin. No mesmo dia, uma segunda sessão perdeu edições em SEIS
arquivos rastreados com um `git checkout -- .` no clone principal, com duas
frentes misturadas na mesma árvore — dois casos em um dia, mesmo mecanismo
(relato direto da sessão atingida). **Categoria** (`RETROSPECTIVA-FASE-D`): garantia sem mecanismo ·
sessões paralelas.
