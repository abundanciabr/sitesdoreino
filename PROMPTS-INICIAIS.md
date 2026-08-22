# PROMPTS INICIAIS — Do Zero ao Esqueleto que Anda

> A ponte entre o kit-como-lei e o sistema-em-execução. Cada prompt de agente é o
> template de despacho do `CAMINHO-DOURADO.md` §2, preenchido. **Depois do Prompt
> Zero, o kit É o repositório** — os agentes leem constituições, contratos e receitas
> direto da árvore em que nasceram.

## Como operar (serial, não paralelo — até o esqueleto andar)

1. **Você** executa o Prompt Zero pessoalmente (agentes não tocam a VPS).
2. Para cada prompt de agente: abra o worktree que o despacho nomeia, cole o prompt,
   espere o PR verde. *(Atualização 22/08/2026: o merge deixou de ser seu — o agente
   mergeia pelo portão, `python ci/mergear.py <N> --confirmo <N>`, inclusive sob
   CODEOWNERS, com anúncio nominal no relatório. Lei 4 e
   `docs/decisoes/DECISAO-merge-pelo-agente.md`.)*
3. Um prompt por vez. Integração é o fato do fim da Etapa D, não uma aposta.
4. Só depois do esqueleto verde na VPS + red-team (Etapa E), abrem-se os briefs de produto.
5. **Multissítio:** um deploy, N domínios (Lei 9). Células públicas usam o middleware
   CONV-SITE; entidades públicas e eventos carregam `site_id` (INV-P11); domínio novo
   entra pela Receita R11 — nunca por infra.

## Mapa para o brief (`01-BRIEF-FASE-0.md`)

| Etapa do brief | Prompt aqui |
|---|---|
| A — Impossibilidades | **Prompt Zero** (humano) |
| B — Jaula verde vazia | **Prompt 1** (roda 8×, uma célula por PR) |
| C — Contratos + invariantes | ratificação no Prompt Zero; guardas nascem dentro dos prompts da Etapa D (evidência vermelho→verde) |
| D — O esqueleto que anda | **Prompts 2 a 7** (na ordem) |
| E — Red-team | **`02-RED-TEAM.md`** (15 golpes) → tag `fundacao-v1.0` |

---

# PROMPT ZERO — Bootstrap + Impossibilidades  *(executor: VOCÊ)*

Não é um prompt de agente: é o seu runbook. Nenhum agente recebe chave SSH desta VPS.

