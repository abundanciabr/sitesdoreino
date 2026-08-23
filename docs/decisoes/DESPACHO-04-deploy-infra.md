# DESPACHO 04 — H11: o compose chega à VPS pelo pipeline, nunca mais à mão

> **Copie tudo abaixo da linha e cole para o agente.**
> Criado em 21/08/2026 · merge: **humano** (toca `.github/`, CODEOWNERS)
> Resolve o item **H11** de `ARMADILHAS.md` §1 e substitui o passo manual H0.1 do
> painel 10X: depois deste despacho, mudou infra no Git ⇒ o robô entrega na VPS.

---

# DESPACHO — infra: sincronizar compose e traefik para a VPS via pipeline

ÁREA: `.github/` (+ docs) — nenhuma célula · WORKTREE: wt-infra-sync

ANTES: leia `ARMADILHAS.md` §1 (H11 — o atrito que este despacho mata), o workflow
`.github/workflows/deploy-celula.yml` INTEIRO (é o padrão de SSH/secrets a seguir),
`infra/provisionamento-vps.sh` (a lista final diz o que a VPS consome),
`INVARIANTES.md` [INV-CI01] (semântica fail-closed) e `CONSTITUICAO.md` Lei 5.
Declaração de abertura (RITOS §1).

## CONTEXTO

`infra/docker-compose.yml` e `infra/traefik/**` são consumidos pela VPS em
`/opt/plataforma/`, mas **nenhum pipeline os entrega** — são copiados à mão (H11).
Consequência real, hoje: o PR #45 criou os consumers de evento no compose e **a
produção continua sem eles**, porque ninguém copiou o arquivo. E o
`deploy-celula.yml` descobre os serviços auxiliares lendo o compose **da VPS** — um
compose desatualizado lá torna o deploy de célula silenciosamente incompleto.

O pipeline JÁ tem tudo que precisa: `VPS_HOST` e `DEPLOY_SSH_KEY` nos secrets, usuário
`deploy`, e o padrão `appleboy/ssh-action` funcionando (runs verdes medidos). Falta só
o workflow.

**Por que assim e não dar acesso SSH a agentes:** Lei 5 — agente não tem chave, por
desenho. O canal do agente para a VPS é o pipeline: auditável, revisado, reversível.
Este despacho completa esse canal para a infraestrutura.

## MISSÃO

Um workflow novo, `.github/workflows/deploy-infra.yml`, que a cada push na `main`
tocando os arquivos de infra sincronize-os para a VPS e aplique — fail-closed.

## ESPECIFICAÇÃO (decisões já tomadas — siga; desvio é issue `arquitetura:`)

1. **Gatilho:**
   ```yaml
   on:
     push:
       branches: [main]
       paths:
         - 'infra/docker-compose.yml'
         - 'infra/traefik/**'
         - '.github/workflows/deploy-infra.yml'
   ```
   O próprio workflow entra nos `paths` **de propósito**: o merge do PR que o cria já
   dispara a primeira sincronização — é ela que finalmente entrega os consumers do
   PR #45 à produção, sem passo manual nenhum. **SEM `workflow_dispatch`** (mesma
   razão do portão de deploy: caminho de entrega que ninguém amarra a commit revisado
   não existe aqui).

2. **Concorrência:** `concurrency: { group: deploy, cancel-in-progress: false }` — o
   MESMO grupo do `deploy-celula`. Dois workflows fazendo SSH na VPS ao mesmo tempo
   (um merge de célula + um de infra) seriam intercalados; o grupo único os enfileira.

3. **O que sincroniza — e o que JAMAIS toca:**
   - Sincroniza: `infra/docker-compose.yml` → `/opt/plataforma/docker-compose.yml`;
     `infra/traefik/` → `/opt/plataforma/traefik/` (o compose monta `./traefik/...:ro`).
   - **NUNCA:** `infra/env/` — os `.env` reais são segredos escritos à mão pelo
     mantenedor (INV-P8); o workflow não lê, não escreve, não lista esse diretório.
     Nem os scripts de provisionamento. Escreva isso em comentário no YAML.

