# Síntese das 4 consultorias externas + plano adaptado à restrição real

> **Recebido em:** 21/08/2026 · 4 pareceres independentes (Gemini, Fable, Fable-2, GPT),
> todos respondendo ao mesmo prompt (`arquivos/PROMPT-CONSULTORIA-EXTERNA.md`).
> **Fontes:** os quatro `.txt` nesta pasta, preservados como recebidos.
> **Este documento:** o que fazer com eles, dado um fato que nenhum deles conhecia.

---

## 0. O fato que invalida a recomendação nº 1 dos quatro

**Os quatro pareceres abrem mandando pagar o GitHub Pro.** Três chamam a decisão de
adiar de "completamente errada", "inversão de custo afundado" e "inversão de
prioridade". O prompt apresentava isso como escolha de custo ("não faturou, não
gasto") — e todos atacaram a escolha.

**Não é escolha.** O cartão de crédito do mantenedor não é aceito pelo GitHub e não há
outra forma de pagamento disponível. GitHub Pro está **descartado por impossibilidade,
não por preferência**.

Isso não anula os pareceres — o *diagnóstico* deles continua de pé, e é unânime: **um
portão que não impede o merge não é portão; é confiança sem garantia.** O que muda é a
solução. Onde os quatro escreveram "pague", leia "resolva o buraco por outro caminho",
e o §1 abaixo é esse caminho.

> **Correção de registro obrigatória:** `ARMADILHAS.md` §1 (H3), `INVARIANTES.md` e os
> painéis descrevem H3 como decisão de custo adiada. Isso agora é **falso** e precisa ser
> corrigido — senão todo agente futuro vai continuar recomendando "assine o Pro", que é
> conselho morto. Ver §6.

---

## 1. Resolver o buraco da proteção de branch — as três saídas reais

O buraco: todos os portões de CI podem estar vermelhos e o merge continua permitido.
Com Pro fora, restam três caminhos. **Não são mutuamente exclusivos.**

### Saída A — Portão no DEPLOY (recomendada, fazer já)

Ideia do parecer Fable, e é a melhor do conjunto inteiro: *você não consegue impedir um
merge ruim, mas consegue impedir um **deploy** ruim — e é o deploy que machuca cliente.*

`.github/workflows/deploy-celula.yml` hoje faz build+push e SSH na VPS **sem consultar
se os testes daquele commit passaram**. Um job novo antes do `deploy` consulta a API de
checks do commit e aborta se algo não estiver verde.

**Verificado como viável nesta sessão** — a API responde por commit:
```
gh api repos/abundanciabr/sitesdoreino/commits/<sha>/check-runs
→ ci-celula-gate: success · detectar: success · guardas do repositório: success
```

Vantagens: grátis, mecânico (impede, não avisa), cobre exatamente onde dói, e não
depende de plano nem de migração. Custo: uma sessão de agente.

**Armadilha a evitar na implementação** (é a mesma família de `ARMADILHAS.md` §5.6 e do
INV-CI01): `skipped` **não é verde**. No commit medido, `ci-celula` e `alarme` aparecem
como `skipped`. O gate precisa dos quatro estados — só `success` nos checks exigidos
libera; ausente, `skipped` sem declaração, ou falha ao consultar a API ⇒ **aborta o
deploy**. Um gate que erra para o lado do verde reproduziria o bug que o PR #22 existiu
para matar.

**Limite honesto:** isso não protege a `main` — código ruim ainda entra nela. Protege a
VPS e o cliente. É defesa em profundidade, não substituto de branch protection.

### Saída B — Migrar para GitLab

Dois pareceres (Gemini, GPT) afirmam que o GitLab Free tem protected branches em
repositório privado. **Confirme antes de mover** — nenhuma sessão verificou isso, e
migrar CI inteiro por uma premissa não checada seria caro. Fable-2 pondera que a
migração custa "muito mais atenção que US$4" — mas esse argumento assumia que os US$4
eram uma opção, e não são.

### Saída C — Tornar o repositório público

