# BRIEF — FASE 0: A FUNDAÇÃO DA PLATAFORMA DE CÉLULAS ISOLADAS

> **Formato:** despacho para agentes executores. Você (mantenedor) executa a Etapa A
> pessoalmente e comparece nos Portões. Prazo total estimado: **3–5 dias-agente**.

---

## CONTEXTO

Esta plataforma nasce do zero (domínio novo, VPS nova, repo novo) sobre a
**Arquitetura de Células Isoladas**: 8 células Django independentes (catalogo, funil,
quiz, leads, checkout, pagamentos, alunos, mensageria), quatro muralhas (execução,
dados, código, contrato), e a Escada da Imposição — toda regra empurrada de prosa
para portão mecânico ou impossibilidade física. Multissítio por desenho: um deploy
serve N domínios — site é dado no catálogo, não infraestrutura (Lei 9, INV-P11,
Receita R11).

O kit fundador (este repositório de arranque) contém: CONSTITUICAO.md, 8 constituições
de célula, 5 contratos OpenAPI + 5 eventos versionados, INVARIANTES.md (11 invariantes
de dinheiro pré-pagos), infra completa (VPS, Postgres, Traefik, compose, envs), CI
(3 workflows + 5 scripts de muralha + CODEOWNERS), template de célula e 4 ritos.

## MISSÃO

Erguer a fundação: impossibilidades provisionadas, jaula verde vazia, contratos
ratificados e congelados, invariantes com guarda, o Esqueleto que Anda verde na VPS —
e a fundação **sobrevivendo ao red-team** (02-RED-TEAM.md). Nenhuma feature de
produto real nesta fase.

## PORTÃO 0 — RATIFICAÇÕES (com o mantenedor, ANTES de qualquer código)

| # | Decisão | Recomendação do kit | Ratificado |
|---|---|---|---|
| 0.1 | Domínio novo + nome do repo/org | definir; rodar `grep -r TROQUE` e preencher | ☐ |
| 0.2 | Contratos (`contracts/*.yaml` + eventos) | ratificar como estão; ajustes AGORA são grátis, depois são rito | ☐ |
| 0.3 | Fila | Huey intra-célula + Redis Streams inter-célula (outbox+relay) | ☐ |
| 0.4 | Integrações externas | nenhuma na Fase 0; cada uma entra por brief próprio sob a lei da ponte (AGENTS.alunos.md) | ☐ |
| 0.5 | Política de merge | auto-merge: funil/quiz/catalogo/leads/mensageria; humano: pagamentos/checkout/contracts/infra/ci | ☐ |
| 0.6 | TLS multissítio | Modo A (Cloudflare SSL Full — domínio novo = ZERO infra) recomendado; Modo B (LE) exige listar cada domínio | ☐ |
| 0.7 | Domínio de operações | qual domínio fixo recebe os webhooks MP (e, recomendado, o portal do aluno) | ☐ |

---

## ETAPA A — IMPOSSIBILIDADES *(executor: VOCÊ, não agente · ~meio dia)*

**Entregáveis:**
1. VPS provisionada com `infra/provisionamento-vps.sh` (usuário deploy só com chave
   do CI; sem senha; ufw; docker; `/opt/plataforma` 750; redes edge/interna).
2. Postgres com `infra/provisionamento-postgres.sql` (7 databases, 7 roles, senhas
   de `openssl rand -hex 24`).
3. `/opt/plataforma/`: compose + traefik + `env/*.env` preenchidos.
   ⚠ INV-P8: `APP_USR-` NÃO entra nesta fase em lugar nenhum — sandbox `TEST-` em tudo.
4. Repo GitHub criado; secrets `VPS_HOST` e `DEPLOY_SSH_KEY`; labels `contrato`,
   `arquitetural`, `mecanizar:`, `arquitetura:` criadas.
5. Branch protection de `main` conforme checklist do 00-LEIA-PRIMEIRO.md.

**DoD:** golpes 7, 8 e 13 do red-team já falham (teste-os agora mesmo — não espere a Etapa E).

## ETAPA B — A JAULA VERDE VAZIA *(agente · ~1 dia)*

**Entregáveis:**
1. Estrutura do repo: `CONSTITUICAO.md`, `RITOS.md`, `INVARIANTES.md`, `contracts/`,
   `constituicoes/`, `ci/` → `.github/workflows/` + `.github/CODEOWNERS`, `infra/`,
   `services/` com as 8 células instanciadas do `celula-template/` (config mínimo,
   healthcheck `/healthz`, zero feature).
2. Os três workflows verdes em um PR de fumaça por célula (um PR trivial por célula
   provando que `muralhas` + `ci-celula` rodam e passam).
3. `make ci` verde LOCALMENTE em cada célula (pytest com 1 teste de fumaça).

**DoD:** CI inteiro verde ANTES de existir qualquer feature; golpes 1–4 do red-team
já falham. **Proibido:** qualquer lógica de negócio nesta etapa.