```
0.  Pré-requisitos locais: gh (GitHub CLI) autenticado, docker, openssl, ssh-keygen.
    Tenha em mãos: a VPS nova (IP), o domínio novo, acesso ao Postgres da VPS.

1.  Criar o repositório (privado) e entrar nele:
      gh repo create abundanciabr/plataforma --private --clone
      cd plataforma

2.  Descompactar o kit na raiz do repo (o conteúdo de kit-fundador/ vai para a raiz).

3.  Levar CI e CODEOWNERS ao layout que o GitHub exige (os scripts ci/*.sh FICAM em ci/):
      mkdir -p .github/workflows
      git mv ci/workflows/*.yml .github/workflows/
      git mv ci/CODEOWNERS .github/CODEOWNERS

4.  Preencher os placeholders (é o último momento barato):
      grep -rl 'TROQUE\|SEU-DOMINIO\|abundanciabr\|abundanciabr\|IP-DA-VPS-NOVA' .
      # substitua domínio, org, usuário, IP. Senhas do Postgres: openssl rand -hex 24
      # (a mesma senha em provisionamento-postgres.sql e no env/<celula>.env correspondente).

5.  PORTÃO 0.2 — Ratificar contratos: reveja contracts/*.openapi.yaml e contracts/eventos/*.
    Ajuste AGORA o que quiser. Após o commit inicial, mudança é Rito de Contrato (RITOS §3).

6.  Par de chaves do deploy (CI ↔ VPS):
      ssh-keygen -t ed25519 -f deploy_ci -N ''
      # deploy_ci.pub  → vai para a VPS (passo 7);  deploy_ci (privada) → segredo (passo 9)

7.  Erguer as impossibilidades na VPS:
      scp infra/provisionamento-vps.sh root@IP:/root/
      ssh root@IP 'DEPLOY_CI_PUBKEY="'"$(cat deploy_ci.pub)"'" bash /root/provisionamento-vps.sh'
      # depois, no Postgres da VPS (após trocar os TROQUE_* no arquivo):
      #   psql -U postgres -f infra/provisionamento-postgres.sql

8.  Montar /opt/plataforma na VPS:
      - copiar infra/docker-compose.yml e infra/traefik/* para /opt/plataforma/
      - criar /opt/plataforma/env/<celula>.env a partir de cada infra/env/*.exemplo
      ⚠ INV-P8: em TODOS os ambientes desta fase, MP_ACCESS_TOKEN=TEST-...  Nunca APP_USR-.

9.  Segredos do GitHub (repo → Settings → Secrets and variables → Actions):
      gh secret set VPS_HOST --body "IP-DA-VPS"
      gh secret set DEPLOY_SSH_KEY < deploy_ci        # a chave PRIVADA
      # apague a privada do disco local depois: shred -u deploy_ci

10. Criar as labels que as muralhas usam:
      gh label create contrato --color 5319e7
      gh label create arquitetural --color b60205
      gh label create "arquitetura:" --color d93f0b
      gh label create "mecanizar:" --color 0e8a16

11. Commit inicial + push para main ANTES da proteção (senão você se tranca para fora):
      git add -A
      git commit -m "chore: fundação da plataforma (kit fundador)"
      git push -u origin main

12. SÓ AGORA ative a branch protection em main (checklist do 00-LEIA-PRIMEIRO.md):
      required checks: muralhas, ci-celula-gate · review de Code Owners ·
      branches up to date · no force push / no deletion.

13. Provar as impossibilidades JÁ (não espere a Etapa E). Se qualquer uma NÃO bloquear,
    pare e conserte antes de despachar o primeiro agente:
      • Golpe 7 (dados):  psql "postgres://quiz_user:SENHA@IP:5432/pagamentos_db"
                          → deve falhar com "permission denied for database".
      • Golpe 8 (push):   git push origin HEAD:main  (de um branch qualquer)
                          → deve ser recusado pela proteção.
      • Golpe 13 (SSH):   confirme que nenhum agente tem a chave — ela é sua e do CI.
```

**DoD do Prompt Zero:** golpes 7, 8 e 13 bloqueados com evidência; repositório com a
fundação em `main`; VPS de pé; contratos ratificados e congelados.

---

# PROMPT 1 — A Jaula Verde Vazia  *(agente · roda 8×, uma célula por worktree/PR)*

Cole este despacho uma vez por célula, trocando `<celula>`. Ordem sugerida:
`catalogo, funil, quiz, leads, mensageria, alunos, checkout, pagamentos`.

```
# DESPACHO — <celula>: esqueleto da célula (jaula verde)
CÉLULA: <celula> · WORKTREE: wt-<celula>-esqueleto · RECEITAS: CONV, R1, R10

ANTES DE TOCAR QUALQUER ARQUIVO:
- Leia CONSTITUICAO.md, RITOS.md e constituicoes/AGENTS.<celula>.md.
- Leia CAMINHO-DOURADO.md §0, §1, §3 e as receitas citadas.
- Crie o worktree AGORA, antes de escrever qualquer arquivo (RITOS.md §1):
  `git fetch origin && git worktree add ../wt-<celula>-esqueleto -b agent/<celula>/esqueleto origin/main`
  — trabalhe só dentro dele; a checkout principal (main) fica intocada até o merge.
- Produza a declaração de abertura (RITOS.md §1) e confirme baseline limpo.

CONTEXTO: Repositório recém-fundado; nenhuma célula tem lógica. Esta sessão cria SÓ o
esqueleto DESTA célula a partir de celula-template/: projeto Django `config`, /healthz
e — se houver contrato congelado — a SUPERFÍCIE da API espelhando o contrato. Zero regra
de negócio.

MISSÃO: `make ci` desta célula VERDE.

ALVOS (PERMITIDO ESCREVER): services/<celula>/**
SOMENTE-LEITURA: celula-template/**, contracts/<celula>.openapi.yaml (se existir),
  contracts/eventos/**, CAMINHO-DOURADO.md
FORA DE ESCOPO: qualquer outra célula; regra de negócio; migrations de domínio;
  qualquer chamada real a serviço externo.

DoD:
- Estrutura do celula-template/ instanciada: config/ (settings fail-hard — CONV),
  apps/core, tests/, Makefile, Dockerfile, requirements.txt PINADO, pytest.ini (R10).
- GET /healthz → 200 com teste de fumaça verde.
- Se existir contracts/<celula>.openapi.yaml: comando export_openapi implementado (R1) e
  a superfície da API (rotas + schemas) espelha o contrato; handlers levantam
  NotImplementedError / retornam 501 → `make contrato-check` VERDE. Se o contrato não
  tiver `components.schemas` (tudo inline — ver "Notas operacionais" abaixo), use a
  técnica de `openapi_extra` documentada no addendo do R1 em CAMINHO-DOURADO.md.
- `make ci` verde (cole a saída no PR).
ORÇAMENTO: ≤ 15 arquivos (label `arquitetural` se ultrapassar — é scaffolding).

EVIDÊNCIA: saída de `make ci` + `git diff --name-only origin/main...HEAD`. Encerre com o
handoff (RITOS.md §1) — **o link do PR em linha própria, em destaque**, para eu poder
copiar sem precisar pedir. Depois que eu confirmar o merge (qualquer forma — "feito",
"mergeado", "ok"), atualize `arquivos/painel-fundacao.html` na hora, sem eu precisar
perguntar de novo se já foi atualizado.
```