Libera branch protection no plano gratuito. **Os pareceres divergem, e a divergência
importa:**
- Fable: viável — nenhum segredo deveria estar no repo, e ninguém ganha vantagem lendo
  seu Django. **Exige** rodar `gitleaks`/`trufflehog` no histórico **completo** antes, e
  rotacionar o que aparecer.
- Fable-2 e GPT: má ideia **aqui** — publicaria o `ARMADILHAS.md`, que é um mapa
  detalhado dos seus buracos abertos (incluindo o bug do 201 falso), numa base que mexe
  com pagamento e é operada por uma pessoa só.

**Leitura desta sessão:** o contra-argumento é forte enquanto os bugs de dinheiro
estiverem abertos. Depois de fechados (§2), publicar volta a ser opção defensável.

**Recomendação:** faça a **Saída A esta semana**, independente do resto. Decida B ou C
depois, sem pressa, com os bugs já fechados.

---

## 2. Consenso unânime — os quatro concordam, faça sem discutir

| # | Ação | Por quê (na voz dos pareceres) |
|---|---|---|
| 1 | **`pagamentos`: validar a resposta do Mercado Pago, fail-closed** | O bug do `201` falso é o único da lista que **mente para o cliente**: diz que a cobrança existe quando não existe. GPT chama de "bloqueador absoluto". Testar 400/401/403/429/500, timeout, JSON inválido, e resposta "de sucesso" com campos faltando. Fable-2 sugere promover a invariante nova: *resposta de provedor só vira sucesso interno após validação de status E payload* |
| 2 | **`checkout`: publicar o evento órfão ou removê-lo formalmente** | GPT é o mais duro: "manter gravado e abandonado não é uma terceira opção". E levanta algo que ninguém tinha visto — se o e2e passa 8/8 **sem** esse relay, o teste pode estar validando uma rota paralela que contorna justamente o componente quebrado |
| 3 | **E2E no CI + varredura das alegações falsas de automação** | Os quatro tratam a documentação que mente como mais grave que a dívida técnica. Fable: "para quem não lê código, a documentação é o painel de instrumentos — e um instrumento seu está mentindo". Fable-2 propõe a regra: toda afirmação de automação nos docs referencia o job de CI que a prova |
| 4 | **Red-team restante: parar** | Unânime, com nuance. Gemini manda abandonar ("vaidade intelectual"); os outros mandam manter só os golpes ligados a dinheiro/webhook/autenticação e adiar o resto. Nenhum defende rodar os 10 agora |

**Sobre o item 4** — os golpes já rodados (1-5) não foram desperdício: todos bloquearam
de verdade, e o 5 ainda precisa do PR que fecha o certificado (pendência já registrada).
O que os pareceres condenam é *continuar* a série antes de fechar o que está aberto.

---

## 3. Os pontos cegos — o que NENHUM documento seu tinha

Estes não estavam em `ARMADILHAS.md`, nem no `PLAYBOOK.md`, nem no `RUNBOOK`, nem na
minha lista de dívidas. Três dos quatro pareceres levantaram cada um:

1. **Backup de banco + restauração testada.** Ausente de tudo. São 8 Postgres.
   *"Rollback de código não devolve dados"* (Fable-2). *"Se esse Postgres sumir, você
   não consegue provar quem comprou o quê — é existencial e são 15 minutos"* (Fable).
2. **Reconciliação: a consulta "quem pagou e não recebeu acesso".** Fable põe como o
   bloqueador nº 1 da lista inteira: *"sem isso você não descobre a falha — o cliente
   descobre por você, no WhatsApp, irritado."* Junto: uma ação manual de conceder acesso
   (transforma catástrofe em aborrecimento).
3. **Mínimos legais.** CDC art. 49 (7 dias de arrependimento), Decreto 7.962/2013
   (identificação do fornecedor, preço total, contrato, canal de atendimento), LGPD. GPT
   detalha e alerta: política "sem reembolso após 7 dias" é juridicamente arriscada.
