# O `../` no comando escolhe QUAL cópia do repositório o portão vai medir

> Irmã da `armadilhas/140`, com gatilho diferente e cura diferente. Lá, o
> comando roda **do** checkout atrasado. Aqui, você está num worktree **em dia**
> e mesmo assim mede outra árvore — porque o caminho que você digitou aponta
> para lá.

**Sintoma:** você acabou de criar o worktree a partir de `origin/main`, o livro
está em dia, e o portão acusa um absurdo:

```
dívida do livro       FAIL   31 merge(s) sem registro
  #328  2026-08-27  fix(notificacoes): quitar a dívida do backfill
  #326  2026-08-27  docs: fechamento do plano-mestre do sininho
  #323  2026-08-27  painel: o livro chega em UM pedido
  …
```

Você confere à mão e os registros **citam** esses PRs. A `armadilhas/140` diz
"rode de um worktree em dia" — e você está num.

**Causa:** o comando foi este, de dentro do worktree:

```bash
python ../sitesdoreino/ci/mergear.py 331 --conferir     # ERRADO
```

`ci/mergear.py` e `ci/divida_do_livro.py` descobrem a raiz a partir da
**localização do próprio arquivo** (`Path(__file__).resolve().parents[1]`), não
do diretório de trabalho. Isso está certo — é o que os faz funcionar chamados de
qualquer subpasta. A consequência é que **o caminho digitado escolhe o
repositório medido**: apontando para o `ci/` do clone principal, ele leu o
`painel/registros/` do clone principal.

Estar no worktree certo não protege. O que decide é de onde o `.py` foi lido.

**Solução:** chame sempre a ferramenta **do checkout onde você está**:

```bash
cd /caminho/do/seu/worktree
python ci/mergear.py 331 --conferir                     # CERTO
```

Nunca `../outra-arvore/ci/...`. Se precisar rodar de uma subpasta, suba antes.

**Como saber em 10 segundos se é ISTO:** o número acusado é grande demais e
inclui PRs que você sabe que foram registrados. Dentro do seu worktree:

```bash
grep -o "pull/[0-9]*" painel/registros/*.js | sort -u | tail
```

Se os PRs acusados aparecem aí, o problema é de onde a ferramenta foi lida — não
do livro.

**Custo real:** 27/08/2026, mergeando o PR #331. A dívida verdadeira eram **2**
merges (#312 e #314); a leitura do clone principal — 152 commits atrás —
inventou **31**. Custou um ciclo de investigação.

**O modo de falha perigoso é o inverso, e vale mais que o susto:** rodar do
checkout velho e receber um **PASS** que não vale nada, mergeando com dívida real
por baixo. O susto se investiga; o falso verde, não.

**Regra em uma frase:** *ferramenta de repositório mede o repositório de onde ela
é lida, não aquele onde você está.*