**Especificidades por célula** (o resto do despacho é idêntico):

| Célula | Contrato? | O que o esqueleto inclui além de config + /healthz |
|---|---|---|
| catalogo | sim | Superfície R1: `GET /ofertas/{slug}`, `GET /produtos/{id}` (stubs 501) |
| leads | sim | Superfície R1: `POST /leads`, `POST /leads/{id}/tags` (stubs 501) |
| checkout | sim | Superfície R1: `POST /sessoes`, `POST /sessoes/{id}/pedido`, `GET /pedidos/{id}` (stubs 501) |
| alunos | sim | Superfície R1 + criar `apps/bridge/__init__.py` com stub `notificar_pontes()` (ponte OFF) |
| pagamentos | sim | Superfície R1 (intents + webhooks) + criar pacotes `core/`, `methods/pix/`, `methods/card/`, `providers/mercadopago/` (só `__init__.py`) + copiar `celula-template/pagamentos-extra/.importlinter` e `mypy.ini` para a raiz da célula → `lint-imports` e `mypy --strict` VERDES |
| funil | não | Só config + /healthz (contrato-check é pulado) |
| quiz | não | Só config + /healthz |
| mensageria | não | Só config + /healthz |

**Notas operacionais (aprendido nas células catalogo/leads — vale para as que faltam):**
- **Worktree antes de tudo.** Na célula leads o agente leu a documentação mas só criou o
  worktree no meio da sessão, depois de já ter escrito arquivos na checkout principal —
  teve que mover tudo para o worktree correto antes de commitar. O passo de `git worktree
  add` já está embutido no template acima; não pule.
- **`make` pode não existir na máquina do agente** (ex.: Windows sem Git Bash com make).
  Se faltar, rode os alvos do Makefile manualmente, na mesma ordem (`black --check .` →
  mypy se houver `mypy.ini` → `pytest -q` → `export_openapi` + `ci/freeze-de-contrato.sh
  <celula> <saida>`) e cole essa saída como evidência.
- **Windows + `ci/freeze-de-contrato.sh`:** o script chama `python3` sem encoding
  explícito; se acentos virarem lixo (mojibake) na comparação, rode com `PYTHONUTF8=1`
  só localmente — no CI real (Linux) não é preciso.
- **Contrato sem `components.schemas` (tudo inline, ex.: leads, alunos):** ninja.Schema
  tipado no handler vira `$ref` nomeado e quebra o freeze. Ver o addendo do R1 em
  `CAMINHO-DOURADO.md` (técnica `openapi_extra` + corpo `dict`).
- **Handoff:** sempre feche com o link do PR em linha própria — não deixe para o
  mantenedor pedir. Assim que o merge for confirmado (em qualquer sessão, mesmo que não
  seja a que abriu o PR), atualize `arquivos/painel-fundacao.html` imediatamente —
  marque o item como concluído, remova a caixa "Precisa de você agora" correspondente,
  e avance o contador de células da Fase B.

