# O `cwd` do shell pode resetar entre duas chamadas SEPARADAS da ferramenta Bash — mesmo com worktree fresco

**Sintoma:** igual ao da `armadilhas/140` (`mergear.py --conferir` acusa
dívida do livro já paga, ou qualquer outro comando de `ci/` "esquece" um
arquivo que você tem certeza de ter acabado de criar/commitar) — mas desta
vez você JÁ seguiu a solução de lá: rodou tudo dentro de um worktree recém-
criado a partir de `origin/main`, com `git fetch` e `git rebase` frescos.
Mesmo assim, uma chamada isolada de `python ci/mergear.py <N> --conferir`
(sem `cd` na mesma chamada) devolve um veredito que só faz sentido se tivesse
rodado em outro diretório.

**Causa:** o `cwd` do shell usado pela ferramenta Bash nem sempre persiste
entre duas chamadas SEPARADAS da ferramenta — mesmo quando uma chamada
anterior terminou com um `cd` bem-sucedido para um worktree. Uma chamada que
não leva `cd` explícito pode rodar a partir do diretório de trabalho
ORIGINAL da sessão (aqui, o clone principal espelho), não do worktree onde a
chamada anterior deixou o shell. O sintoma no `mergear.py` é o mesmo da
`armadilhas/140` (lê `painel/registros/*.js` do disco local errado) — a
causa é diferente: lá o worktree em si estava desatualizado; aqui o worktree
estava em dia, mas o COMANDO rodou no lugar errado.

**Como confirmar, na hora:** compare o resultado de uma chamada com `cd`
explícito contra uma sem. Se o veredito mudar, era isto.

**Solução:** trate CADA chamada da ferramenta Bash como se pudesse começar
do zero. Nunca confie em `cd` de uma chamada anterior para uma chamada
seguinte — prefixe TODO comando que precisa rodar dentro de um worktree com
`cd "<caminho-do-worktree>" && ...` na MESMA chamada, do primeiro ao último
comando da sequência. Isto vale em dobro para `ci/mergear.py`, que decide
merge de verdade: um veredito de PASS obtido no diretório errado não é um
PASS que valha confiar.

**Origem:** lote do sininho (Fase 5, o sino do `funil`), 27/08/2026 — dois
`ci/mergear.py --conferir` seguidos no PR #296, o segundo sem `cd`, primeiro
devolveu conflito não-calculado (esperado, `armadilhas/130`), o segundo
devolveu "10 merges sem registro" — todos, na verdade, já citados havia
horas. Comparar com uma chamada de controle (`cd` explícito) confirmou em
segundos. Ver também `armadilhas/135` (por que o clone principal nunca é
bancada) e `armadilhas/140` (o mesmo sintoma, causa irmã).
