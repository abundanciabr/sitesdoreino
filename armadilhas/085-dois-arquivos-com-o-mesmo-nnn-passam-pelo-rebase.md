# Dois arquivos com o mesmo `NNN` em `armadilhas/` passam pelo rebase sem conflito

**Sintoma:** depois de um `git rebase origin/main` limpo, a pasta tem dois arquivos
com o mesmo número:

```
armadilhas/078-guarda-de-imutabilidade-nao-sobrevive-ao-cascade.md
armadilhas/078-script-injetado-no-container-que-ja-roda-importa.md
```

O git não reclamou de nada, o índice foi regenerado com `exit 0` e **duas linhas
`078`**, e a citação `armadilhas/078` passou a apontar para dois lugares.

**Causa:** a regra "crie `armadilhas/NNN-slug.md`, NNN = próximo número livre"
resolve o conflito de *hunk* (cada sessão escreve num arquivo só seu), mas não
resolve a **escolha do número**: duas sessões que leem a pasta ao mesmo tempo veem
o mesmo "próximo livre". Como os nomes de arquivo são diferentes, o rebase junta os
dois sem nada para mesclar — não existe conflito para o git detectar. Aconteceu em
24/08/2026 (EVO-11), e só foi pego porque alguém listou a pasta com `ls` na mão.

**Aconteceu DUAS vezes no mesmo dia.** O despacho que escreveu esta entrada criou-a
como `083-…`; enquanto ele rodava os testes, outra sessão mergeou
`083-static-404-em-producao-com-todos-os-settings.md` na main. O `git merge
--ff-only origin/main` passou limpo e a pasta ficou com dois `083-`. Dessa vez
ninguém precisou de `ls`: o portão abaixo parou o gerador e disse para qual número
renomear (085). Não é uma armadilha rara — é o que acontece sempre que duas sessões
terminam no mesmo dia.

**Solução (mecanizada em 24/08/2026):** `ci/indice_de_armadilhas.py` agora **para
com ERROR (exit 2)** quando dois arquivos compartilham o mesmo `NNN` — comparando o
número, não o texto, para `78-` e `078-` também colidirem. A mensagem já traz o
`git mv` pronto para o primeiro número acima de todos. O portão roda em três
lugares: ao regenerar, no `--conferir`, e na suíte do testador
(`python ci/ci.py --apenas testador`), que o workflow `muralhas` executa em **todo
PR** — ou seja, a colisão agora deixa o PR vermelho antes do merge.

Se você caiu aqui com o ERROR na tela: renomeie a SUA entrada (a que ainda não está
na `main`) para o número que a mensagem indica e rode
`python ci/indice_de_armadilhas.py`. **Nunca** reaproveite um número vago no meio
(042, 046…): eles estão aposentados e as referências antigas ainda apontam para eles.

**Origem:** despacho de mecanização da numeração (Lei 1 — empurrar a regra escada
acima), a partir da colisão real corrigida no PR #113.