---

# ETAPA D — O ESQUELETO QUE ANDA  *(Prompts 2 a 7, na ordem)*

Cada prompt escreve o guarda de invariante PRIMEIRO (vê vermelho), implementa (vê verde)
e cola as duas saídas no PR — é a Lei 6 virando hábito. Em dev, dependências de outras
células vêm do mock prism (`make mocks`), nunca subindo a célula real.

## PROMPT 2 — catalogo: o produto do esqueleto

```
# DESPACHO — catalogo: produto e oferta reais
CÉLULA: catalogo · WORKTREE: wt-catalogo-seed · RECEITAS: R1, R7, R9, R11
ANTES: leia AGENTS.catalogo + CAMINHO-DOURADO (R1,R7,R9,R11). Declaração de abertura.

MISSÃO: modelos Site/Product/Offer/Bump (R7, expand-only; Offer com site_id, slug único
POR site) + comando criar_site (R11) + seed idempotente: Site "esqueleto" (host =
domínio de operações) e oferta "curso-esqueleto" (R9, 990 cents) NESSE site + handlers
REAIS de GET /sites/by-host/{host}, GET /sites/{site_id}/ofertas/{slug} e
GET /produtos/{id} servindo do banco.

ALVOS: services/catalogo/apps/sites/**, .../apps/produtos/**, .../apps/ofertas/**,
  .../apps/core/management/commands/seed_esqueleto.py, services/catalogo/tests/**
SOMENTE-LEITURA: contracts/catalogo.openapi.yaml, CAMINHO-DOURADO.md
FORA DE ESCOPO: outras células; admin; versionamento de oferta além do mínimo do contrato.
INVARIANTES: preço amount_cents inteiro; oferta publicada não editada destrutivamente;
INV-P11 — fronteira de site (guarda vermelho→verde obrigatória).

DoD: migrations aplicam; seed idempotente (rodar 2× não duplica) coberto por teste;
/sites/by-host resolve o host de operações e devolve 404 p/ host não cadastrado
(INV-P11 vermelho→verde); GET /sites/{id}/ofertas/curso-esqueleto → 990 cents;
contrato-check VERDE; make ci verde.
ORÇAMENTO: ≤ 15 arquivos.
EVIDÊNCIA: make ci + saída do seed rodado 2×. Handoff.
```

## PROMPT 3a — pagamentos: intents (sandbox MP)  *(merge: humano)*

```
# DESPACHO — pagamentos: intents
CÉLULA: pagamentos · WORKTREE: wt-pagamentos-intents · RECEITAS: R1, R5, R8
ANTES: leia AGENTS.pagamentos + INVARIANTES (P4,P8,P9) + CAMINHO-DOURADO (R1,R5,R8). Declaração.

MISSÃO: core.gateway + providers/mercadopago (fala com o MP só com TEST-) + POST /intents
(idempotente por X-Idempotency-Key; o payload traz site_id OPACO — armazenar e ecoar,
nunca interpretar) + GET /intents/{id}. Pix gera QR/expiração; card cria a
intent pendente aguardando confirmação (POST /intents/{id}/card com card_token do Brick).

ALVOS: services/pagamentos/pagamentos/core/**, .../providers/mercadopago/**,
  .../methods/pix/** (criação), .../methods/card/** (criação/confirmação), .../api/** (intents),
  services/pagamentos/tests/**
SOMENTE-LEITURA: contracts/pagamentos.openapi.yaml
FORA DE ESCOPO: webhooks, outbox e eventos (vêm no 3b); credencial APP_USR-; matrícula.
INVARIANTES TOCADOS: INV-P4 (guarda vermelho→verde). INV-P9 já é vigiado por import-linter.

DoD: methods/pix e methods/card independentes (lint-imports verde); mypy --strict verde;
test_inv_p4_intent_idempotente VERDE com evidência vermelho→verde; TODA escrita ao MP leva
X-Idempotency-Key própria; amount_cents inteiro; contrato-check VERDE; make ci + cross-smoke verdes.
ORÇAMENTO: ≤ 15 arquivos.
EVIDÊNCIA: make ci + cross-smoke + P4 vermelho→verde. Handoff.
```

