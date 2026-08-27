# Crase em `git commit -m "…"` EXECUTA comando, corrompe a mensagem e cria arquivos-lixo

**Sintoma:** você escreve uma mensagem de commit rica, citando arquivos entre
crases como no resto do projeto, e o terminal despeja dezenas de linhas assim:

```
ci/divida_do_livro.py: line 32: CLAUDE.md: command not found
ci/mergear.py: line 31: Upgrade: command not found
ci/divida_do_livro.py: line 32: painel/registros/: Is a directory
/usr/bin/bash: line 1: devedores:: command not found
```

O commit **é criado assim mesmo** — e a mensagem gravada tem buracos onde
estavam as crases, com pedaços de saída de comando enfiados no meio. Um caso
real deste repositório (26/08/2026) gravou o texto de ajuda inteiro do `gh`
dentro da mensagem, no lugar de uma citação a `gh`. E `git status` passa a
mostrar arquivos novos com nomes absurdos:

```
?? ,
?? "c\303\251lula,"
?? "\357\200\252\357\200\252Para"
```

**Causa:** dentro de aspas DUPLAS, o shell faz substituição de comando por
crase — `` `assim` `` é sintaxe de execução, não de citação. A mensagem do
projeto usa crase o tempo todo (é a convenção de Markdown para nome de arquivo),
e num `-m "…"` cada trecho entre crases vira um comando. O que "sobra" na
mensagem é a SAÍDA desses comandos. Os arquivos-lixo nascem de trechos que o
shell leu como redirecionamento (`>`), comuns em texto com tabelas ou setas.

Não é exclusivo de commit: vale para QUALQUER string de várias linhas passada
entre aspas duplas ao shell — `gh pr create --body "…"` cai igual.

**Solução — escreva a mensagem num arquivo e passe por `-F`:**

```bash
git commit -F caminho/para/mensagem.txt
gh pr create --body-file caminho/para/corpo.md
```

Vale o scratchpad da sessão para esses arquivos: eles não pertencem ao
repositório, e criar um `.txt` na raiz para depois esquecer de apagar é a versão
lenta do mesmo problema.

**Alternativa quando a mensagem é curta:** vários `-m`, cada um simples, e
**sem crase nenhuma** — texto puro. Aspas SIMPLES também protegem (`-m '…'`),
mas quebram no primeiro apóstrofo do português (`não é`, `d'água`), então não
são saída confiável aqui.

**Como PERCEBER que aconteceu, se você não viu o despejo:** confira o que ficou
gravado, e não o que você escreveu —

```bash
git log -1 --format=%B
git status --short
```

Mensagem com buraco no lugar de um nome de arquivo, ou `??` com nome estranho,
são a assinatura. O conserto é `git commit --amend -F arquivo.txt` (e, se já
houve push do ramo, `git push --force-with-lease` — **nunca** `--force` seco) e
remover os arquivos-lixo **um a um, pelo nome**: `git clean -f` resolveria, mas
apaga todo não rastreado da árvore, e em pasta compartilhada isso pode levar
junto o trabalho de outra sessão (`armadilhas/135`).

**Por que isto vale uma entrada, e não é "só tomar cuidado":** o commit não
falha. Ele fica verde, com a mensagem estragada — e a mensagem de commit é onde
este projeto guarda o PORQUÊ de cada decisão. Uma mensagem corrompida não dispara
alarme nenhum e só é descoberta meses depois, por quem for entender a decisão e
encontrar texto do `gh` no lugar do argumento.

**Origem:** despacho admin/painel-vivo-atras-da-porta, 26/08/2026, no commit da
dívida do livro (PR #257). Corrigido com `--amend -F` e `--force-with-lease`
antes do PR; três arquivos-lixo removidos pelo nome.