## ETAPA C — CONTRATOS RATIFICADOS + INVARIANTES SEMEADOS *(agente + você no portão · ~1 dia)*

**Entregáveis:**
1. Sessão de ratificação dos contratos (Portão 0.2 formalizado): ajustes finais em
   PR único `contracts/` com label `contrato`; a partir do merge, CONGELADOS.
2. `export_openapi` implementado em cada célula com contrato; `make contrato-check`
   verde célula a célula (o schema vivo nasce IGUAL ao congelado).
3. Testes-guarda dos 11 invariantes criados como testes REAIS (podem nascer
   vermelho-esqueleto com `xfail` documentado apenas onde o alvo ainda não existe;
   INV-P1/P2/P3/P4/P5/P6/P10 devem nascer verdes na Etapa D).
4. Mocks prism funcionando: `make mocks` em checkout sobe pagamentos+catalogo fake.

**DoD:** golpes 5, 6 e 12 do red-team já falham.

## ETAPA D — O ESQUELETO QUE ANDA *(agente, um por célula em worktrees · ~1,5–2 dias)*

Seguir `ESQUELETO-QUE-ANDA.md` à risca, construindo pelas receitas do
`CAMINHO-DOURADO.md` (cada despacho cita as suas). Ordem de construção sugerida (cada item =
1 sessão de agente = 1 worktree = 1 PR):

1. `catalogo`: modelo Product/Offer/Bump + seed "curso-esqueleto" + API do contrato.
2. `pagamentos`: intents + sandbox MP + webhooks assinados + outbox + relay
   (INV-P3/P4/P6/P10 verdes com evidência vermelho→verde).
3. `checkout`: sessão + snapshot + pedido + páginas dados/pix/cartao mínimas
   (INV-P1/P2/P7 verdes).
4. `alunos`: consumer + matrícula sob lock (INV-P5 verde) + listagem.
5. `leads`, `mensageria`, `quiz`, `funil`: consumers/emissores mínimos do caminho.
6. `e2e/esqueleto.sh` + `make esqueleto` na raiz.

**DoD (os 4 critérios do ESQUELETO-QUE-ANDA.md):** esqueleto verde local (webhook
simulado) e na VPS (cartão APRO + webhook real do MP); drill de rollback < 5 min;
evidências cruas anexadas.

## ETAPA E — O RED-TEAM *(você + agente sabotador · ~meio dia)*

Executar `02-RED-TEAM.md` inteiro. 15/15 golpes bloqueados com evidência ⇒ a tabela
vira o certificado de graduação no PR final. Golpe que passar ⇒ `mecanizar:` ⇒
corrigir ⇒ repetir o golpe.

**Ao graduar:** tag `fundacao-v1.0`; `constituicoes/AGENTS.pagamentos.md` muda para
STATUS: CONGELADA. Só então abrem-se os briefs de produto (primeiro quiz real,
primeira oferta real, funil de lançamento).

---

## PROIBIÇÕES DA FASE 0 (para todo agente)

1. Nenhuma feature de produto — a fundação não compete com o funil por atenção.
2. Nenhum toque em `contracts/` fora do rito (Etapa C, com o mantenedor).
3. Nenhuma credencial `APP_USR-` em lugar algum, nem "só para testar".
4. Nenhum agente pede, recebe ou usa acesso SSH — deploy é pipeline, emergência é rollback do mantenedor.
5. Nenhum teste-guarda afrouxado, desativado ou deletado — inclusive os xfail: viram verdes, nunca somem.
6. Duas tentativas falhas ⇒ reset ao último verde ⇒ reportar (RITOS.md §2). Sem exceção.

## EVIDÊNCIAS EXIGIDAS (o que cada PR de etapa anexa)

- Saída crua de `make ci` da célula tocada (verde).
- Para invariantes: vermelho sem o fix → verde com o fix, colado sem edição.
- Para a Etapa D: as duas execuções do esqueleto (local + VPS) na íntegra.
- Para a Etapa E: a tabela 14/14 com prints.
- Handoff de cada sessão (RITOS.md §1) no corpo do PR.

## RISCOS CONHECIDOS E RESPOSTA PRONTA

- **Webhook local:** MP não alcança localhost ⇒ endpoint DEBUG de simulação assinada
  (já especificado no ESQUELETO-QUE-ANDA.md). Não inventar túnel/ngrok na Fase 0.
- **Sandbox MP instável:** se o sandbox oscilar, o teste-guarda usa o provider
  mockado (respx) e a validação real fica para o run manual na VPS — nunca afrouxar
  o guarda por instabilidade de terceiro.
- **Tentação de acelerar pulando o red-team:** a Etapa E é o que separa esta fundação
  do plano anterior "que garantia que tudo daria certo". Ela não é opcional.

*Que as muralhas sejam testadas antes de serem necessárias. Amém.*
