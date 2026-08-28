# O espelho recusa atualizar, a sujeira é invisível (`status` acusa, `diff` vem vazio) — e a ferramenta de limpar está trancada de propósito

**Sintoma:** você faz o que a `armadilhas/148` manda — atualizar o clone
principal para parar de ler um mapa velho — e o `git pull --ff-only` é recusado
pela muralha:

```
🧱 MURALHA DA PASTA COMPARTILHADA: recusado `git pull` no clone principal
```

Você não tocou em nada, e mesmo assim `git status --porcelain` acusa um arquivo
rastreado modificado. Aí vem a parte que faz perder rodada: **`git diff` naquele
arquivo vem VAZIO**. Não há o que reverter, e nada indica o que está errado. E o
caminho óbvio de limpar — `git restore` / `git checkout -- <arquivo>` — é
recusado pela mesma muralha, porque é git de estado no espelho.

**Causa — duas travas corretas se somando.** (1) A muralha só libera `switch` e
`pull` no principal **com a árvore limpa** (`armadilhas/135`), e limpar exige
justamente o git que ela recusa ali. (2) No Windows, um arquivo rastreado pode
divergir **só no fim de linha** (LF no disco, CRLF esperado pelo checkout):
`git diff` normaliza e não mostra nada, enquanto `git status` compara bytes e
acusa `M`. Resultado: uma sujeira que não aparece no diff tranca a atualização
do espelho, e o botão de limpeza está trancado por desenho — não por defeito.

No caso medido, a sujeira era um arquivo **gerado que o `origin/main` já tinha
apagado** (`painel/manifesto.js`, removido no PR #331): o espelho tinha parado
num commit onde ele ainda existia, com conteúdo divergente. Ou seja, o espelho
estava travado por causa de um arquivo que nem existe mais no projeto.

**Solução — só leitura de git e shell, sem nenhum git de estado:**

1. **Diagnostique antes de descartar.** `git diff -- <caminho>` vazio + `git
   status` acusando `M` ⇒ é fim de linha (ou cache de `stat` velho), **não**
   conteúdo. Se o diff vier com conteúdo de verdade, PARE: é trabalho de alguém,
   e a resposta é a `armadilhas/137`, não esta.
2. **Copie a sobra para fora antes de qualquer coisa** (`cp <caminho>
   "$SCRATCH/..."`). Custa um comando e devolve o arquivo se o diagnóstico
   estiver errado.
3. **Devolva o arquivo ao estado do commit, por fora do git:**

   ```bash
   git show HEAD:<caminho> > <caminho>      # conteúdo do commit (sai com LF)
   sed -i 's/$/\r/' <caminho>               # devolve o CRLF que o checkout espera
   git status --porcelain                   # tem de ficar só com os não rastreados
   ```

   `git show` é leitura (a muralha libera); a escrita é do shell, que é a
   fronteira honesta que ela não cobre. Não rastreado não suja a árvore para
   este fim — as pastas de trabalho do mantenedor podem ficar.
4. **Agora `git pull --ff-only` passa.** Se o arquivo tiver sido apagado lá na
   frente, **não o apague à mão**: o próprio fast-forward o remove, que é
   exatamente o que se queria.

**A pegadinha do comando composto:** o hook da muralha mede a árvore **antes** de
o comando rodar. Então `rm sobra.js && git pull` é recusado — quando ele mediu, a
árvore ainda estava suja. Limpe numa chamada, atualize na seguinte.

**Por que isto merece entrada própria:** a `148` provou que o espelho velho faz
robô decidir sobre um sistema que não existe mais, e receita "atualize / leia do
`origin/main`". Esta é o degrau seguinte, e é onde a receita trava na prática:
**a atualização recomendada pode ser recusada, com a causa invisível no diff e a
cura aparentemente proibida.** Sem isto escrito, o próximo agente lê a recusa 🧱
como defeito da muralha e ou desiste (fica no mapa velho) ou tenta contornar a
muralha — os dois desfechos ruins.

**Origem:** 28/08/2026, ao atualizar o espelho a pedido do mantenedor depois da
consulta sobre colisões entre robôs (PR #354). O espelho estava **90 merges**
atrás do `origin/main`, travado por um arquivo gerado que o projeto já tinha
apagado. **Categoria** (`RETROSPECTIVA-FASE-D`): sessões paralelas ·
fail-closed na borda.
