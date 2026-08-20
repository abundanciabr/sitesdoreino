# INVARIANTES — Jurisprudência Pré-Paga da Plataforma

Formato: **o quê / por quê / teste-guarda / célula dona**. Os invariantes de dinheiro
nascem ANTES da primeira feature, com guarda no mesmo PR — a lei existe antes da
primeira oportunidade de violá-la.

**Regras de trabalho:**
1. Código que toca um invariante referencia o código dele em comentário (ex.: `[INV-P3]`).
2. Teste-guarda é intocável: nunca deletar, desativar ou afrouxar para passar.
3. Evidência falsificável: correção em invariante apresenta a saída crua vermelho→verde.
4. Invariante sem guarda no mesmo PR só entra na seção final (dívida), com dono e prazo.

---

### [INV-P1] Snapshot do Pedido é Create-Only
- **O quê:** `Order.items`, `Order.total_cents` e `Order.customer` são congelados na
  criação. Nenhum caminho de código os atualiza depois — nem UPSERT, nem reprocesso,
  nem admin. Correção de pedido = novo pedido + cancelamento do antigo.
- **Por quê:** snapshot mutável é recibo que mente — um UPSERT descuidado zera campos,
  um reajuste de preço reescreve o passado do cliente, e o suporte nunca mais sabe o
  que a pessoa realmente comprou e por quanto.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p1_snapshot.py` — cria pedido,
  tenta alterar itens/total por todos os caminhos públicos, assert de imutabilidade.
- **Célula dona:** checkout

### [INV-P2] Dinheiro é Calculado no Servidor
- **O quê:** o cliente envia intenção (`bump_ids`, `method`, dados); o servidor
  recalcula itens e total a partir do catálogo. Qualquer valor monetário vindo do
  navegador é ignorado. Padrão client-sends-intent / server-validates.
- **Por quê:** total computado no cliente é superfície de manipulação de preço —
  basta editar o payload no DevTools para comprar por um centavo.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p2_server_money.py` — payload
  adulterado com `total_cents` falso e `price_cents` falsos ⇒ snapshot sai com os
  valores do catálogo.
- **Célula dona:** checkout

### [INV-P3] Webhook Idempotente por mp_payment_id
- **O quê:** o mesmo webhook entregue N vezes produz UMA transição de estado e UM
  evento na outbox. Chave de deduplicação: `mp_payment_id` + status alvo.
- **Por quê:** o Mercado Pago reentrega webhooks por design (retry, timeout,
  reprocessamento). Sem deduplicação, cada reentrega duplicaria matrícula, e-mail
  e linha de ledger.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p3_webhook_idempotente.py` —
  POST do mesmo webhook assinado 3×; assert: 1 transição, 1 linha de outbox.
- **Célula dona:** pagamentos

### [INV-P4] Criação de Intent Idempotente por X-Idempotency-Key
- **O quê:** `POST /intents` com a mesma chave devolve a MESMA intent (200), sem nova
  tentativa de cobrança. Toda escrita ao MP também leva `X-Idempotency-Key` própria.
- **Por quê:** refresh na página de pagamento, retry de rede e double-click são
  comportamento normal de usuário — e nenhum deles pode virar dupla cobrança.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p4_intent_idempotente.py` —
  2× POST mesma chave ⇒ mesma intent, 1 chamada ao provider (mock).
- **Célula dona:** pagamentos

### [INV-P5] Matrícula sob Lock, Idempotente por order_id
- **O quê:** o consumer de `pagamento.aprovado` matricula dentro de
  `transaction.atomic()` + `select_for_update()`, com unicidade por `order_id`.
  Evento duplicado ou concorrente ⇒ UMA matrícula.
- **Por quê:** eventos chegam duplicados e concorrentes por natureza (é a garantia
  at-least-once do transporte). Duplicar matrícula duplica acessos, e-mails de
  boas-vindas e tickets de suporte.
- **Teste-Guarda:** `services/alunos/tests/test_inv_p5_matricula_lock.py` — dois
  consumers processando o mesmo evento em threads ⇒ 1 matrícula no banco.
- **Célula dona:** alunos

### [INV-P6] Outbox Transacional
- **O quê:** todo evento emitido é gravado na tabela outbox NA MESMA transação da
  mudança de estado que o justifica. O relay (Huey) publica no Redis Streams depois.
  Estado sem evento e evento sem estado são ambos impossíveis.