4. **ECA Digital (Lei 15.211/2025) se o público inclui menores.** GPT levanta
   especificamente por causa de cursos de Roblox. Se crianças/adolescentes acessam,
   privacidade e desenho protetivo viram frente própria de go-live.
5. **Você virou o comerciante de registro.** Ao hospedar o próprio checkout, chargeback,
   MED do Pix, nota fiscal e disputa caem em você — não numa Hotmart que absorve isso.
6. **Fator ônibus = 1, e esse 1 não programa.** Fable recomenda o contraintuitivo:
   pagar um dev sênior humano para auditar `checkout` e `pagamentos` **uma vez, algumas
   horas** — vale mais que os 10 golpes restantes e custa menos em tempo de agente.
7. **Monitoramento externo + alerta no celular.** 8 processos e 8 bancos numa VPS, e o
   plantonista é você.

---

## 4. Onde eles DISCORDAM — decisão sua, com meu voto

### Drill de rollback: fazer ou pular?
- **Gemini:** pular. *"Luxo inútil. Se quebrar, você arruma ou volta manualmente."*
- **Fable:** é o item mais importante da lista inteira. *"Quando quebrar às 23h e você
  não puder ler o código, a única jogada disponível é voltar. Se nunca foi cronometrada,
  você não tem jogada nenhuma."*
- **GPT:** necessário, mas o critério está errado — rollback de software **não desfaz
  uma cobrança externa**. Precisa provar três coisas: parar novas transações, restaurar
  o software, e reconciliar o que aconteceu durante a falha.
- **Fable-2:** inclua o cenário com migração de banco no meio — é onde rollback de 5
  minutos vira de 5 horas.

**Meu voto: Fable e GPT estão certos, Gemini está errado aqui.** O argumento do Gemini
("você arruma manualmente") pressupõe alguém que lê código. Você não lê. Rollback não é
uma opção entre várias — é sua *única* resposta a incidente. E a correção do GPT é
importante: seu critério atual ("voltou o container em <5 min") é insuficiente sozinho.

### A arquitetura de 8 células foi um erro?
- **Gemini:** sim, erro claro. Microsserviços com zero usuários é fuga do mercado, e o
  evento órfão do checkout é consequência direta disso — num monólito seria uma
  transação simples.
- **Os outros três:** não desmontar. É custo afundado com mérito real no seu modo de
  operação — limita o raio de explosão de agentes que você não consegue auditar. GPT
  propõe **congelamento arquitetural** em vez de reversão.

**Meu voto: congelamento, não reversão.** O Gemini está certo no diagnóstico (é
complexo demais para o estágio) e errado na conclusão (migrar agora custaria meses e
introduziria riscos novos num sistema que mexe com dinheiro). Adote a regra do GPT:
*nenhuma célula, rito, constituição ou generalização nova até um piloto pago rodar.*

---

## 5. Plano ordenado (adaptado à restrição)

**Semana 1 — tornar verdadeiro o que já existe**
1. Portão no deploy (Saída A do §1) — fail-closed, `skipped` não é verde
2. `pagamentos` fail-closed na resposta do MP, com teste-guarda de credencial inválida
3. `checkout`: relay ou remoção formal do evento órfão — e confirmar se o e2e passa
   por ele ou por uma rota paralela
4. E2E no CI + varredura de alegações falsas de automação nos documentos

**Semana 2 — o que não existe e é existencial**
5. Backup automático dos bancos + **uma** restauração testada de verdade
6. Consulta de reconciliação "pagou e não recebeu" + ação manual de conceder acesso
7. Fechar Fase D: VPS com webhook real + drill de rollback nos 3 critérios do GPT

**Semana 3 — antes de dinheiro real**
8. Mínimos legais (CDC/Decreto/LGPD; ECA Digital se houver menores) — revisar com
   advogado; definir PF ou PJ e nota fiscal com contador
9. Kill switch (suspender cobranças sem derrubar acesso de aluno)
10. Monitoramento externo com alerta no celular

