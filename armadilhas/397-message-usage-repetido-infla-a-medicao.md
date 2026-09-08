---
schema_version: 2
armadilha: 397
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - .claude/agents/
licao: Ao medir `message.usage`, deduplique por `(message.id, message.model)`, conserve o maior valor de cada campo e some separadamente `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens` e `output_tokens`. Tokens medem uso registrado, não percentual de cota nem dinheiro.
guarda:
  tipo: nenhum
  motivo: a contagem acontece em análises locais, fora do produto e do CI, e não produz erro de execução para uma guarda detectar. A proteção é declarar a chave, a regra de consolidação e os limites da conclusão em cada medição
---

# 397 — `message.usage` repetido infla a medição sem produzir erro

**Data:** 07/09/2026 · **Onde:** transcripts JSONL de sessões · **Custo evitado:** atribuir consumo a trabalho que apareceu duas vezes na fonte.

## Sintoma

Na janela UTC de 5 a 6 de setembro de 2026, 621 arquivos JSONL ligados apenas ao projeto `sitesdoreino` continham 31.220 linhas com `message.usage`. Havia 17.139 identificadores únicos: 45,1% das linhas eram repetições. Somar as linhas diretamente superestima o uso registrado sem avisar.

## Causa

A mesma mensagem pode aparecer mais de uma vez nos eventos e arquivos da sessão. O uso pertence à mensagem, não à linha que voltou a carregá-la. Além disso, juntar toda entrada num número só esconde a composição: depois da deduplicação, `cache_read_input_tokens` respondeu por 98,42% da entrada medida.

## Solução

Use `(message.id, message.model)` como chave. Para cada chave, conserve o maior valor observado em cada campo e agregue separadamente `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens` e `output_tokens`.

Declare o limite da prova junto do resultado. Esses campos permitem medir tokens registrados e sua composição. Sozinhos, não demonstram percentual da cota do plano, cobrança ou dinheiro gasto. Não publique o conteúdo dos transcripts, nomes de sessão ou segredos para sustentar a conta.