4. **Sequência fail-closed no lado remoto** (um step de validação ANTES de qualquer
   troca, e backup antes de sobrescrever):
   - copiar para caminhos temporários (`docker-compose.yml.new`, `traefik.new/`);
   - `docker compose -f docker-compose.yml.new config --quiet` **na VPS** (valida
     sintaxe E interpolação contra os env/ reais que só existem lá). Falhou ⇒ aborta
     sem trocar nada;
   - backup datado do que está em uso (`docker-compose.yml.bak-<UTC>`; idem traefik);
   - trocar os arquivos; `docker compose up -d` (idempotente — só recria o que mudou);
   - **verificação**: após espera curta (~20s), comparar
     `docker compose config --services` com os serviços em estado `running`;
     divergência ⇒ **exit 1** com `docker compose ps` e `logs --tail 60` dos serviços
     não-rodando impressos, mais a instrução de restauração do backup. Imprimir o
     `docker compose ps` SEMPRE, também no sucesso — é a evidência do run.
   - Transferência de arquivo: `appleboy/scp-action` (mesmo autor da ssh-action já em
     uso) ou streaming via ssh — escolha e justifique em comentário; nada de action
     de terceiro novo além dessa família.

5. **Set de shell:** `set -eu` no script remoto (o padrão da casa; sem `|| true` —
   ARMADILHAS §5.6).

## ALVOS (PERMITIDO ESCREVER)

- `.github/workflows/deploy-infra.yml` (novo)
- `ARMADILHAS.md` (a linha H11 — ver protocolo de status abaixo)
- `RUNBOOK-FASE-D.md` (§7: a linha dos consumers menciona a cópia manual — atualizar)
- `docs/decisoes/DESPACHO-01-consumers-producao.md` (o cabeçalho cita H11 — nota curta)

## FORA DE ESCOPO

- `infra/**` (nenhuma mudança nos arquivos sincronizados — este despacho cria o
  CANAL, não altera a carga)
- `services/**`, `ci/` (o portão de deploy é o card B1, separado)
- Sincronizar `env/` ou qualquer segredo — proibido, não "fora de escopo"
- **NÃO toque em `arquivos/painel-*.html`** (sempre da janela raiz)

## DoD — com a divisão honesta do que é provável ANTES e DEPOIS do merge

**Antes do merge (você prova):**
- YAML validado (`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy-infra.yml'))"`
  ou equivalente) — cole a saída.
- A lógica remota revisada contra a especificação item a item (cole o script final e
  aponte onde cada item 3/4/5 está atendido).
- `python ci/ci.py --apenas muralhas` VERDE na branch — cole inteiro.
- Confirmação explícita, com grep, de que `env/` não aparece em nenhum comando de
  cópia do workflow.

**Depois do merge (o primeiro run é a prova real — deixe PRONTO no corpo do PR):**
- O merge dispara o workflow (o próprio arquivo está nos `paths`). Instrua o
  mantenedor: abrir o run, conferir o `docker compose ps` impresso — devem aparecer
  os serviços auxiliares (`*-consumer`, worker da mensageria) em `running`.
- **Protocolo de status do H11:** no seu PR, atualize a linha H11 para
  "🟡 mecanizado — aguardando prova do primeiro run". Quem confirmar o run verde
  (mantenedor ou sessão seguinte) promove para ✅ com o link do run. NÃO marque ✅
  você mesmo: você não verá o run.

## ORÇAMENTO

≤ 5 arquivos.

## REGISTRE NO HANDOFF (para os próximos despachos)

1. Quando o card B1 (portão de deploy) for implementado, este workflow precisa entrar
   no escopo do portão (ou ter gate próprio) — hoje ele confia no rito de PR + CODEOWNERS.
2. O passo manual H0.1 do painel 10X morre com este despacho — a janela raiz atualiza
   o painel (não você).

--- CONTRATO DE EVIDÊNCIA (não negociável) ---
Seu handoff SÓ vale com saída CRUA colada, nunca descrição: o YAML final, o resultado
da validação, o muralhas inteiro, o grep do env/. Se um item do DoD não pôde ser
provado, escreva NÃO EXECUTADO e o motivo — um DoD honestamente incompleto é útil;
um falsamente completo custa a próxima sessão inteira mais a confiança do mantenedor.
