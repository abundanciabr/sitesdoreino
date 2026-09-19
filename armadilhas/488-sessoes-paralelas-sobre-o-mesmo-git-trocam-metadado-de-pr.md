---
schema_version: 2
armadilha: 488
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/pr.py
  - ci/sessao.py
sinal:
  - "gh pr edit .* --body-file"
  - "PASS PR aberto: #[0-9]+"
guarda:
  tipo: sino
  dono: ci/consultar_armadilhas.py
  detector: gatilho por caminho (ci/pr.py, ci/sessao.py)
licao: "Sub-agentes em paralelo? De NOME UNICO por PR aos arquivos de entrada do ci/pr.py (corpo, mensagem, detalhe, validacao): o scratchpad e COMPARTILHADO entre sessoes irmas e nome generico se sobrescreve entre o commit e o gh pr edit. Duas sessoes chamando ci/pr.py no mesmo segundo sobre o mesmo .git tambem trocam a mensagem do commit. Os arquivos nao se perdem; o metadado mente."
---

# Sessoes paralelas sobre o mesmo `.git` trocam metadado de PR entre si

**Data:** 18/09/2026 · **Onde:** `ci/pr.py`, scratchpad da sessao ·
**Custo evitado:** um PR publicado descrevendo o trabalho de outra tarefa

## Sintoma

Seis sub-agentes foram disparados em paralelo pela mesma sessao, cada um na sua
bancada. Tres deles relataram, de forma independente, o mesmo estrago:

```
o corpo do PR #1727 nasceu com o texto da Frente A (provador/adversario)
o corpo do PR #1728 foi publicado com o texto de outra tarefa
o commit a67cb7e1 contem os quatro arquivos certos, mas carrega a mensagem
  "ci: as fichas do provador e do adversario", citando TAR-472 e TAR-464,
  que nao estao naquele PR
```

Os arquivos entregues estavam corretos em todos os casos. O que mentiu foi o
metadado: corpo do PR e mensagem de commit.

## Causa

Duas causas distintas, que se somam quando ha paralelismo:

1. **O scratchpad e compartilhado entre as sessoes irmas.** Nomes genericos
   (`corpo.md`, `mensagem.txt`, `detalhe.txt`, `validacao.json`) colidem. O
   `ci/pr.py` le a mensagem e o recibo cedo, mas o corpo do PR e enviado depois,
   por `gh pr edit`: na janela entre os dois, a sessao irma sobrescreve o
   arquivo e o corpo publicado e o dela.

2. **O `.git` e o mesmo.** As bancadas sao worktrees do mesmo repositorio. Duas
   sessoes que chamam `ci/pr.py` no mesmo segundo (medido: 19:37:33 nas duas)
   disputam o estado de commit e a mensagem cruza de uma bancada para a outra.

## Solucao

Quem dispara os sub-agentes escreve no brief, e quem executa obedece:

- **Nome unico por PR** nos quatro arquivos de entrada do `ci/pr.py`. Use um
  subdiretorio proprio ou o sufixo da tarefa: `corpo-TAR-471.md`,
  `mensagem-TAR-471.txt`. Nunca a raiz do scratchpad com nome generico.
- **Confira o corpo depois de publicar**, com `gh pr view <N> --json body`. Se
  saiu errado, `gh pr edit <N> --body-file <arquivo com nome unico>` conserta,
  e isso nao reescreve historia.
- **Mensagem de commit trocada NAO se conserta com rebase** quando o recibo do
  livro ja cita aquele SHA nominalmente: o rebase faria o registro apontar para
  um commit inexistente, e registro nao se edita. Declare o fato no relatorio e
  siga; o PR, os arquivos e o recibo continuam corretos.
- Se puder, **escalone as chamadas de `ci/pr.py`** em vez de deixar seis
  sessoes fecharem no mesmo minuto.

## O que NAO e a causa

Nao e o worktree: o isolamento de arvore funcionou, e nenhum agente pisou no
arquivo de outro. Nao e o `ci/pr.py` estar errado: ele le o que esta no caminho
que recebeu. E o caminho que era ambiguo.
