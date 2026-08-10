# Constituição da Célula: pagamentos — A FORTALEZA

> **Jurisdição:** governa apenas `services/pagamentos/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (→ **CONGELADA** após ratificação v1.0 — ver §Congelamento)
> **Merge:** SEMPRE humano (CODEOWNERS). O botão de merge não existe para agentes aqui.

## Missão

A única célula do universo desta plataforma que conhece o Mercado Pago. Cria intents,
confirma cartão via token do Brick, gera Pix via API, recebe webhooks, mantém o ledger
e anuncia o resultado por eventos. Ela não sabe qual produto, qual bump, qual quiz,
qual campanha — recebe `order_id + amount_cents + customer` (mais um `site_id`
OPACO, que apenas ecoa nos eventos para atribuição) e cobra. O resto é
responsabilidade de outros domínios.

## Estrutura interna (vigiada por import-linter — INV-P9)

```
pagamentos/
├── core/            # 🔒 SOMENTE-LEITURA p/ agentes de método: modelos, ledger,
│                    #    outbox, validação de assinatura, gateway p/ providers
├── methods/
│   ├── pix/         # cria pagamento Pix na API MP, QR, expiração, webhook handler
│   └── card/        # confirma com card_token do Brick, parcelas, webhook handler
├── providers/
│   └── mercadopago/ # o ÚNICO lugar que fala HTTP com api.mercadopago.com
├── api/             # Django-Ninja: intents (interna) + webhooks (pública)
└── tests/           # unit + smoke_pix + smoke_card + guardas de invariante
```

**Leis mecânicas internas** (`.importlinter`, roda no `make ci`):
`methods.pix` e `methods.card` são **independentes** — nenhum importa o outro, nunca.
Métodos não importam `providers.*` diretamente — só através de `core.gateway`.

## Fronteiras

- **PERMITIDO ESCREVER:** `services/pagamentos/**` conforme o brief da sessão
  (um brief de Pix declara `methods/pix/**` + `tests/` como alvo; `core/` é somente-leitura)
- **SOMENTE LEITURA:** `contracts/pagamentos.openapi.yaml`, `contracts/eventos/`
- **PROIBIDO (nem ler):** todas as outras células, `infra/`

## Comunicação

- **Expõe internamente:** `POST /intents`, `GET /intents/{id}`, `POST /intents/{id}/card`
  (rede Docker apenas — o gateway NÃO publica essas rotas)
- **Expõe publicamente:** SOMENTE `/api/pagamentos/webhooks/mp/pix` e `/webhooks/mp/card`
  (é a única rota desta célula no Traefik; o MP precisa alcançá-la)
- **Emite:** `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1`
  — via outbox transacional (INV-P6) + relay Huey → Redis Streams
- **Autenticação de entrada:** Bearer estático por par (`TOKENS_ACEITOS_CHECKOUT`);
  sem fallback de sessão. Webhooks autenticam por assinatura
  `x-signature` do MP (INV-P10), nunca por Bearer.

## As leis do dinheiro (guardas completas em INVARIANTES.md)

- **INV-P3** Webhook idempotente por `mp_payment_id` — reentrega ⇒ uma transição, um evento.
- **INV-P4** `X-Idempotency-Key` obrigatória na criação de intent — replay ⇒ mesma intent.
- **INV-P6** Outbox na mesma transação do estado — evento nunca se perde, nunca antecipa.
- **INV-P8** `MP_ACCESS_TOKEN` de produção (`APP_USR-`) existe SÓ em `/opt/plataforma/env/pagamentos.env` na VPS. Dev/CI/worktrees conhecem apenas `TEST-`. O CI reprova `APP_USR-` no repo.
- **INV-P10** Webhook sem assinatura válida ⇒ 403, zero efeito colateral.
- `amount_cents` inteiro sempre; `Decimal` só na borda do provider; float é proibido.
- Toda chamada de escrita ao MP leva `X-Idempotency-Key` própria.
- **mypy estrito** (`mypy.ini`): código de dinheiro falha em check time, não em produção.

## Congelamento

Quando o esqueleto andar e os golden paths passarem, esta célula recebe tag `v1.0`,
o contrato congela e este cabeçalho muda para `STATUS: CONGELADA — alterações exigem
autorização do mantenedor e bump de versão`. Daí em diante ninguém desenvolve *contra*
pagamentos: desenvolve-se contra o mock do contrato. O pronto-e-funcionando não vira
labirinto porque nenhum agente volta a entrar aqui sem rito.

## Definição de Pronto

`make ci` verde (lint + import-linter + mypy estrito + testes + freeze de contrato) ·
**cross-smoke**: tocou `methods/pix` ⇒ `smoke_card` roda e passa (e vice-versa; `core/`
ou `providers/` ⇒ ambos) · evidência falsificável vermelho→verde para qualquer invariante ·
diff dentro do brief. **Não inclui:** E2E, deploy, credencial de produção.

## Ritos

RITOS.md §1 (worktree DENTRO de `services/pagamentos/`), §2 (catraca verde; 2 falhas ⇒
reset ao último verde ⇒ reportar — a terceira tentativa é onde nascem labirintos),
§3 (contrato), §4 (emergência = rollback; jamais hotfix no servidor).
