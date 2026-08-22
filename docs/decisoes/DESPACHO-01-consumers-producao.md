# DESPACHO 01 — consumers de evento em produção

> ## ✅ EXECUTADO — PR #45, mergeado em 21/08/2026. NÃO redespache.
> Entregou os 4 consumers + worker Huey + healthchecks + o deploy descobrindo os
> auxiliares do próprio compose. **Duas ressalvas que seguem abertas** (ARMADILHAS §1):
> **H11** — ~~o compose NÃO chega à VPS por pipeline~~ **mecanizado pelo despacho 04**
> (`.github/workflows/deploy-infra.yml`) e **✅ provado em 22/08/2026**: run
> 32538231311 verde — estes consumers e o worker Huey estão em `running` na produção.
> **H10** — dois remendos moram no compose (healthcheck TCP do checkout; bootstrap Huey
> da mensageria) até as correções de célula saírem em PRs próprios.
>
> ~~Copie tudo abaixo da linha e cole para o agente.~~
> Criado em 21/08/2026 · merge: **humano** (toca `infra/` e `.github/`, ambos CODEOWNERS)

---

# DESPACHO — infra: subir os consumers de evento em produção

CÉLULA: nenhuma (infraestrutura) · WORKTREE: wt-infra-consumers · RECEITAS: R4 (referência)

ANTES: leia `ARMADILHAS.md` (raiz), com atenção especial a **§3.13** (dois containers
rodando `migrate` ao mesmo tempo) e §3.12 (CRLF em `.sh`). Ao terminar, acrescente o que
aprendeu; o que só o mantenedor resolve vai na tabela §1 do `ARMADILHAS.md` **e** no seu
relatório final. Declaração de abertura (RITOS.md §1) antes de tocar qualquer arquivo.

## CONTEXTO (o achado que motiva este despacho)

`infra/docker-compose.yml` — o compose que roda no servidor — sobe **um único container
por célula: só o servidor HTTP**. O `CMD` dos Dockerfiles é
`migrate --noinput && uvicorn ...`.

Os processos que **consomem** eventos existem **apenas** em `e2e/docker-compose.e2e.yml`
(`checkout-consumer`, `alunos-consumer`). Medido:

```
grep -cE "consumer|huey|consume_eventos" infra/docker-compose.yml   →  0
```

Consequência em produção: cliente paga → webhook valida → outbox grava → `relay_outbox()`
publica em `eventos.pagamento.aprovado` no Redis → **ninguém lê o stream**. Sem matrícula,
sem e-mail, e `GET /pedidos/{id}` fica em `aguardando_pagamento` para sempre. É por isso
que `make esqueleto` passa 8/8 e a produção não funcionaria: **o e2e testa uma topologia
que não existe no servidor**.

Nenhuma linha de código de célula precisa mudar. O que falta é infraestrutura.

## MISSÃO

Fazer o compose de produção subir os processos consumidores que já existem no código, e
garantir que o deploy por célula continue atualizando todos eles.

## ALVOS (PERMITIDO ESCREVER)

- `infra/docker-compose.yml`
- `.github/workflows/deploy-celula.yml`
- `ARMADILHAS.md` (acrescentar o que aprender)

## SOMENTE-LEITURA

`e2e/docker-compose.e2e.yml` (é o modelo pronto — copie o padrão dele),
`services/*/Dockerfile`, `infra/env/*.exemplo`, `RITOS.md`, `CONSTITUICAO.md`

## FORA DE ESCOPO

- Qualquer arquivo em `services/**` — nenhuma célula muda neste despacho.
- Os relays ausentes de `checkout` e `quiz` (são outro despacho — não os implemente aqui).
- O portão de deploy que consulta checks (outro despacho).
- Backup, reconciliação, kill switch (outros despachos).
- **NÃO toque em `arquivos/painel-fundacao.html`** — isso é sempre da janela raiz.

## O QUE PRECISA EXISTIR

### 1. Quatro consumers (as 4 células que têm `consume_eventos.py`)

Confirmado em disco: `alunos`, `checkout`, `leads`, `mensageria`.

Cada um: mesma imagem da célula, **`command:` sobrescrito** para
`python manage.py consume_eventos`, mesmo `env_file`, `restart: unless-stopped`.

**[ARMADILHAS §3.13] Só UM container por célula pode migrar.** O `command:` sobrescrito
já resolve isso (não roda `migrate`) — mas confirme que a sobrescrita realmente elimina o
`CMD` do Dockerfile, e não o complementa.

### 2. Um worker Huey para `mensageria`

Só `mensageria` usa Huey (`services/mensageria/config/huey.py`, `huey` no
`requirements.txt`). Sem worker, a receita R8 (retry de envio) nunca executa. Descubra o
comando correto lendo a configuração da célula — não invente.

### 3. Healthcheck nas células

Hoje `infra/docker-compose.yml` tem **um** healthcheck no repositório inteiro (o do
`postgres`). Sem healthcheck na célula, o consumer não tem como esperar o `migrate`
terminar, e `docker compose ps` retorna sucesso com container em crash-loop.

Acrescente healthcheck ao bloco âncora `x-celula: &celula` (sondando `/healthz`) e faça
cada consumer depender da sua célula com `condition: service_healthy`.

**Verifique antes:** confirme que as 8 células realmente expõem `/healthz` — não presuma.
Se alguma não expuser, relate em vez de improvisar.

### 4. O deploy precisa atualizar o consumer junto

`.github/workflows/deploy-celula.yml:63` faz `docker compose up -d ${{ matrix.celula }}`.
Isso sobe **só a célula**. Depois deste despacho, um deploy de `alunos` atualizaria
`alunos` e deixaria `alunos-consumer` **rodando a imagem antiga, em silêncio** — versões
divergentes do mesmo código, sem alarme.

Corrija para que o deploy suba a célula **e** os processos auxiliares dela, de forma que
funcione tanto para as células que têm consumer quanto para as que não têm. Não
hardcode uma lista que vai envelhecer sem ninguém perceber.

## DoD

- `docker compose -f infra/docker-compose.yml config` válido, com os 4 consumers, o
  worker de `mensageria` e o healthcheck das células — **cole a saída**.
- Prove que o `command:` sobrescrito **não** roda `migrate`: mostre a linha do config
  renderizado para pelo menos um consumer.
- Prove que o deploy alcança o consumer: mostre o comando final e explique, em uma frase,
  por que ele funciona para `funil` (sem consumer) e para `alunos` (com consumer).
- `python ci/ci.py` verde na raiz — **cole a saída completa, sem resumir**.
- Nenhum arquivo em `services/**` no diff (`git diff --name-only origin/main...HEAD`).

## ORÇAMENTO

≤ 5 arquivos. Se passar disso, **pare e avise antes de continuar** — este despacho é
pequeno de propósito.

## EVIDÊNCIA

Saída completa de `docker compose config` + `python ci/ci.py`, e o diff do workflow de
deploy. Handoff completo ao final (RITOS.md §1): branch, arquivos, resultado, pendências,
pronto para PR ou não.

## LIMITE HONESTO DESTE DESPACHO — declare no handoff

Isto faz os consumers **existirem** em produção. **Não** prova que funcionam lá: o
`make esqueleto` roda contra o compose de e2e, não contra a VPS. A prova real é o critério
2 do `ESQUELETO-QUE-ANDA.md` (transação na VPS com webhook real), que continua pendente.

Não escreva "consumers funcionando em produção" no handoff. Escreva o que você mediu.
