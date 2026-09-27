---
schema_version: 2
armadilha: 544
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: gerar o brief sempre com python ci/economia_da_fabrica.py brief evita o problema por completo; a ficha ja para e devolve sozinha quando falta o campo, entao nao ha queda silenciosa a guardar
sinal:
  - "herdar modelo caro não é decisão"
gatilho:
  - ".claude/agents/despacho.md"
  - "python ci/economia_da_fabrica.py brief"
licao: "despacho.md exige modelo_recomendado e esforco_recomendado no brief (gerados por ci/economia_da_fabrica.py brief); sem os dois, o subagente para de imediato e devolve sem trabalho. Reincidencia: WHEEL-BASE em 27/09 (devolvido em 42s) e ja em 26/09. Sempre gere o brief com o comando, nunca escreva os campos a mao."
---

# 544: Brief de despacho sem `modelo_recomendado`/`esforco_recomendado` volta sem trabalho

**Data:** 27/09/2026 · **Onde:** frente WHEEL-BASE, obra dos experimentos ·
**Custo evitado:** um turno inteiro de subagente gasto só para descobrir que
o brief estava incompleto (reincidência: já tinha ocorrido em 26/09).

## Sintoma

Um despacho em `opus` recebeu um brief sem os campos `modelo_recomendado` e
`esforco_recomendado` e devolveu à sessão responsável em 42 segundos, sem
tocar em código, citando a exigência de `.claude/agents/despacho.md`.

## Causa

`.claude/agents/despacho.md` (linha 14) declara: "O brief precisa trazer
`modelo_recomendado` e `esforco_recomendado`, gerados por `python
ci/economia_da_fabrica.py brief`; sem isso, pare e devolva à sessão
responsável, porque herdar modelo caro não é decisão." Quem monta o brief à
mão (sem rodar o comando) esquece esses dois campos, e o subagente recusa a
tarefa corretamente, mas o custo do despacho perdido já foi pago. Já
reincidiu: WHEEL-BASE em 27/09/2026 e outra frente em 26/09/2026.

## Solução

Sempre gere o brief com `python ci/economia_da_fabrica.py brief` antes de
despachar qualquer subagente; nunca escreva `modelo_recomendado` ou
`esforco_recomendado` a mão nem omita esses campos por pressa. Confira que
as duas linhas aparecem no texto final do brief antes de disparar o
subagente.

## Evidência

Frente WHEEL-BASE, 27/09/2026 (devolução em 42s); reincidência de 26/09/2026,
mesma causa.
