# Constituição da Célula: alunos
> **Jurisdição:** governa apenas `services/alunos/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde (exceto `apps/bridge/` — humano)

## Missão
Matrícula e acesso do aluno. Escuta `pagamento.aprovado.v1` e matricula — sob lock,
idempotente por `order_id` (INV-P5). Área do aluno em `/alunos/*` com auth local
simples (e-mail + link de definição de senha no primeiro acesso).

## Fronteiras
- **PERMITIDO ESCREVER:** `services/alunos/**`
- **SOMENTE LEITURA:** `contracts/alunos.openapi.yaml`, `contracts/eventos/`
- **PROIBIDO (nem ler):** as demais células, `infra/`

## Lei da Ponte (integrações com sistemas externos)
Quando esta célula precisar provisionar ou notificar um sistema externo (plataforma
de formação, comunidade, CRM), a integração obedece à lei da ponte:
- Vive exclusivamente em `apps/bridge/<sistema>.py`, atrás de flag
  `BRIDGE_<SISTEMA>_ENABLED=0` por padrão.
- Fala apenas HTTP, com token Bearer dedicado por sistema; sem sessão, sem fallback.
- Falha da ponte NUNCA impede a matrícula local (retry assíncrono via Huey).
- O resto da célula conhece apenas a interface `notificar_pontes(matricula)` —
  nenhum outro arquivo importa nada de `apps/bridge/`.
- Nenhuma ponte é implementada na Fase 0; cada uma entra por brief próprio.

## Comunicação
- **Escuta:** `pagamento.aprovado.v1` (consumer group `alunos`, idempotente por `event_id` e por `order_id`)
- **Expõe:** `/alunos/*` público + API interna mínima (`contracts/alunos.openapi.yaml`) para reprocesso manual
- **Banco:** `alunos_db` (role `alunos_user`)

## Invariantes desta célula
- **Multissítio:** a matrícula guarda o `site_id` do evento; a identidade do aluno
  é global por e-mail (a mesma pessoa pode comprar em vários sites).
- **INV-P5** matrícula sob `select_for_update()` + `transaction.atomic()`, idempotente por `order_id` — webhook/evento duplicado ⇒ UMA matrícula.
- Mensageria offline ⇒ matrícula acontece mesmo assim (o e-mail de boas-vindas é consequência, nunca pré-condição).

## Definição de Pronto
`make ci` verde · teste de evento duplicado/concorrente verde · diff no escopo.

## Ritos
RITOS.md §1, §2.