## PROMPT 3b — pagamentos: webhooks, outbox e eventos  *(merge: humano)*

```
# DESPACHO — pagamentos: webhooks, outbox e eventos
CÉLULA: pagamentos · WORKTREE: wt-pagamentos-webhooks · RECEITAS: R3, R5, R8
ANTES: leia AGENTS.pagamentos + INVARIANTES (P3,P6,P10) + CAMINHO-DOURADO (R3,R5,R8). Declaração.

MISSÃO: handlers de /webhooks/mp/pix e /webhooks/mp/card na sequência: valida x-signature →
dedup por mp_payment_id → transição de estado → emitir na outbox NA MESMA transação → relay
para o Redis Streams. Endpoint DEBUG /debug/simulate-webhook (SÓ com DEBUG=1) que constrói e
entrega a si mesmo um webhook assinado (ver ESQUELETO-QUE-ANDA.md). Emitir pagamento.aprovado,
pagamento.recusado e pix.expirado conforme os schemas congelados (ecoando o
site_id da intent).

ALVOS: services/pagamentos/pagamentos/methods/pix/webhook*, .../methods/card/webhook*,
  .../apps/eventos/** (outbox + emitir + relay — R3), .../api/webhooks*, services/pagamentos/tests/**
SOMENTE-LEITURA: contracts/pagamentos.openapi.yaml, contracts/eventos/*.v1.json
FORA DE ESCOPO: consumo dos eventos (é de alunos/leads/mensageria); credencial APP_USR-.
INVARIANTES TOCADOS: INV-P3, INV-P6, INV-P10 (os três com guarda vermelho→verde).

DoD: webhook sem assinatura válida ⇒ 403 + banco intacto + outbox vazia (P10); mesmo webhook
3× ⇒ 1 transição + 1 linha de outbox (P3); aprovação grava outbox na MESMA transação e o relay
publica no stream (P6); com DEBUG=0 o endpoint de simulação NÃO existe (404); contrato-check VERDE;
make ci + cross-smoke verdes.
ORÇAMENTO: ≤ 15 arquivos.
EVIDÊNCIA: P3/P6/P10 vermelho→verde + saída do simulate-webhook local. Handoff.
```

## PROMPT 4 — checkout: sessão, snapshot e pedido  *(merge: humano)*

```
# DESPACHO — checkout: sessão, snapshot e pedido
CÉLULA: checkout · WORKTREE: wt-checkout-pedido · RECEITAS: CONV-SITE, R1, R2, R3, R4, R5, R6
ANTES: leia AGENTS.checkout + INVARIANTES (P1,P2,P7) + CAMINHO-DOURADO (R1,R2,R3,R4,R5,R6). Declaração.

MISSÃO: middleware CONV-SITE (site do Host; desconhecido = 404); POST /sessoes
(lê a oferta DO SITE no catalogo via R2); POST /sessoes/{id}/pedido (RECALCULA
dinheiro do catálogo — INV-P2 —, CONGELA o snapshot — INV-P1 —, cria a intent em pagamentos via
R2 e emite pedido.criado via R3); GET /pedidos/{id}. Páginas dados/pix/cartao como ilhas Alpine
(R6) com status derivado do servidor (INV-P7). Consumer de pagamento.aprovado/recusado/pix.expirado
(R4) atualiza o status do pedido.

ALVOS: services/checkout/apps/**, services/checkout/templates/checkout/**,
  services/checkout/static/checkout/**, services/checkout/tests/**
SOMENTE-LEITURA: contracts/checkout.openapi.yaml, contracts/catalogo.openapi.yaml,
  contracts/pagamentos.openapi.yaml, contracts/eventos/**, CAMINHO-DOURADO.md
FORA DE ESCOPO: catalogo, pagamentos, alunos; order bump além de somar itens do catálogo;
  design final das páginas (esqueleto funcional basta).
INVARIANTES TOCADOS: INV-P1, INV-P2, INV-P7, INV-P11 (guardas vermelho→verde).
DEV: consuma catalogo e pagamentos via mock prism (make mocks), nunca subindo as células.

DoD: payload adulterado com total/price falsos ⇒ snapshot com valores do catálogo (P2);
snapshot imutável por todos os caminhos públicos (P1); pix.js/cartao.js SEM transição local
para "pago" (status por GET /pedidos/{id} — P7); a página do Pix não carrega o SDK do MP;
contrato-check VERDE; make ci verde.
ORÇAMENTO: ≤ 15 arquivos. Se páginas + API ultrapassarem, DIVIDA em dois PRs (API/pedido primeiro,
depois páginas) — nunca use label para inchar o escopo.
EVIDÊNCIA: P1/P2/P7 vermelho→verde. Handoff.
```

