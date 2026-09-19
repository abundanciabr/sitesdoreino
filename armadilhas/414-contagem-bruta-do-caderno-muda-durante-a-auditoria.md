---
schema_version: 2
armadilha: 414
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/analise_fase4.py
  - ci/telemetria.py
guarda:
  tipo: nenhum
  motivo: a auditoria registrou a distinção; não alterou o contrato do caderno
sinal: 'a contagem total do caderno muda entre duas análises da mesma entrada'
licao: 'Comandos de auditoria também registram fases no caderno privado. Fixe revisão, hash da entrada e conjunto de eventos tarefa_medida; a contagem total inclui histórico novo e não identifica a amostra.'
---

# 414: A contagem bruta do caderno muda durante a auditoria

## Sintoma

Duas execuções de `python ci/analise_fase4.py --local` podem mostrar números
totais diferentes de registros e arquivos, mesmo quando a amostra operacional
não mudou.

## Causa

Os comandos da própria auditoria registram fases operacionais no caderno
privado. A leitura total inclui esses eventos históricos, enquanto a entrada
da Fase 4 usa somente registros `tarefa_medida` válidos.

## Lição

O parecer deve fixar a revisão do analisador, o hash da entrada válida e os
eventos autorizados. Contagem bruta do caderno é contexto móvel, não identidade
da amostra.

## Evidência

Na auditoria da TAR-281, o hash válido permaneceu
`44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c` enquanto a
quantidade total de eventos cresceu durante os retestes. Não houve novo registro
`tarefa_medida` real.
