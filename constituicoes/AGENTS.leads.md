# Constituição da Célula: leads
> **Jurisdição:** governa apenas `services/leads/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
A pessoa antes do dinheiro: entidade Lead/Person (upsert por e-mail/telefone), UTM,
tags, consentimentos e timeline. Escuta os eventos da plataforma para montar a
história de cada pessoa — nunca lê o banco de ninguém.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/leads/**`
- **SOMENTE LEITURA:** `contracts/leads.openapi.yaml`, `contracts/eventos/`
- **PROIBIDO (nem ler):** as demais células, `infra/`

## Comunicação
- **Expõe:** API interna conforme `contracts/leads.openapi.yaml` (sem rota pública)
- **Consome eventos:** `quiz.completado.v1`, `pedido.criado.v1`, `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1` (consumer group próprio; idempotente por `event_id`)
- **Banco:** `leads_db` (role `leads_user`)

## Invariantes desta célula
- **Multissítio:** upsert por (`site_id`, `email`) — a mesma pessoa pode ser lead
  em vários sites; a timeline é por site.
- Consumo idempotente: o mesmo `event_id` processado duas vezes gera uma única entrada de timeline.
- Merge de pessoas (mesmo e-mail em fontes distintas) preserva timeline integral — nunca deleta histórico.

## Definição de Pronto
`make ci` verde · replay de evento duplicado coberto por teste · diff no escopo.

## Ritos
RITOS.md §1, §2.
