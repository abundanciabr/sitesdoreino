---
schema_version: 2
armadilha: 542
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o rito ainda nao distingue citacao textual de declaracao real de qual tarefa o PR fecha; a correcao esta em curso no PR #2238, ainda nao integrado
sinal:
  - "nunca acessa pedido.detalhe"
gatilho:
  - "ci/pr.py"
licao: "A 526 diz que ci/pr.py deduz do --titulo ou --detalhe; o codigo (_identificar_tarefa) nunca le --detalhe. So cai em tarefas_citadas sem TAR propria: `ramo + titulo`, depois --corpo-arquivo (corpo do PR). Cite outra TAR sem prefixo tambem no corpo. PR #2238 (aberto) propoe corrigir; confira gh pr view 2238 --json state."
---

# 542: A 526 erra o campo — a dedução de tarefa lê o corpo do PR, não o detalhe

**Data:** 27/09/2026 · **Onde:** `ci/pr.py`, função `_identificar_tarefa` ·
**Custo evitado:** confiar que citar uma TAR alheia só no campo `--detalhe`
era seguro, quando na verdade o texto perigoso é o `--corpo-arquivo`.

## Sintoma

`armadilhas/526` afirma: "`ci/pr.py` identifica qualquer TAR-N no --titulo ou
no --detalhe". Ao ler o código de `_identificar_tarefa` em 27/09/2026, esse
não é o comportamento: a função nunca acessa `pedido.detalhe` para deduzir
tarefa.

## Causa

`_identificar_tarefa` (ci/pr.py) só recorre a `tarefas_citadas(...)` quando a
sessão não tem nenhuma TAR própria (nem `--tarefa`, nem tarefa da abertura,
nem tarefa cujo `quem == ramo`). Nesse caso, ela procura `TAR-\d+` em duas
fontes, nesta ordem: `ramo + " " + pedido.titulo`, e se ainda vazio, o
conteúdo de `pedido.corpo_arquivo.read_text(...)` — o arquivo passado em
`--corpo-arquivo`, que vira o corpo/descrição do PR no GitHub. `--detalhe`
(o campo que vira o registro do livro) nunca entra nessa busca.

## Solução

Ao citar outra tarefa por número, evite o prefixo `TAR-` tanto no `--titulo`
quanto no `--corpo-arquivo` (o corpo do PR), não só no `--detalhe`: é o corpo
que o rito lê. Quando o PR realmente fecha uma tarefa, passe sempre
`--tarefa TAR-N` explicitamente, que é a única fonte confiável. A correção
estrutural (usar só `--tarefa` e conferir `depende_de`) está proposta no PR
#2238, ainda **aberto** em 27/09/2026 — confira o estado atual com
`gh pr view 2238 --json state` antes de supor que o comportamento mudou.

## Evidência

`ci/pr.py`, função `_identificar_tarefa`, leitura em 27/09/2026; PR #2238
(estado OPEN na mesma data); corrige `armadilhas/526`.
