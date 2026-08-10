# Constituição da Célula: quiz (Crivo)
> **Jurisdição:** governa apenas `services/quiz/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
O motor Crivo: perguntas, respostas, pontuação, resultado, qualificação. O quiz não
sabe o que é um cartão de crédito. Ao concluir, emite `quiz.completado.v1` e
redireciona com `?lead=…` — quem cria pedido é o checkout, quem guarda pessoa é leads.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/quiz/**`
- **SOMENTE LEITURA:** `contracts/eventos/quiz.completado.v1.json`
- **PROIBIDO (nem ler):** as demais células, `infra/`

## Comunicação
- **Expõe:** páginas públicas em `/quiz/*`
- **Consome:** nada
- **Emite:** `quiz.completado.v1` (via outbox → relay Redis Streams)
- **Banco:** `quiz_db` (role `quiz_user` — não enxerga nenhum outro database)

## Invariantes desta célula
- **Multissítio (INV-P11):** o quiz pertence a um site (resolvido do Host via
  CONV-SITE); `quiz.completado.v1` carrega `site_id`.
- Pontuação calculada exclusivamente no servidor; o cliente envia respostas, nunca score.
- Emissão de evento é transacional (outbox na mesma transação do resultado).

## Definição de Pronto
`make ci` verde · schema do evento validado contra o contrato · diff no escopo.

## Ritos
RITOS.md §1, §2. Evento novo ou mudança de payload = rito de contrato (§3), nunca decisão local.
