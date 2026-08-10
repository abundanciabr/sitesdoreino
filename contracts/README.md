# Contratos — a Muralha nº 4

Os arquivos desta pasta são **a fronteira oficial entre células**. Depois de ratificados
(Portão do brief da Fase 0), eles congelam:

1. **Nenhum agente altera `contracts/`** em sessão normal. Mudança = Rito de Contrato
   (RITOS.md §3): PR contendo SÓ `contracts/`, label `contrato`, aprovação do mantenedor
   (CODEOWNERS), provedor implementa primeiro com retrocompatibilidade, consumidores em
   PRs seguintes.
2. **O CI compara o schema vivo com o congelado** (`ci/freeze-de-contrato.sh`) e reprova
   drift — mudar o código não muda o contrato "por acidente".
3. **Consumidor desenvolve contra o mock, nunca contra o provedor:**
   `npx @stoplight/prism-cli mock contracts/pagamentos.openapi.yaml -p 4010`
   O agente do checkout constrói o fluxo inteiro sem nunca rodar — nem ler — pagamentos.
4. **Eventos são versionados no nome** (`*.v1.json`). Mudança breaking ⇒ nasce `v2`,
   `v1` continua sendo emitido até o último consumidor migrar. Renomear campo "porque
   achou melhor" não existe.
5. **Envelope canônico de evento:** `{event, version, event_id (uuid), occurred_at, data}`.
   Consumo idempotente por `event_id` é lei para toda célula consumidora.
6. **Autenticação:** APIs internas usam Bearer estático **por par** (checkout→pagamentos
   ≠ funil→leads). Sem sessão, sem fallback.
7. **Dinheiro é `amount_cents` inteiro** em todo contrato. Float de dinheiro é proibido.
