schema_version: 2
armadilha: 424
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: docs/decisoes/RELATORIO-FASE4-MEDICAO.md
  detector: revisão manual do estado da auditoria após o merge
sinal: 'a fila marca a auditoria concluída, mas o relatório continua dizendo que ela está pendente'
gatilho:
  - docs/decisoes/RELATORIO-FASE4-MEDICAO.md
  - docs/decisoes/AUDITORIA-INDEPENDENTE-FASE4-20260908.md
  - fila/eventos
licao: 'Depois de uma auditoria incorporada, o relatório da medição precisa atualizar o estado da auditoria, a evidência do PR e o próximo reteste; estado pendente antigo contradiz a prova publicada e pode esconder que os bloqueios reais são amostra, qualidade, custo e publicação.'
---

# 424: Auditoria concluída não pode deixar relatório stale

**Data:** 08/09/2026. **Onde:** fechamento da auditoria independente da Fase 4.

## Sintoma e causa

O PR #1420 incorporou um parecer independente válido, mas o relatório da Fase 4
continuava afirmando que TAR-281 estava bloqueada e que a auditoria ainda não
existia. O parecer e o relatório passaram a divergir porque o relatório não foi
revisado no mesmo ciclo da auditoria.

## Solução

O relatório agora aponta o parecer e o deploy, marca F4-11 como atendido para a
entrada atual, preserva os bloqueios de amostra, qualidade, custo e publicação,
e exige nova auditoria quando entrarem observações reais novas.

## Evidência

`gh pr view 1420` mostrou `MERGED` com checks verdes. `gh run view 34283078065
--json status,conclusion,headSha,url` retornou `completed/success` no SHA do
merge. A fila marcou TAR-281 como concluída.
