---
schema_version: 2
armadilha: 556
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/pr.py
  - ci/fila.py
sinal:
  - "tarefa que nao existe"
guarda:
  tipo: nenhum
  motivo: "ci/pr.py exige --arquivos e so faz git add nos caminhos declarados (linha 763); nao ha portao local que force o autor a lembrar do arquivo da tarefa nova"
licao: "python ci/fila.py criar grava fila/tarefas/NNN-*.json na arvore, mas python ci/pr.py so faz git add nos caminhos passados em --arquivos (obrigatorio, linha 945); esquecer o arquivo da tarefa nesse --arquivos sobe os eventos sem a tarefa e a muralha-da-fila reprova com tarefa que nao existe (PR #2296, TAR-921)."
---

# 556: `ci/pr.py` não embarca sozinho o arquivo da tarefa recém-criada

**Data:** 27/09/2026 · **Onde:** `ci/pr.py`, `ci/fila.py` · **Custo evitado:**
commit extra e novo ciclo de validação para corrigir um PR já aberto.

## Sintoma

```
muralha-da-fila: tarefa que nao existe
```

No PR #2296 (TAR-921), `ci/pr.py --tarefa TAR-921 --arquivos ...` subiu os
eventos da tarefa (`fila/eventos/...TAR-921...json`) sem o arquivo
`fila/tarefas/921-*.json` criado por `python ci/fila.py criar` momentos
antes. A `muralha-da-fila` reprovou porque os eventos referenciam uma tarefa
ausente do commit. Corrigido com um commit extra incluindo o arquivo da
tarefa. Em outros dois PRs do mesmo dia (#2292 TAR-920, #2295 TAR-922) o
arquivo da tarefa foi incluído desde o início e a muralha passou de
primeira.

## Causa

`ci/pr.py` declara `--arquivos` como obrigatório e, na preparação do commit,
só executa `git add -- *pedido.arquivos` (não varre a árvore procurando
arquivos novos fora da lista declarada). `python ci/fila.py criar` grava
`fila/tarefas/NNN-slug.json` no disco, mas não o adiciona ao índice do Git
nem ao pedido do `ci/pr.py`: quem abre o PR precisa lembrar de citar esse
caminho manualmente em `--arquivos`, junto dos arquivos de trabalho e dos
eventos que `ci/pr.py` embarca da tarefa.

## Solução

Ao montar o `--arquivos` de um PR que abre ou fecha uma tarefa nova, inclua
sempre o `fila/tarefas/NNN-*.json` criado por `ci/fila.py criar`, além dos
arquivos de trabalho. Confira com `git status` antes de rodar `ci/pr.py`
que o arquivo da tarefa aparece como novo/staged pretendido; se a
`muralha-da-fila` reprovar com "tarefa que nao existe", o arquivo da tarefa
ficou de fora do `--arquivos` do commit.

## Origem

PR #2296 (TAR-921), corrigido com commit extra; comparado a #2292 (TAR-920)
e #2295 (TAR-922), do mesmo dia, que incluíram o arquivo da tarefa desde o
início.
