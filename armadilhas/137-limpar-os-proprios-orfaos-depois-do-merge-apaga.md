# Limpar os próprios "órfãos" depois do merge apaga arquivo RASTREADO e suja o espelho

**Sintoma:** você migrou para worktree no meio do trabalho (`armadilhas/135`) e
deixou arquivos não rastreados para trás no clone principal. Horas depois, com o
trabalho já mergeado, você "limpa a sujeira" apagando aqueles arquivos do disco —
e o clone principal fica com **deleções pendentes**, a muralha da pasta
compartilhada passa a recusar até o `git pull` lá (árvore suja, corretamente), e
alguém precisa restaurar tudo.

**Causa:** eles deixaram de ser órfãos no instante em que o PR mergeou. Antes do
merge eram `??` (não rastreados) no clone principal; depois do merge — e depois
de o clone principal voltar para `main` e dar `pull` — o MESMO caminho passou a
ser conteúdo rastreado da `main`. Apagar do disco não é mais "limpar lixo": é
`git rm` sem o git.

**A parte cruel: a conferência que parece prudente é a que engana.** Antes de
apagar, o certo é conferir se há conteúdo único a perder — e o resultado foi:

```
IDENTICO ao mergeado : services/admin/apps/core/painel.py
IDENTICO ao mergeado : services/admin/apps/core/templates/admin/painel_ausente.html
IDENTICO ao mergeado : services/admin/tests/test_painel_vivo.py
```

Isso foi lido como *"são cópias descartáveis, pode apagar"*. É o contrário:
**idêntico ao mergeado significa que são os arquivos do repositório.** A prova de
que era seguro apagar era exatamente a prova de que não era.

**O que fazer em vez disso:** não apague nada por caminho de disco. Pergunte ao
git — de dentro de um worktree, nunca redirecionando para o clone principal:

```bash
git ls-files <caminho>      # imprime algo => é RASTREADO, não encoste
git status --short          # ?? => não rastreado; ' D' => você já apagou rastreado
```

Se `git ls-files` imprime o caminho, o arquivo pertence à `main` e a "limpeza"
correta é **nenhuma**. Órfão de verdade é só o que continua `??` depois de o
trabalho ter mergeado — e, mesmo esse, some sozinho quando o dono do clone
principal o devolve para `main`.

**A falha de processo por trás, que é a lição maior:** a exclusão foi feita num
diretório cujo estado de git era **impossível de inspecionar dali**. A tentativa
de rodar `git status --git-dir=<clone principal>` de dentro do worktree foi
recusada pelo harness (corretamente — é a muralha do `armadilhas/135` fazendo o
trabalho dela). O erro não foi apagar: foi **apagar mesmo assim**, sem conseguir
medir. Ausência de medição não autoriza ação destrutiva; ela a proíbe. Quando o
estado não é observável de onde você está, o dono daquele diretório é quem age —
peça a ele.

**Se acontecer:** o conserto é restaurar do próprio git, não reescrever os
arquivos à mão — `git restore <caminhos>` a partir de um worktree do mesmo
commit, conferindo byte a byte depois. Reescrever à mão introduz diferença de
fim de linha e faz o espelho continuar sujo.

**Origem:** despacho admin/painel-vivo-atras-da-porta, 26/08/2026. Os três
arquivos eram de `services/admin`, mergeados pelo PR #249; apagados algumas horas
depois "para ativar a muralha", e restaurados pela sessão vizinha, que percebeu o
espelho sujo. Ver `armadilhas/135` (a muralha e a migração para worktree que
criou os órfãos) e `armadilhas/136` (outro tropeço do mesmo despacho).
