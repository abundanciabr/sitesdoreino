# Contratos

Esta pasta contém os formatos de integração entre as células do site.

## Compatibilidade HTTP

1. `ci/freeze-de-contrato.sh` compara o schema HTTP com o congelado. O manifesto
   `ci/manifesto-de-contratos.json` registra quais schemas participam dessa
   prova; um schema marcado como obrigatório precisa estar declarado nele.
2. Extensões aditivas preservam operações e definições existentes. Remoções,
   mudanças incompatíveis ou diferenças entre schema, manifesto e serviço
   aparecem na prova de compatibilidade.

3. Consumidores podem desenvolver e exercitar a integração pelo mock do schema:

```sh
npx @stoplight/prism-cli mock contracts/pagamentos.openapi.yaml -p 4010
```

## Eventos

4. Eventos têm versão no nome do arquivo, como `*.v1.json`. Uma mudança
   incompatível usa uma nova versão; consumidores existentes continuam podendo
   ler a versão que já utilizam durante a migração.

5. O envelope de evento é `{event, version, event_id, occurred_at, data}`.
   Consumidores usam `event_id` para tornar o processamento idempotente.

## Autenticação e valores

6. APIs internas usam Bearer estático distinto para cada par de serviços. Não
   há sessão nem autenticação alternativa.

7. Valores monetários usam `amount_cents` como inteiro; contratos não
   representam dinheiro com ponto flutuante.