**Em paralelo, custo zero de código (começar já):**
11. **Validar demanda com link de pagamento do Mercado Pago + entrega manual.** Três dos
    quatro insistem nisso. *"Seu primeiro real não precisa passar pelo seu código."*
    Fable-2 pergunta o que nenhum documento seu responde: **o conteúdo dos cursos existe
    e está pronto?** Se não, o caminho crítico do projeto não é técnico.

**Recomendação tática que apaga vários bloqueadores de uma vez (Fable):** lance **só com
Pix**. Elimina chargeback, elimina fraude de cartão em produto digital de entrega
instantânea, elimina metade do caminho de código. Cartão entra depois das primeiras 50
vendas.

**Adiado:** red-team restante (exceto os de dinheiro), provedores reais de
e-mail/WhatsApp (modo concierge até ~20 clientes), leads/mensageria no e2e, multissítio,
novas células ou ritos.

---

## 6. Correções de registro que este documento obriga

1. **H3 em `ARMADILHAS.md` §1** — hoje diz "decisão de custo adiada de propósito enquanto
   o projeto não fatura". É falso: é impossibilidade de pagamento. Sem corrigir, todo
   agente futuro recomenda "assine o Pro".
2. **`INVARIANTES.md`**, seção "A cadeia de merge não está fechada" — mesma correção, e
   acrescentar o portão de deploy como degrau novo da Escada da Imposição quando existir.
3. **Painéis** — mesma correção, em linguagem para o dono.
4. **Reauditar tudo marcado "concluído"** (Fable item d, GPT): a Fase D avançou com 1 de
   4 critérios e ninguém barrou. *"O sistema que você construiu para se manter honesto
   não te manteve honesto nessa ocasião."* Uma passada relendo cada "concluída" contra os
   critérios que ela mesma declarou.

---

## 6-bis. Auditoria interna (3 agentes Opus, 21/08/2026) — o que as consultorias não podiam ver

As 4 consultorias externas responderam a um resumo escrito por nós. Três agentes
leram o **código e a infraestrutura reais**. Acharam coisas que nenhum resumo continha —
todas verificadas por mim, comando a comando.

### O que reordena o plano do §5

**Em produção não roda consumer nenhum.** `infra/docker-compose.yml` sobe 8 células +
traefik + postgres + redis; `grep -c "consumer|huey|consume_eventos"` → **0**. Os
containers `checkout-consumer` e `alunos-consumer` existem **só** em
`e2e/docker-compose.e2e.yml`. O `CMD` dos Dockerfiles é `migrate && uvicorn` — só HTTP.

Consequência: cliente paga → webhook valida → outbox grava → relay publica no Redis →
**ninguém lê**. Sem matrícula, sem e-mail, pedido preso em `aguardando_pagamento` para
sempre, e nenhum alarme. **Isto vem antes do portão de deploy**: não adianta trancar a
porta de um cofre sem fundo.

E o e2e não valida uma rota paralela no *código* — valida uma **infraestrutura
paralela**. O caminho do código é real; a topologia testada não existe no servidor.

### Bugs de dinheiro que ninguém tinha registrado

| Achado | Evidência |
|---|---|
| **Dedup gravado ANTES de matricular** — `EventoProcessado` commita, o handler roda fora daquela transação. Falha transitória ⇒ evento marcado como feito, matrícula nunca acontece, reentrega descartada | `alunos/apps/eventos/management/commands/consume_eventos.py:25-30`. Correção: mover uma linha para dentro do `atomic` |
| **Dois eventos órfãos, não um** — checkout **e quiz** gravam na outbox sem relay. E `leads` consome os dois (`consume_eventos.py:19-20`). Resultado: **quem abandona carrinho e quem completa quiz são invisíveis** | `services/quiz/config/` não tem `huey.py`. O §9 só registrava o checkout |
| **A assinatura do webhook não cobre o dado que decide** — valida `data.id` do query param; lê `id` e `status` do **corpo**, não assinado. Sem janela de frescor no `ts` | `webhook_signature.py:38` vs `methods/pix/webhook.py:34-35` |
| **Cartão recusado trava a intent em 409 permanente** — reforça a recomendação de lançar Pix-only | `methods/card/service.py:74` + linha 61 |

