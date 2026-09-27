---
schema_version: 2
armadilha: 531
estado: documentada
degrau: 2
confianca: media
custo_por_queda: medio
gatilho:
  - ci/pr.py
sinal:
  - "Subsystem for Linux"
guarda:
  tipo: nenhum
  motivo: "o validacao.json e escrito por quem chama ci/pr.py; um portao generico nao sabe qual bash a celula quer (Git Bash, WSL de verdade, MSYS2), entao nao ha como o rito escolher por conta propria"
licao: "ci/pr.py roda cada comando do validacao.json sem shell, pelo primeiro elemento literal. No Windows, declarar so \"bash\" resolve pelo PATH para C:/Windows/System32/bash.exe, o lancador do WSL (nao o Git Bash), que falha ou abre um subsistema errado quando nao ha distribuicao Linux instalada. Declare o caminho absoluto do bash pretendido, por exemplo C:/Program Files/Git/bin/bash.exe."
---

# 531: `"bash"` genérico no `validacao.json` chama o stub do WSL, não o Git Bash

**Data:** 26 e 27/09/2026 · **Onde:** validação local do `ci/pr.py`, obra
Appmax, mesma máquina Windows do armadilhas/528 · **Custo evitado:**
validação travada ou falhando por rodar o subsistema errado, achando que o
script de teste está quebrado.

## Sintoma

Um comando de `validacao.json` cujo primeiro elemento é só `"bash"` (sem
caminho) não roda o Git Bash instalado em `C:/Program Files/Git/bin/`.
No Windows, `bash` no `PATH` costuma resolver primeiro para
`C:/Windows/System32/bash.exe`, que é apenas o lançador do WSL (Windows
Subsystem for Linux). Numa máquina sem distribuição Linux instalada ou
iniciada, esse lançador não executa o script pretendido: ou recusa, ou
espera por um subsistema que não existe, produzindo mensagem própria do WSL
em vez do resultado do script.

## Causa

`ci/pr.py` executa cada comando do `validacao.json` como subprocesso direto
(sem `shell=True`), então o primeiro elemento é resolvido pelo `PATH` do
sistema operacional, exatamente como o `armadilhas/528` já documentou para
`"python"`. A mesma causa alcança qualquer executável citado sem caminho: no
Windows, `System32` costuma vir à frente do `PATH` do Git Bash no `PATH` do
usuário, e `bash.exe` de lá é o stub do WSL, não o interpretador que a
célula espera.

## Solução

Declare o caminho absoluto do Git Bash como primeiro elemento de cada
comando que precise de `bash`, por exemplo:

```json
["C:/Program Files/Git/bin/bash.exe", "-c", "..."]
```

Isso vale junto com a lição do `armadilhas/528` (Python do venv por caminho
absoluto): todo `validacao.json` novo declara o executável, nunca o nome
genérico, para os dois interpretadores.

## Origem

Obra Appmax, sessões de coordenação de 26 e 27/09/2026, mesma máquina
Windows do `armadilhas/528`.
