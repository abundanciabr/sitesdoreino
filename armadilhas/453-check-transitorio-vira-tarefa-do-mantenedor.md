---
schema_version: 2
armadilha: 453
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: .github/workflows/muralhas.yml
  detector: painel_no_navegador
sinal: 'falha transitória de dependência externa chega ao mantenedor como pedido manual de reexecução'
gatilho:
  - .github/workflows/muralhas.yml
licao: 'Checks com instalação de dependência externa devem repetir automaticamente falhas transitórias no próprio runner, limpar o cache temporário quando necessário e só reprovar após o limite.'
---

# 453: Check transitório vira tarefa do mantenedor

**Data:** 09/09/2026. **Onde:** instalação do navegador no CI.

## Sintoma e causa

Uma inconsistência temporária no índice do Google Chrome reprovou o check e
fez o mantenedor receber a instrução de clicar em reexecutar.

## Regra

O workflow tenta novamente de forma automática e limpa os índices APT entre as
tentativas. Só uma falha persistente chega ao mantenedor, com causa técnica.