## PROMPT 5 — alunos: matrícula por evento

```
# DESPACHO — alunos: matrícula por evento
CÉLULA: alunos · WORKTREE: wt-alunos-matricula · RECEITAS: R4, R5
ANTES: leia AGENTS.alunos + INVARIANTES (P5) + CAMINHO-DOURADO (R4,R5). Declaração.

MISSÃO: consumer de pagamento.aprovado.v1 (R4) que matricula sob select_for_update() +
transaction.atomic(), idempotente por order_id (INV-P5). A matrícula guarda o
site_id do evento. POST /matriculas para reprocesso
manual, com a MESMA idempotência. Mensageria offline NÃO impede matrícula. A ponte fica
DESLIGADA (apps/bridge intacto, flag off).

ALVOS: services/alunos/apps/matriculas/**, .../apps/eventos/** (consumer — R4),
  services/alunos/api/**, services/alunos/tests/**
SOMENTE-LEITURA: contracts/alunos.openapi.yaml, contracts/eventos/pagamento.aprovado.v1.json
FORA DE ESCOPO: apps/bridge (nenhuma integração externa na Fase 0); login/área do aluno final.
INVARIANTES TOCADOS: INV-P5 (guarda vermelho→verde).

DoD: dois consumers processando o mesmo evento em threads ⇒ 1 matrícula (P5); evento
reentregue (mesmo event_id) ⇒ 1 matrícula (dedup — R4); contrato-check VERDE; make ci verde.
ORÇAMENTO: ≤ 15 arquivos.
EVIDÊNCIA: P5 vermelho→verde. Handoff.
```

## PROMPT 6 — as quatro células finas  *(quatro PRs, um por célula)*

```
# DESPACHO — leads: pessoa e timeline por evento
CÉLULA: leads · WORKTREE: wt-leads-timeline · RECEITAS: R1, R4
MISSÃO: POST /leads (upsert por site_id+email — R1) + consumer dos eventos quiz.completado,
pedido.criado, pagamento.aprovado/recusado e pix.expirado (R4), montando timeline idempotente
por event_id. Nunca lê o banco de ninguém.
ALVOS: services/leads/apps/**, services/leads/tests/**
SOMENTE-LEITURA: contracts/leads.openapi.yaml, contracts/eventos/**
INVARIANTES: consumo idempotente (event_id); merge de pessoa preserva timeline.
DoD: evento duplicado ⇒ 1 entrada; upsert por email não duplica lead; contrato-check + make ci verdes.
ORÇAMENTO: ≤ 15 arquivos. EVIDÊNCIA + handoff.
```

```
# DESPACHO — mensageria: envios por evento
CÉLULA: mensageria · WORKTREE: wt-mensageria-envios · RECEITAS: R4, R8
MISSÃO: consumer (R4) que envia boas-vindas em pagamento.aprovado e recuperação em pix.expirado
e pagamento.recusado. Provedores como stubs que LOGAM (SMTP/WhatsApp reais ficam para depois).
Falha de provedor ⇒ retry Huey (R8); nunca propaga erro a quem emitiu.
ALVOS: services/mensageria/apps/**, services/mensageria/tests/**
SOMENTE-LEITURA: contracts/eventos/**
INVARIANTES: idempotência por event_id (1 envio por evento); mensageria nunca bloqueia dinheiro.
DoD: reentrega do mesmo evento ⇒ 1 envio; make ci verde (célula sem contrato REST).
ORÇAMENTO: ≤ 15 arquivos. EVIDÊNCIA + handoff.
```

