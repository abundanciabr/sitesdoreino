# PLANO 10X — as cinco alavancas de ordem de grandeza deste sistema

> **Escrito em 21/08/2026**, consolidando: 3 auditorias internas profundas (economia de
> contexto, caminho do dinheiro, portões de CI — agentes Opus, relatórios com números
> medidos), 4 consultorias externas independentes (`Recomendacao-*.txt` nesta pasta),
> e duas varreduras de código linha a linha (incluindo os PRs #43–#48).
>
> **O que este documento NÃO é:** uma lista de tudo que dá para melhorar. Isso já
> existe (`SINTESE-E-PLANO.md`, `ARMADILHAS.md` §1/§9). Um 10x não vem de vinte
> melhorias de 10% — vem de poucas alavancas onde a linha de base medida está uma
> ordem de grandeza longe do possível. Encontramos **cinco**. Cada uma traz: a linha
> de base MEDIDA, o alvo, os movimentos (dimensionados como despachos), e o risco.
>
> **Premissa inegociável (congelamento arquitetural, decisão já registrada):** nenhuma
> alavanca cria célula, rito, constituição ou abstração nova. Tudo aqui é subtrativo,
> de ferramenta, ou de fiação do que já existe.

---

## ALAVANCA 1 — Throughput da fábrica: o gargalo é a janela humana, não a CI

**Linha de base medida:**
- CI roda em **15–70 s**. Latência PR→merge: mediana **22 min**, média **264 min** —
  o gargalo é a janela de atenção do mantenedor, não a máquina.
- A doutrina manda operar serial — mas a regra **venceu por escrito**
  (`PROMPTS-INICIAIS.md:7`: *"serial, não paralelo — até o esqueleto andar"*; o
  esqueleto andou no PR #31) e está **mal atribuída** no painel (cita RITOS §1, onde a
  palavra "serial" não existe: `grep -ci serial RITOS.md` → 0).
- O paralelo já foi demonstrado DUAS vezes: **7 células em 51 minutos** na Fase D
  (6 PRs mergeados em 21 min, zero colisões de código) e **6 PRs em uma noite**
  (#43–#48) em 21/08. As únicas colisões medidas foram em **arquivo de texto
  compartilhado** (`ARMADILHAS.md` @@ -309, tabela do `02-RED-TEAM.md`, bloco `env:`
  do `ci-celula.yml`) — nunca em código. A proteção real é a cerca (1 PR = 1 célula),
  que não muda.

**Alvo:** de ~1 despacho por ciclo de atenção para **um LOTE de 4–6 células por
janela** — 5x de calendário, já provado, só não codificado.

**Movimentos:**
1. Aposentar a regra serial por escrito (1 parágrafo; corrigir a atribuição falsa no
   painel). Custo: minutos. Decisão: do mantenedor.
2. Codificar o padrão de lote: 1 lote = N células **distintas** + 1 janela de merge.
   Merge serial dentro da janela (`make mergear` um a um), desenvolvimento paralelo.
3. Tornar os 3 arquivos de colisão *append-safe* — resolvido de graça pela Alavanca 2
   (particionamento do ARMADILHAS) e por regra de despacho ("tabela do red-team: cada
   golpe escreve SÓ a própria linha").
4. Manter serial onde há dependência real: Rito de Contrato (provedor→consumidores) e
   o e2e de fechamento.

**Risco:** baixo — o mecanismo de segurança (cerca + worktree) já segurou os dois
episódios reais. O que muda é só a permissão.

---

## ALAVANCA 2 — Custo de contexto por despacho: de ~32k para ~8k tokens

**Linha de base medida (despacho real de checkout, somado arquivo a arquivo):**
- **32.180 tokens** de governança carregados ANTES da primeira linha de código.
- `ARMADILHAS.md` sozinho = **15.406 tokens (48% da carga)**, com ~38% do conteúdo
  inútil para um despacho de célula (histórico "RESOLVIDO", seções só do humano, como
  mergear — o agente não mergeia). Cresceu **364 → 842 linhas em 3 dias (+131%)** e é
  append-only por lei: a curva não achata sozinha.
- `INV-CI01` = **33% do INVARIANTES.md**, e trata dos portões da CI — irrelevante para
  quem implementa célula.
- `arquivos/painel-fundacao.html` = **~34k tokens**, e o CLAUDE.md manda editá-lo a
  cada tarefa — **cada atualização de painel custa mais que toda a governança de um
  despacho**.
- Os "6 primeiros minutos" de toda sessão (worktree+venv+docker+env) são manuais,
  documentados em ~900 tokens de §2/§3 — e já causaram N rodadas de erro (PATH, venv,
  `/tmp`, UTF-8).

**Alvo:** ~8k tokens de governança por despacho (**4x**), painel editável por ~2k
(**16x**), e os 6 minutos virando 1 comando. Isso COMPÕE com a Alavanca 1: contexto
menor × lotes maiores.

**Movimentos:**
1. **Particionar `ARMADILHAS.md`** em `armadilhas/NNN-slug.md` (48 entradas hoje) +
   `INDICE.md` gerado, 1 linha por entrada com a MENSAGEM DE ERRO CRUA como chave de
   busca. Regra nova: "leia o índice e abra só o que casa com sua tarefa". Histórico
   (`RESOLVIDO`) vai para `docs/historico/`. Seções do humano (§1, §5.8–5.9, §7.1–7.4)
   viram `ARMADILHAS-OPERACAO.md`, fora da dieta do agente. **Bônus: mata a classe
   inteira de conflito de merge em paralelo** (duas sessões escrevem entradas
   diferentes = arquivos diferentes).
2. **Extrair `INV-CI01`** para `INVARIANTES-CI.md` (−1.300 tokens por despacho de
   célula; ele fica junto de quem o usa, `ci/`).
3. **Separar dados do renderizador do painel**: `arquivos/painel-dados.js`
   (`const DADOS = {...}`) + HTML estático que o carrega via `<script src>` (tem que
   ser `.js`, não `.json`+fetch — o painel abre por `file://`). Edição de painel cai
   de ~34k para ~2k tokens.
4. **`make sessao CELULA=x TAREFA=y`**: fetch + worktree + venv FORA do worktree +
   `pip install` + Postgres em background + `.env` de sessão + doctor + baseline `make
   ci` + imprime a Declaração de Abertura preenchida. Mecaniza o RITOS §1 inteiro e
   apaga §3.3/3.4/3.5/3.8/3.9 da leitura obrigatória.
5. `PLAYBOOK.md` assume papel de ÍNDICE (ele já é mapa; hoje soma 5,3k tokens em vez
   de substituir leitura — decidir: ou vira índice de 30 linhas, ou ganha portão de
   consistência).

**Risco:** médio-baixo. O único real: agente não achar uma armadilha cujo sintoma não
soube nomear — mitigado mantendo a mensagem de erro crua no índice (as entradas já são
escritas assim de propósito).

---

## ALAVANCA 3 — Confiança mecânica: cada garantia declarada ganha um verificador

Esta é a alavanca da TESE do projeto. A premissa inteira — "um não-programador opera
com segurança via agentes" — depende de portões que mordem. A auditoria mediu o
contrário em pontos centrais:

**Linha de base medida (o teatro):**
| Garantia declarada | Realidade medida |
|---|---|
| "INV-P9 vigiado por import-linter" | o guarda é `@if [ -f .importlinter ]` — **apagar o arquivo deixa `make ci` verde**, nada acusa |
| "lint + import-linter + type + testes" (nome do step no CI) | **7 das 8 células não têm** `mypy.ini` nem `.importlinter` — para elas o step roda black+pytest |
| "muralhas rodam em todo PR" | verdade — mas **nunca na main**: `alarme-main` roda só `--apenas testador`; **a guarda de segredos nunca executou na main** |
| "hook pre-push bloqueia push direto" | depende de `core.hooksPath` por clone, **que nada verifica** — nem o doctor |
| "`[RECEITA:Rx v1]` é como detectamos drift" | **110 arquivos** carregam o marcador; **0 portões** o leem |
| "make esqueleto roda no CI a cada PR" | **não roda em workflow nenhum** |
| "required checks impedem merge" | não existem e **não podem existir** (H3 — sem forma de pagamento aceita) |
| deploy | **cego**: não consulta checks (ganha a corrida por ~55s) e fica verde com container em crash-loop (`compose ps` = exit 0; sonda pós-deploy só entrou no compose, não no workflow) |

**Alvo:** zero alegações falsas de automação, e a cadeia
commit → checks → deploy → produção com um verificador em cada elo. De ~6 portões que
mordem para ~14. Isso não é 10x de velocidade — é 10x no que o projeto VENDE para si
mesmo: a capacidade de o dono confiar no verde.

**Movimentos (todos já projetados em detalhe no relatório do agente de CI):**
1. **Portão de deploy** (`ci/portao_de_deploy.py` + YAML prontos): consulta os checks
   reais do commit ANTES do build, 4 estados INV-CI01, chaveado por *path* de workflow
   (há dois checks `detectar` no mesmo SHA), evidência das muralhas via PR de origem —
   efeito colateral desejado: push direto sem PR não vira deploy. É o required check
   que o GitHub não vende.
2. **Guarda-dos-guardas**: `INVARIANTES.md` como fonte executável — parse dos campos
   `Teste-Guarda:`, afirmar que cada arquivo citado existe, tem `def test_`, sem
   `skip/xfail`; e o inverso (todo `test_inv_*.py` em disco está declarado). Mecaniza
   RITOS §2.3 ("teste é intocável"), hoje prosa. Fecha também o buraco do
   `.importlinter` apagável.
3. **`alarme-main` roda as muralhas completas** (`--apenas muralhas,testador`) — a
   guarda de segredos passa a existir na main. Custo: 1 linha.
4. **Sonda pós-deploy no workflow** (o healthcheck já está no compose desde o #45; o
   workflow ainda declara sucesso sem olhar).
5. **`doctor` verifica `core.hooksPath`** e o drift template↔células (a correção do
   `contrato-check` existe SÓ no template — H12).
6. **e2e em camadas no CI** (projeto pronto no relatório): `respx` no transporte a cada
   PR (já entrou no #44); `mp-fake` stateful de ~80 linhas para o esqueleto mockado a
   cada PR de célula do caminho; sandbox real 1×/dia agendado (precisa do secret — H8);
   elo "pedido→pago" **promovido a bloqueante** (hoje é "diagnóstico, não bloqueia" —
   o e2e pode passar 8/8 com o pedido preso). Junto: `curl -f` no healthz do harness
   (hoje `curl` sem `-f` aprova HTTP 500).
7. **Duas correções de 1 linha que não esperam despacho próprio:**
   `guarda-de-segredos.sh:18` (falha de redireção vira "não achei") e o item 6's curl.

**Risco:** o modo de falha de tudo acima é "abortar quando não devia" — o lado seguro,
recuperável por re-run. O teto honesto: quem editar o YAML e remover o portão não é
impedido, é detectado (teste de forma no `muralhas` + `alarme-main`).

---

## ALAVANCA 4 — Detecção de falha: de "o cliente reclama" para "o sistema avisa"

**Linha de base:** hoje, **todo** caminho de falha do dinheiro é descoberto pela
reclamação do cliente. Não existe reconciliação, alarme, nem consulta "quem pagou e
não recebeu". Tempo-até-detecção: **horas ou dias** (e custo reputacional junto).
Caminhos abertos que levam a "pago sem entrega", todos verificados no código:
- Mensagem falhada fica na **PEL do Redis para sempre** (`xreadgroup ">"` nunca relê;
  `xautoclaim` existe só nos LICOES; consumer sem try/except morre e pula a mensagem).
- **Dois relays ausentes** (checkout `pedido.criado`, quiz `quiz.completado`) — leads
  espera os dois: carrinho abandonado e quiz completado são invisíveis.
- Corrida do `place_order` (B4): double-click pode gerar 500 ou pedido eternamente
  `aguardando_pagamento` com matrícula sob `order_id` fantasma.
- Webhook: assinatura não cobre o `status` (corpo não assinado), `data.id` da query
  nunca comparado com o do corpo, `ts` sem janela de frescor.
- Sem caminho de reembolso/chargeback (enums existem; nenhum código os escreve).
- **Checkout nunca ligado para produção** — 4 quebras independentes (rota Traefik,
  tokens, estáticos, `window.API_BASE` indefinido): ninguém consegue COMPRAR.

**Alvo:** tempo-até-detecção de qualquer divergência: **minutos** (é honestamente um
50–100x, não 10x). E os caminhos de falha conhecidos, fechados.

**Movimentos (em ordem de dependência):**
1. (SEU, 5 min) Copiar o compose para a VPS — nada abaixo vale sem isso (H11).
2. Despacho **relays + PEL**: os dois relays que faltam + `try/except` no laço do
   consumer + `xautoclaim` na partida + alarme de PEL envelhecida. Um pacote — é a
   mesma região de código.
3. Despacho **checkout-produção**: as 4 quebras, com reprodução em ambiente prod-like
   como evidência (não "deveria funcionar").
4. Despacho **reconciliação**: um comando que responde *"Intents approved sem
   Matricula? OutboxEvents com published_at nulo? PEL > N minutos?"* — agendado
   1×/dia com alarme (issue automática, o padrão do `alarme-main`). É o item que
   transforma TODOS os outros bugs de "silenciosos" em "avisados".
5. Despacho **webhook**: comparar `data.id` query↔corpo, janela de `ts`, e
   `GET /v1/payments/{id}` (o webhook real do MP não traz `data.status` — sem isso o
   critério 2 da Fase D falha em silêncio, com 200 para o MP).
6. Despacho **place_order**: criar o `Order` antes da chamada externa, na transação,
   `except IntegrityError` → 409.
7. Backup automático dos 8 Postgres + **um restore testado** (ausente de tudo;
   "rollback de código não devolve dados").
8. Kill switch (suspender cobranças sem derrubar acesso) + monitoramento externo com
   alerta no celular.

---

## ALAVANCA 5 — O gargalo que não é de engenharia: zero vendas, conteúdo em construção

As 4 consultorias foram unânimes e esta sessão não achou nada que as contradiga: **o
modo de falha mais provável do projeto não é webhook furado — é a fortaleza perfeita
que ninguém visita.** E o caminho crítico até o primeiro real provavelmente é o
CONTEÚDO do curso, não a plataforma.

**Movimentos (custo zero de código, começam HOJE, em paralelo a tudo):**
1. Validar demanda com **link de pagamento do Mercado Pago + entrega manual** — o
   primeiro real não precisa passar pelo nosso código.
2. **Pix-only no lançamento** (cartão depois de ~50 vendas): elimina chargeback e
   fraude de cartão em produto digital, e corta metade do caminho de código — o
   G5 (retry de cartão recusado) deixa de ser bloqueador.
3. **Modo concierge** até ~20 clientes: e-mail de acesso manual é aceitável;
   inexistente, não. Definir quem entrega o acesso ao comprador nº 1 e em quanto tempo.
4. Mínimos legais ANTES da venda 1 (CDC art. 49, Decreto 7.962/2013, LGPD; ECA
   Digital se houver menores — cursos de Roblox): advogado + PF/PJ + nota fiscal.
5. A hora do mantenedor rende mais na oferta e no conteúdo do que em qualquer decisão
   de arquitetura restante — as alavancas 1–4 são executáveis por agentes.

---

## O mapa de dependências (o que destrava o quê)

```
HOJE (você):    copiar compose → VPS ─────────────┐
HOJE (você):    aposentar regra serial (Alav.1) ──┤
                                                  ▼
LOTE A (paralelo, células/áreas distintas):
  relays+PEL (leads/eventos)   checkout-produção   webhook (pagamentos)
  guarda-dos-guardas (ci/)     alarme-main muralhas (1 linha)
                                                  ▼
LOTE B:  portão de deploy + sonda    reconciliação+alarme    place_order
                                                  ▼
LOTE C:  particionar ARMADILHAS   painel dados/renderer   make sessao
         backup+restore   e2e em camadas   kill switch
                                                  ▼
FECHAR:  esqueleto na VPS (critério 2) + rollback drill 3-dimensões (critério 3)
         → red-team: só os golpes de dinheiro → PILOTO Pix-only, 1 site, concierge
```

Alavanca 5 corre em paralelo a tudo, desde já.

## O que NÃO fazer (anti-metas, com a mesma força)

- **Não desmontar as 8 células** (congelamento ≠ reversão — decisão registrada).
- **Não criar** célula, rito, constituição ou camada de abstração nova.
- **Não rodar os 10 golpes restantes do red-team agora** — só os de dinheiro, dentro
  do checklist da VPS.
- **Não migrar para GitLab agora** (400 min/mês de CI grátis vs 2.000 no GitHub; e a
  migração custaria mais atenção do que devolve pré-lançamento).
- **Não tornar o repo público enquanto os bugs de dinheiro estiverem abertos** (o
  ARMADILHAS é um mapa dos buracos).
- **Não deixar o orçamento de 15 arquivos decidir arquitetura de novo** — ele já
  eliminou a tabela de dedup do checkout e o relay Huey (as duas viraram dívida cara).
  Regra nova até o portão mudar: estourou por coesão legítima → **pare e avise**,
  nunca funda arquivos para caber.

## Placar honesto (para medir se o plano está funcionando)

| Métrica | Hoje (medido) | Alvo |
|---|---|---|
| Células avançadas por janela de atenção | 1 | 4–6 |
| Tokens de governança por despacho | ~32k | ~8k |
| Tokens por edição de painel | ~34k | ~2k |
| Portões que mordem de verdade | ~6 | ~14 |
| Alegações falsas de automação nos docs | ≥4 conhecidas | 0 |
| Tempo-até-detecção de "pago sem entrega" | reclamação do cliente | minutos (reconciliação) |
| Caminho de compra funcionando na VPS | não (4 quebras) | critério 2 verde |
| Vendas reais | 0 | 1 (por link, antes da plataforma) |