### Portões que são teatro (o mais grave da sessão)

- **A trava do INV-P9 é apagável com `rm` e nada acusa.** `Makefile:18` —
  `@if [ -f .importlinter ]; then lint-imports; fi`. Apagar o arquivo deixa `make ci`
  **verde**. Idem `mypy.ini`. Medido: **só `pagamentos` tem os dois; as outras 7 células
  não têm nenhum** — e o passo da CI se chama "lint + import-linter + type + testes +
  freeze".
- **`muralhas` só roda em `pull_request`** (`muralhas.yml:5-7`) — nunca no commit da
  main. E `alarme-main` roda só `--apenas testador`: **cerca, orçamento e guarda de
  segredos nunca rodam na main.**
- **Lei 4 é inexecutável**: `gh api .../collaborators` → **um colaborador**. O GitHub
  proíbe aprovar o próprio PR, então exigir review travaria todo PR para sempre.
  Saída de custo zero: **segunda conta GitHub gratuita** só para aprovar.
- `guarda-de-segredos.sh:18` — se a *redireção* falhar, bash retorna 1 sem executar o
  git e o script lê isso como "nenhuma ocorrência": passa sem ter varrido nada.
- `e2e/esqueleto.sh:100` — `curl` sem `-f` **sai 0 em HTTP 500**: a espera de `/healthz`
  aprova célula respondendo erro.

### O custo de produzir trabalho

