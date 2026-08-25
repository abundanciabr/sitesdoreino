# `git checkout <commit> -- <arquivos>` esvazia o `git diff` da prova — e o patch de 0 byte aplica ao contrário sem erro

**Sintoma:** você está montando a evidência vermelho→verde da Lei 6 pelo caminho que
a `armadilhas/084` manda (gerar patch, aplicar `-R` para o vermelho, aplicar de novo
para o verde). Desfaz o código com `git checkout origin/main -- <arquivos>`, gera o
patch, roda o vermelho, e depois "restaura" com `git apply -R`. Tudo parece
funcionar: nenhum comando falha, a suíte volta ao verde, `git status` fica limpo.

**O patch tem zero byte.** A restauração não restaurou coisa alguma — o verde voltou
porque o `git apply -R` de um patch vazio é um no-op, e o que estava na árvore já
era o verde... ou não era, e ninguém mediu. A evidência colada no PR descreve uma
prova que não aconteceu.

```
$ git checkout origin/main -- services/celula/app.py
$ git diff --stat            # <- não imprime nada
$ git diff > prova.patch
$ wc -l prova.patch
0 prova.patch                 # <- a prova inteira
$ git apply -R prova.patch    # <- exit 0, sem efeito nenhum
```

**Causa:** `git checkout <commit> -- <caminhos>` **também escreve no ÍNDICE**, não só
na árvore de trabalho — é a diferença entre ele e `git checkout -- <caminhos>` (sem
commit), que só copia do índice para a árvore. Depois dele, índice e árvore estão
IGUAIS, e `git diff` — que por definição compara *árvore contra índice* — não tem o
que mostrar. A mudança existe: ela está em `git diff HEAD` (árvore contra o commit) e
em `git diff --cached` (índice contra o commit). Só o comando que a receita usa é
que não a enxerga.

O modo de falha é o pior possível: **silencioso e verde**. Nenhum comando retorna
erro, o patch é um arquivo válido (vazio é válido), o `git apply -R` sai 0, e o
`git status` limpo no fim é lido como "restaurei tudo" quando significa "nunca mexi
em nada pelo caminho que eu achava".

**Solução — uma das duas, e a conferência que fecha:**

```bash
git checkout origin/main -- <arquivos>
git reset -q                     # desfaz o ÍNDICE, preserva a árvore quebrada
git diff > prova.patch           # agora contém a quebra
wc -l prova.patch                # <- o portão: patch vazio é prova ausente
```

ou, sem mexer no índice:

```bash
git diff HEAD > prova.patch      # árvore contra o commit, índice à parte
```

**Confira o tamanho do patch antes de confiar nele.** É uma linha de comando e é o
que separa "provei" de "achei que provei" — a mesma classe do falso-verde do
`| tail` pendurado no `gh run view` (ARMADILHAS §5.10): comando que sai 0 sem ter
medido nada.

**Parente próxima:** a `armadilhas/084` (gere o patch com `git diff`, nunca com
`git stash` — a pilha é única do repositório e outra sessão pode popar a sua) e o
refinamento registrado em `services/sugestoes/LICOES.md` no EVO-21: `git diff`
captura **tudo** que está sem commit, não só a quebra recém-escrita, por isso o verde
se commita ANTES de gerar o patch (catraca do RITOS §2.1). As três se somam na mesma
receita: *commite o verde · quebre · `git reset` se usou `checkout <commit>` ·
`git diff` · confira o tamanho · rode o vermelho · `git apply -R` · confira
`git diff --stat` vazio E a contagem de testes*.

**Origem:** despacho EVO-31 (`sugestoes`, a faixa de roadmap), 25/08/2026 — pego
por um `ls -la` no patch, feito por desconfiança e não por procedimento.
