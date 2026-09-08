---
schema_version: 2
armadilha: 398
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_fichas_de_robo.py
  detector: test_receitas_operacionais_seguem_as_emendas_da_constituicao
sinal: 'receita de agente induz merge reservado'
gatilho:
  - .claude/agents/*
licao: 'Confira as emendas da CONSTITUICAO e o comando real; só a pista mergeia, e a abertura é ci/sessao.py. Cópias locais não rastreadas precisam ser conferidas separadamente.'
---

# 398: Receita antiga induz merge fora da pista

**Data:** 08/09/2026 · **Onde:** operação da Fase 1 · **Custo evitado:** seguir receita recusada pelo próprio portão.

## Sintoma

```text
AssertionError: RUNBOOK-LOTES.md: receita de agente induz merge reservado à pista
2 failed, 7 passed
```

## Causa

A Constituição já atribuía integração à pista, mas a receita ainda mandava a
maestro executar a confirmação de merge. As fichas também reconstruíam à mão
a preparação que `ci/sessao.py` já executava.

## Solução

Aplicar as emendas rastreáveis da Constituição e remeter ao RITOS §1 e §2.
Manter baseline, testes, revisão independente e recibo; testar que a receita
ativa não contém confirmação de merge de agente. O histórico continua
identificado como histórico. Um arquivo local fora do Git não recebe a
correção do PR automaticamente.
