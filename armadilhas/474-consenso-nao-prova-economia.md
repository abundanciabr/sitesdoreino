---
schema_version: 2
armadilha: 474
estado: sombra
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: "A autenticidade de concordâncias e a qualidade da evidência exigem revisão; o protocolo não implementa controle de acesso."
sinal:
  - "acordo entre IAs apresentado como prova de redução de custo"
gatilho:
  - docs/decisoes/CONSENSO-FASE4.md
licao: "Concordância entre IAs não prova ganho. Fixe revisões e hash da entrada, preserve a medição existente e trate silêncio como ausência, nunca concordância. O editor de documentos não protege gravações concorrentes."
---
# Consenso entre IAs não substitui medição

Em 12/09/2026, o pedido de colaboração na Fase 4 exigiu separar proposta,
acordo sobre experimento e benefício demonstrado. O protocolo existente mede
tempo completo e custos observados; não converte chamadas em dinheiro.

O editor de documentos aceita gravação do corpo inteiro sem controle de
concorrência. Pareceres em comentários separados evitam sobrescrita por
disciplina, mas comentários GitHub continuam editáveis. A decisão final deve
ser versionada, e silêncio de outra sessão não conta como concordância.

Fontes: `services/admin/apps/core/editor_de_documentos.py`,
`docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md` e
`docs/decisoes/CONSENSO-FASE4.md`.