- **O orçamento de 15 arquivos mudou a arquitetura do produto duas vezes**, com
  confissão escrita: a tabela de dedup do checkout (`checkout/LICOES.md:24` — "o
  orçamento fechava em 16") e o relay Huey (`pagamentos/LICOES.md:262` — "ficou fora do
  escopo para caber no orçamento"). **São exatamente as duas dívidas que as 4
  consultorias priorizam.** Distribuição: 13 PRs em exatamente 15 arquivos, **zero entre
  16 e 20**.
- **A regra "serial" venceu por escrito.** `grep -ci serial RITOS.md` → **0**. A fonte é
  `PROMPTS-INICIAIS.md:7`: *"serial, não paralelo — **até o esqueleto andar**"*. O
  esqueleto andou no PR #31. O painel atribui a frase ao RITOS §1, onde ela não existe.
  Medido: 7 células em 51 min, 6 PRs em 21 min, **zero colisões de código** — 5,5x de
  calendário já demonstrado.
- **`ARMADILHAS.md` é 48% da carga de contexto** (15.406 de ~32.180 tokens) e cresceu
  **364 → 842 linhas em 3 dias**. Quebrar em `armadilhas/NNN-slug.md` + índice reduz
  **86%** e mata a classe de conflito de merge que atrapalha o paralelismo.
- **110 arquivos carregam `[RECEITA:Rx v1]`; zero portões leem** — mais uma alegação
  falsa de automação (`CAMINHO-DOURADO.md:16`: *"é assim que detectamos drift"*).
- `.venv/` não está em nenhum `.gitignore` — a armadilha §3.8 existe só por isso.

### Ordem consolidada (substitui o §5 na parte de engenharia)

> **Atualização 21/08/2026, fim do dia:** os itens 1 e 2 foram executados em PRs
> paralelos — **#43** (alunos dedup), **#44** (pagamentos fail-closed, com `respx`),
> **#45** (consumers + worker + healthchecks + deploy descobrindo auxiliares),
> **#46/#47** (mesmo dedup em leads e mensageria), **#48** (lição §4.12).
> **Duas ressalvas novas, registradas em `ARMADILHAS.md` §1:** o compose **não chega à
> VPS por pipeline** (H11 — a produção só muda quando o mantenedor copiar o arquivo), e
> o 502 novo do fail-closed **não está no contrato congelado** (H7 — Rito de Contrato).

1. ~~**Consumers em produção** + mover a linha do dedup.~~ ✅ feito no Git (#43–#47);
   **pendura no H11** para valer na VPS.
2. ~~Fail-closed do MP~~ ✅ (#44) · **restam deste item:** os **dois relays**
   (checkout `pedido.criado`, quiz `quiz.completado` — `leads` espera os dois) e o
   endurecimento do webhook (`data.id` + janela de `ts`).
3. Portão de deploy (projetado por extenso; ver relatório do agente de CI) + sonda
   pós-deploy. Os healthchecks das células já entraram no #45; a sonda do workflow não.
4. Guarda-dos-guardas: `INVARIANTES.md` como fonte executável, afirmando que cada
   teste-guarda ainda existe e não foi enfraquecido. Mecaniza RITOS §2.3, que hoje é prosa.
5. Backup + restore testado · reconciliação diária · kill switch.
6. Aposentar a regra serial; afrouxar o orçamento para o valor declarado no despacho;
   reestruturar `ARMADILHAS.md`.
7. (novos, de H10/H11) Corrigir na célula os dois remendos do compose — checkout
   `request.path_info` no middleware, mensageria entrypoint Huey — e mecanizar o envio
   do compose para a VPS num passo do `deploy-celula`.

> **Auditoria do código de hoje (varredura de 21/08, noite):** li os diffs dos PRs
> #43–#48 inteiros. Veredito: **qualidade alta, nenhum bug novo encontrado** — o #44
> cobriu inclusive o replay da intent incompleta (completa em vez de recusar, seguro
> pela mesma `X-Idempotency-Key`), o cartão (status vazio não trava mais a intent) e o
> `ValueError` do `fromisoformat`; o compose respeita a §3.13 e a sonda TCP do checkout
> está documentada com causa e saída. **Dois buracos seguem abertos e ganharam
> evidência nova:**
> 1. **PEL do Redis sem recuperação** (era o B3): os fixes de dedup tornaram a
>    reentrega *segura*, mas nada *reentrega* — handler que estoura mata o processo, o
>    restart lê só mensagens novas (`xreadgroup ">"`), e a mensagem falhada fica na
>    Pending Entries List para sempre, sem alarme. `xautoclaim` existe só nos LICOES.
> 2. **A cadeia página→API→estáticos do checkout nunca foi ligada para produção** (era
>    o B6, agora com um 4º item): sem rota `/api/checkout` no Traefik, sem
>    `TOKENS_ACEITOS_*` no env de produção, sem servidor de estáticos com `DEBUG=0`, e
>    **`window.API_BASE` não é definido em nenhum template** (grep vazio — o `api.js`
>    chamaria `undefined/...`). Ninguém consegue comprar, mesmo com todo o backend
>    perfeito. Bloqueia o critério 2 da Fase D.
> Varredura transversal dos settings das 8 células: limpa (DEBUG off por padrão, sem
> SECRET_KEY hardcoded, sem csrf_exempt; `ALLOWED_HOSTS=["*"]` segue como observação).

### Novas linhas para `ARMADILHAS.md` §1 (PRECISA DE VOCÊ)

- **H8** — secret `MP_ACCESS_TOKEN` sandbox em Environment do GitHub, para o e2e em
  camadas rodar contra a MP real 1×/dia.
- **H9** — segunda conta GitHub gratuita, sem a qual a Lei 4 é inexecutável.
- **H12** — decidir se o `contrato-check` das 8 células é corrigido de uma vez (o
  template já tem a correção; nenhuma célula usa). *(Renumerado de H10 → H12 em
  21/08 à noite: sessões paralelas ocuparam H10/H11 com os remendos do compose e o
  achado de que o compose não chega à VPS por pipeline.)*

---

## 7. A frase que resume os quatro

> Pare de construir muralha. Conserte o instrumento que está mentindo. Torne o rollback
> e o backup reais. Lance só com Pix, em modo concierge, para dez pessoas — e descubra
> se alguém quer comprar antes de gastar mais um mês provando que a plataforma
> aguentaria se quisessem.

O maior risco deste projeto, segundo três dos quatro pareceres, não é webhook furado.
É **construir uma fortaleza perfeita que ninguém visita.**