```
# DESPACHO — quiz: resultado e evento
CÉLULA: quiz · WORKTREE: wt-quiz-resultado · RECEITAS: CONV-SITE, R3, R9
MISSÃO: middleware CONV-SITE + fluxo mínimo do Crivo (o quiz pertence ao site) — perguntas fixas via seed (R9), pontuação SÓ no servidor,
tela de resultado — emitindo quiz.completado.v1 pela outbox (R3) e redirecionando com ?lead=.
Páginas em /quiz/*.
ALVOS: services/quiz/apps/**, services/quiz/templates/quiz/**, services/quiz/static/quiz/**,
  services/quiz/tests/**
SOMENTE-LEITURA: contracts/eventos/quiz.completado.v1.json
INVARIANTES: pontuação calculada só no servidor; emissão transacional (outbox).
DoD: schema do evento validado contra o contrato; make ci verde (célula sem contrato REST).
ORÇAMENTO: ≤ 15 arquivos. EVIDÊNCIA + handoff.
```

```
# DESPACHO — funil: a vitrine mínima
CÉLULA: funil · WORKTREE: wt-funil-vitrine · RECEITAS: CONV-SITE, R2, R6
MISSÃO: middleware CONV-SITE + landing mínima DO SITE (R6, mobile-first, estende
base_mobile.html) que lê a default_offer do site no catalogo via R2 (server-side) e tem botão que redireciona para /checkout/<oferta> PRESERVANDO UTM.
Formulário de captura posta em leads via R2. Sem banco (célula stateless).
ALVOS: services/funil/**, services/funil/tests/**
SOMENTE-LEITURA: contracts/catalogo.openapi.yaml, contracts/leads.openapi.yaml
INVARIANTES: mobile-first por contrato (teste-guarda); UTM preservada até o checkout.
DEV: catalogo e leads via mock prism.
DoD: test_mobile_first_contract verde; UTM chega intacta ao link do checkout; make ci verde.
ORÇAMENTO: ≤ 15 arquivos. EVIDÊNCIA + handoff.
```

## PROMPT 7 — e2e: o esqueleto que anda  *(PR na raiz)*

```
# DESPACHO — e2e: o esqueleto que anda
WORKTREE: wt-e2e-esqueleto · RECEITAS: R9 (referência)
ANTES: leia ESQUELETO-QUE-ANDA.md INTEIRO. Declaração de abertura.

MISSÃO: e2e/esqueleto.sh que sobe o compose de dev do caminho, seeda e percorre via curl a
transação inteira — sessão → pedido → intent → (DEBUG simulate-webhook assinado) → outbox →
relay → matrícula — imprimindo cada elo com ✅/❌ e FALHANDO se qualquer elo falhar. Alvo
`esqueleto:` no Makefile da raiz.

ALVOS: e2e/**, Makefile (raiz)
SOMENTE-LEITURA: todas as constituições e contratos (referência), ESQUELETO-QUE-ANDA.md
FORA DE ESCOPO: alterar qualquer célula; usar APP_USR-; o caminho real de cartão (esse é o
run manual na VPS, não o e2e local).

DoD: `make esqueleto` VERDE localmente (webhook simulado assinado). No corpo do PR, deixe as
instruções para o run manual na VPS (cartão sandbox APRO + webhook real do MP) e para o drill
de rollback cronometrado (< 5 min), conforme os 4 critérios do ESQUELETO-QUE-ANDA.md.
ORÇAMENTO: ≤ 10 arquivos.
EVIDÊNCIA: saída completa de `make esqueleto`. Handoff.
```

---

# PROMPT FINAL — Graduação  *(Etapa E, você + um agente sabotador)*

Execute `02-RED-TEAM.md` inteiro: os 15 golpes, cada um com evidência crua do bloqueio.
Golpe que passar ⇒ issue `mecanizar:` ⇒ corrigir o portão ⇒ repetir o golpe até falhar.

Com a tabela 14/14 ☑:

```
git tag fundacao-v1.0
# editar constituicoes/AGENTS.pagamentos.md → STATUS: CONGELADA (via Rito de Contrato/PR)
```

A partir daqui, a fundação está de pé e testada. Abrem-se os briefs de produto — o primeiro
quiz real, a primeira oferta real, o funil de lançamento — cada um como um despacho novo,
citando as receitas do Caminho Dourado.

*Que as muralhas sejam testadas antes de serem necessárias. Amém.*
