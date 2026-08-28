# Os checks do PR param de rodar e não há erro nenhum — o PR está em conflito com a `main`

**Sintoma:** você faz `git push`, tudo dá certo, e **nenhum check aparece**.
`gh pr checks <N>` responde `no checks reported on the '<branch>' branch`.
`gh pr view <N> --json statusCheckRollup` vem **vazio**. E não é o GitHub
parado: outros PRs, de outras sessões, ganham runs normalmente no mesmo minuto.

Tudo o que você confere para descartar "o push não chegou" dá certo, o que é
justamente o que faz perder tempo:

```
git ls-remote origin <branch>      → o commit novo está lá
gh pr view <N> --json headRefOid   → o head do PR é o commit novo
git status -sb                     → em sincronia com o remoto
```

**Causa:** o GitHub só emite os eventos `pull_request` (`synchronize`,
`reopened`) depois de conseguir calcular o **merge commit** do PR com a base.
Com conflito, esse merge não existe — e os workflows do PR **não são
disparados, em silêncio**. Não há erro, não há job vermelho, não há
notificação: há a *ausência* de checks, que a esta altura você já leu como
"ainda está na fila".

**O que NÃO resolve** (e cada um custa uma rodada de espera):

- `gh pr close && gh pr reopen` — `reopened` está nos `types` do workflow, mas
  o evento continua sem merge commit para calcular;
- `git commit --allow-empty && git push` — mesmo motivo;
- esperar mais.

**Diagnóstico, em um comando — faça-o PRIMEIRO:**

```bash
gh pr view <N> --json mergeable,mergeStateStatus
```

`mergeable=CONFLICTING`, `mergeStateStatus=DIRTY` fecha o caso. Resolvido o
conflito e feito o push, os checks disparam na hora.

**Por que isto vai pegar toda sessão deste repositório, e não é azar:** desde a
reforma dos painéis, **todo PR relevante regenera `painel/painel.html` e
`painel/livro-202608.js`** ao acrescentar um registro no livro. São arquivos
gerados, grandes e tocados por *todas* as sessões — então basta outra sessão
mergear um registro para o seu PR virar `CONFLICTING`. O conflito nasce em
arquivo que ninguém edita à mão, por trabalho que não é seu, e o primeiro sinal
que você recebe é o silêncio dos checks.

**Cura do conflito, quando ele for só dos gerados:** não resolva à mão —
regenere.

```bash
git rebase origin/main
git checkout --ours painel/painel.html painel/livro-202608.js   # em rebase, "ours" é a main
node painel/gerar_manifesto.js
git add painel/ && git rebase --continue
```

E **confira se o número do seu registro ainda está livre**: a colisão de `NNN`
é a irmã desta armadilha (a outra sessão que provocou o conflito provavelmente
gravou o número que você escolheu). `node painel/gerar_manifesto.js` reprova e
diz o próximo livre — renomeie o arquivo **e** o campo `arquivo`.

**Parente:** `armadilhas/085` (dois arquivos com o mesmo `NNN` passam pelo
rebase sem conflito) descreve a colisão de numeração; esta descreve o silêncio
que a precede.

**Origem:** lote das categorias de usuário, 28/08/2026 — PR da célula `alunos`
(#345). Entre o `git push` do código e o do registro, outra sessão mergeou o
PR #344; gastei um `close/reopen` e um commit vazio antes de perguntar ao
GitHub se o PR era mergeável.
