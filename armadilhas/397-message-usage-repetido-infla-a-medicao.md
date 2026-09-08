---
schema_version: 2
armadilha: 397
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a contagem acontece em análises locais, fora do produto e do CI, e não produz erro de execução para uma guarda detectar. A proteção é declarar a chave, a regra de consolidação e os limites da conclusão em cada medição
---

# 397 — Registro parcial de `message.usage` não é chamada nova

**Data:** 07/09/2026 · **Onde:** análise de eventos JSONL · **Custo evitado:** atribuir duas chamadas a uma mensagem registrada mais de uma vez.

## Sintoma

Um relatório soma cada ocorrência de `message.usage` como uma chamada independente. O total cresce quando a mesma mensagem reaparece em outro evento ou quando um registro posterior completa campos que estavam parciais. A conta termina sem erro, com um número plausível e inflado.

## Causa

No schema conferido, os registros repetidos carregam estados parciais ou cumulativos da mesma mensagem, não deltas independentes. O uso pertence à mensagem, não à linha que voltou a carregá-la. Descartar apenas a segunda ocorrência também perde dados quando ela completa campos. Somar toda entrada num campo único esconde se ela veio de entrada nova, criação de cache ou leitura de cache.

## Solução

Depois de confirmar essa semântica no schema da fonte, use `(message.id, message.model)` como chave. Para cada chave, conserve o maior valor observado em cada campo e agregue separadamente `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens` e `output_tokens`.

Exemplo sintético: duas linhas com a chave `(msg-exemplo, modelo-x)` trazem `input_tokens=10` e `cache_read_input_tokens=90`; a segunda completa `output_tokens=5`. Somar linhas daria 205 tokens. Consolidar o máximo de cada campo descreve uma mensagem com 105.

Declare o limite da prova junto do resultado. Esses campos permitem medir tokens registrados e sua composição. Sozinhos, não demonstram percentual da cota do plano, cobrança ou dinheiro gasto. Não publique o conteúdo dos transcripts, nomes de sessão ou segredos para sustentar a conta.

Esse método não vale para uma fonte que declare cada linha como delta independente. Nesse contrato, os deltas precisam ser somados conforme a documentação do provedor.
