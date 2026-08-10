# Constituição da Célula: mensageria
> **Jurisdição:** governa apenas `services/mensageria/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
Comunicação transacional: e-mail e WhatsApp disparados por eventos. Boas-vindas no
`pagamento.aprovado`, recuperação no `pix.expirado` e no `pagamento.recusado`.
Templates versionados dentro da célula. Nunca toca dinheiro, nunca bloqueia dinheiro.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/mensageria/**`
- **SOMENTE LEITURA:** `contracts/eventos/`
- **PROIBIDO (nem ler):** as demais células, `infra/`

## Comunicação
- **Escuta:** `pedido.criado.v1`, `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1`, `quiz.completado.v1` (consumer group `mensageria`)
- **Expõe:** nada público; API interna opcional para reenvio manual
- **Banco:** `mensageria_db` (role `mensageria_user`) — log de envios e templates

## Invariantes desta célula
- **Multissítio:** template e remetente escolhidos pelo `site_id` do evento
  (fallback padrão da plataforma) — e-mail de um site jamais sai com a marca de outro.
- Consumo idempotente por `event_id`: evento reentregue ⇒ UM envio (tabela de deduplicação).
- Falha de provedor (SMTP/WhatsApp fora) ⇒ retry com backoff via Huey; jamais propaga erro para quem emitiu.
- Todo envio registra: evento de origem, template+versão, destinatário, resultado.

## Definição de Pronto
`make ci` verde · teste de reentrega duplicada verde · diff no escopo.

## Ritos
RITOS.md §1, §2.