- **Por quê:** "pagou mas não matriculou" e "matriculou sem pagar" são as duas
  falhas que destroem confiança num funil. O outbox elimina a janela entre commit e
  publicação.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p6_outbox.py` — aprovação ⇒
  na mesma transação existe linha de outbox; falha simulada do relay ⇒ evento
  permanece pendente e é republicado, nunca perdido.
- **Célula dona:** pagamentos (padrão replicado em quiz e checkout para seus eventos)

### [INV-P7] Status na UI Deriva do Servidor
- **O quê:** as páginas de pagamento fazem polling de `GET /pedidos/{id}` (ou intent).
  Nenhuma máquina de estado no navegador decide "pago"; nenhum status é inferido do
  passo do wizard ou de índice de array.
- **Por quê:** status inferido de estado local quebra com refresh, aba duplicada e
  o retorno do app do banco após o Pix. Dados do servidor sobrevivem a tudo isso.
- **Teste-Guarda:** `services/checkout/tests/test_inv_p7_status_servidor.py` +
  revisão de `pix.js`/`cartao.js`: os arquivos não contêm transição local para "pago".
- **Célula dona:** checkout

### [INV-P8] Segredo de Produção Só Existe em Produção
- **O quê:** `MP_ACCESS_TOKEN` de produção (`APP_USR-…`) existe em UM lugar no
  universo: `/opt/plataforma/env/pagamentos.env` na VPS, escrito manualmente pelo
  mantenedor. Dev, CI, worktrees e agentes conhecem apenas `TEST-…`.
- **Por quê:** credencial cara alcançável de ambiente de teste queima dinheiro real
  mais cedo ou mais tarde — um loop de testes com a chave errada cobra de verdade.
  Aqui isso não é proibido: é inexistente.
- **Teste-Guarda:** `ci/guarda-de-segredos.sh` (roda em todo PR — reprova `APP_USR-`
  e chaves privadas no repo) + red-team golpe nº 10.
- **Célula dona:** plataforma (CI)

### [INV-P9] Pix e Cartão Mutuamente Invisíveis
- **O quê:** `methods/pix` e `methods/card` não se importam (independência), e nenhum
  importa `providers/*` diretamente (só via `core.gateway`). No front, `pix.js` e
  `cartao.js` não compartilham estado nem funções além de `api.js`.
- **Por quê:** mudança num método de pagamento não pode alcançar o outro — nem por
  import, nem por estado compartilhado. Enquanto um método estiver em manutenção,
  o outro continua vendendo. A arquitetura diz "não" em check time.
- **Teste-Guarda:** `services/pagamentos/.importlinter` (`lint-imports` no `make ci`)
  + cross-smoke (`ci/cross-smoke.sh`): tocou um método, o smoke do outro roda.
- **Célula dona:** pagamentos

### [INV-P10] Webhook Sem Assinatura Válida ⇒ 403 e Zero Efeito
- **O quê:** todo webhook valida `x-signature` (HMAC com `MP_WEBHOOK_SECRET`) ANTES de
  qualquer leitura de payload com efeito. Inválido ⇒ 403, nada gravado, nada emitido.
- **Por quê:** um webhook forjado que aprovasse pedidos seria matrícula grátis em
  escala. Autenticação de origem vem antes de qualquer efeito colateral.
- **Teste-Guarda:** `services/pagamentos/tests/test_inv_p10_assinatura.py` — payload
  válido sem assinatura e com assinatura errada ⇒ 403 + banco intacto + outbox vazia.
- **Célula dona:** pagamentos

### [INV-P11] Fronteira de Site (multissítio)
- **O quê:** o site é resolvido do Host UMA vez por requisição (middleware
  CONV-SITE) e toda consulta pública é filtrada por `site_id`. Host não cadastrado
  ⇒ 404 — nunca "cai" num site padrão. Oferta, sessão, pedido, lead e matrícula de
  um site jamais aparecem em outro.
- **Por quê:** com dezenas de marcas em teste no mesmo deploy, o vazamento clássico
  de multi-tenant (preço/oferta de um site aparecendo em outro, ou host
  desconhecido servindo o site nº 1) contamina experimentos e quebra confiança —
  e é silencioso até acontecer em público.
- **Teste-Guarda:** `services/catalogo/tests/test_inv_p11_fronteira_site.py`
  (dois sites com o mesmo slug e preços distintos ⇒ cada host vê só o seu; host
  aleatório ⇒ 404) + `services/checkout/tests/test_inv_p11_fronteira_site.py`
  (sessão criada no site A não fecha pedido com oferta do site B).
- **Célula dona:** catalogo + checkout (padrão replicado em quiz, leads e alunos)

---

## Invariantes da própria CI

Os invariantes acima protegem a plataforma. Este protege o INSTRUMENTO que
verifica os outros — porque um portão que erra para o lado do verde não protege
coisa alguma, e ainda gasta a confiança de todo mundo.

### [INV-CI01] Portão Crítico é Fail-Closed
- **O quê:** todo portão crítico prova positivamente que executou a medição
  antes de devolver sucesso. A semântica é de quatro estados, e não de dois:

  | Situação | Estado | Exit |
  |---|---|---|
  | mediu e o estado está correto | `PASS` | 0 |
  | mediu e encontrou violação | `FAIL` | 1 |
  | **não conseguiu medir** | `ERROR` | 2 |
  | medição DECLARADA não aplicável | `SKIP` | 0 |

  É proibido o caminho `não conseguiu validar → PASS`. Em particular:
  ferramenta ausente, arquivo obrigatório ausente, raiz não resolvida, stdout
  vazio, exceção engolida, subprocesso sem propagação de exit code e `SKIP`
  inferido da ausência de evidência são todos `ERROR`. `SKIP` só existe quando
  alguém o declarou por escrito (ex.: `ci/manifesto-de-contratos.json`).
- **Por quê:** em 2026-08 o freeze de contrato imprimiu
  `✅ Freeze de contrato: OK` **com o contrato divergente**. O script chamava
  `python3`, que não existia naquela máquina; as duas pontas de
  `diff <(norm A) <(norm B)` viraram vazio; `diff(vazio, vazio)` deu igualdade.
  Uma ferramenta ausente virou aprovação. Um portão que só sabe dizer "não
  observei diferença" é indistinguível de um portão desligado — e o dia em que
  ele desliga sozinho é justamente o dia em que ninguém percebe.
- **Teste-Guarda:** `ci/tests/test_contract_freeze.py` — suíte adversarial que
  prova o portão reprovando quando deve: contrato divergente ⇒ `FAIL`;
  exportador quebrado, silencioso, ausente ou cuspindo lixo ⇒ `ERROR`;
  congelado ausente ou malformado ⇒ `ERROR`; raiz não resolvida ⇒ `ERROR`;
  dois lados vazios ⇒ `ERROR` (nunca `PASS`); `not-applicable` sem motivo
  declarado ⇒ `ERROR`. Roda no workflow `muralhas` a cada PR.
- **Célula dona:** o repositório (`ci/`) — não pertence a nenhuma célula.

#### Escopo de conformidade (atualize junto com a realidade)

INV-CI01 vale para os portões migrados. Declarar "CI fail-closed global" sem
esta tabela seria a mesma classe de erro que o invariante combate: afirmar mais
do que foi medido.

| Portão | Onde roda | Conforme? |
|---|---|---|
| freeze de contrato (`ci/contract_freeze.py`) | local + `make ci` da célula | **sim** |
| sonda de autenticação efetiva | junto do freeze | **sim** |
| cerca de célula · orçamento · guarda de segredos | workflow `muralhas` | **sim** |
| detecção de escopo + gate terminal (`ci-celula.yml`) | workflow `ci-celula` | **sim** |
| runner canônico (`ci/ci.py`) | local, `make`, workflow | **sim** |
| `contrato-check` dos 8 `services/*/Makefile` | `make ci` da célula | **não** — decide pelo disco em vez do manifesto (mitigado: a auditoria do manifesto roda em `muralhas` a cada PR) |
| **branch protection** | GitHub | **não existe** — ver abaixo |

#### A cadeia de merge não está fechada

Um portão fail-closed só protege se algo exigir que ele passe. Consultado em
2026-08-19, o GitHub responde à API de branch protection deste repositório:

```
Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)
```

Ou seja: **não há required check algum**. Todo portão descrito aqui pode estar
vermelho e o merge pelo site continua permitido. O único obstáculo é
`.githooks/pre-push`, que bloqueia push direto para `main` a partir desta
máquina — e não bloqueia merge de PR pela interface do GitHub.

Enquanto isso não mudar, o estado honesto é **núcleo fail-closed concluído, CI
global ainda parcial**. A mecanização está registrada na issue `mecanizar:` do
RITOS.md §2.

---

## Dívida de invariantes (nasce vazia — que permaneça assim)

| Código | O quê | Dono | Prazo | Motivo de estar sem guarda |
|---|---|---|---|---|
| — | — | — | — | — |

> Se esta tabela crescer, cada linha é uma esperança no lugar de uma lei.
