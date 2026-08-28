# painel/ia — 05. Infraestrutura, CI/CD e Deploy

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Resumo curado — a fonte
> de verdade é `infra/`, `.github/workflows/` e `ci/`. **Nota de segurança:**
> este documento foi escrito depois de uma varredura dedicada por segredos
> reais (IP, tokens, chaves privadas) nos arquivos-fonte, e nenhum foi
> encontrado neles nem foi reproduzido aqui — só nomes de variáveis, nunca
> valores.

## Topologia (uma VPS, sem orquestrador)

Produção é um único `docker-compose.yml`, sem Kubernetes/Swarm: **24
containers** em duas redes Docker — `edge` (Traefik ↔ mundo ↔ células) e
`interna` (tudo ↔ Postgres/Redis). Três containers de infraestrutura:

- **`traefik`** (v3.4) — único ponto que expõe as portas 80/443 do host.
- **`postgres:17`** — um único servidor, mas **um database e um role por
  célula** (isolamento reforçado por `REVOKE ALL ... FROM PUBLIC` — cruzar
  banco de outra célula dá erro do próprio Postgres, não "proibição"
  documental).
- **`redis:7`** — compartilhado como barramento de eventos (Redis Streams) e
  broker do Huey (filas assíncronas); cada célula usa um índice de DB Redis
  próprio (`/0` a `/8`).

**12 células** rodam como servidor HTTP (porta 8000 interna) em imagem
própria (`ghcr.io/.../plataforma-<celula>:<TAG>`), com healthcheck comum em
`/healthz`. **9 processos auxiliares** (consumers de evento, relays, workers
Huey) usam a MESMA imagem da célula-mãe com `command:` sobrescrito, ficam só
na rede `interna` (sem rota pública) — a topologia de rede aplica fisicamente
o "raio de explosão = 1 célula" da Lei 2. O nome do auxiliar sempre começa
com `<celula>-`, e é assim (sem lista fixa) que o deploy descobre o que subir
junto. Três volumes nomeados persistem estado: `pgdata`, `redisdata`,
`letsencrypt`.

## Roteamento (Traefik)

Provider **file-based** (`infra/traefik/dynamic/plataforma.yml`), não Docker
labels — decisão deliberada: rotas ficam revisáveis em PR, sob CODEOWNERS.
Roteamento **por caminho (path-based), multissítio**: um deploy serve N
domínios, rotas casam por `PathPrefix` em qualquer host — só os webhooks do
Mercado Pago e as células `identidade`/`admin` usam `Host(...)` explícito
amarrado a `meshcraft.top` (o `redirect_uri` do Google OAuth e a superfície
administrativa não podem responder em domínio de terceiro apontado para a
VPS — seria matéria-prima de phishing).

Prioridades explícitas: `1` catch-all do `funil` · `10` prefixo de página de
célula (inclui `/mapa-ia`, desde 28/08/2026 — mesmo backend do `admin`, mas
público: ver [INV-P14](01-leis-ritos-e-invariantes.md) e a nota de segurança
no topo deste documento) · `20` API · `100` webhook amarrado a host. TLS em
dois modos: a maioria dos domínios usa Cloudflare na frente (SSL "Full"); só
`meshcraft.top` usa Let's Encrypt direto via `httpChallenge`. Duas cadeias de
headers de segurança coexistem (`seguranca` padrão `DENY`; `seguranca-admin`
com `SAMEORIGIN` em `/admin` e `/mapa-ia`, porque a galeria de painéis
históricos embute HTML em iframe de mesma origem).

Dois testes em `ci/tests/` prova mecanicamente esta tabela a cada PR — sem
eles, uma mudança em `infra/traefik/` não tocaria `services/` e não
dispararia suíte nenhuma: `test_rota_da_compra_existe.py` (mini-interpretador
do matcher do Traefik, prova que `/api/checkout` sempre vence o catch-all)
e `test_rotas_sem_forma_de_locale.py` (prova que nenhum prefixo de rota de
célula colide com um código de idioma).

## Provisionamento

- **`infra/provisionamento-vps.sh`** — único script rodado manualmente pelo
  mantenedor, como root, uma vez por VPS nova: cria usuário `deploy` (única
  porta SSH), endurece SSH, configura UFW (só 22/80/443), instala Docker,
  cria as duas redes externas.
- **`infra/provisionamento-postgres.sql`** — cria os pares role+database
  originais.
- **`infra/provisionar-{admin,aprovadores,identidade,notificacoes,sugestoes}.sh`**
  — passo do mantenedor para ligar uma célula nova/sensível: geram segredos
  locais com `openssl rand`, criam role+database isolados, nunca repetem o
  mesmo valor de token entre pares consumidor→provedor diferentes. **Todos
  idempotentes com "trava de deriva"**: antes de reescrever um `.env`
  inteiro, cada script confere se o arquivo já tem alguma chave que ele não
  sabe gerar — se tiver, para com "PAROU POR SEGURANÇA" em vez de apagar em
  silêncio uma variável que outra célula acrescentou depois.
- **`infra/sincronizar_sites.py`** — mecaniza a Receita R11 (site/domínio
  novo): converge o catálogo de sites/ofertas ao declarado em
  `infra/sites.json`. Deliberadamente tolerante a rodar contra uma imagem
  mais velha que ele mesmo (os workflows de deploy disparam em paralelo, sem
  ordem garantida) — sincroniza o que dá e avisa a pendência em voz alta,
  nunca falha por atraso de imagem; mas reprova alto se o banco não tiver as
  colunas que o modelo espera (migração não rodou).

## Os 6 workflows do GitHub Actions

| Workflow | Trigger | Faz | Required? |
|---|---|---|---|
| **muralhas** | todo PR | `ci/ci.py --apenas muralhas` (cerca de célula + orçamento + guarda de segredos + muralha do painel) + `--apenas testador` (suíte adversarial) | Sim — required check nativo desde 26/08/2026 |
| **ci-celula** | PR e push em `main` | `detectar` (célula tocada) → `rodar` (`make ci` da célula) → `gate` (job terminal `if: always()`, só aceita `skipped` como verde se a detecção concluiu que não há célula nenhuma tocada) | Sim — `ci-celula-gate` é o check exigido |
| **alarme-main** | push em `main` | Guarda de segredos na `main` inteira (não só o diff) + testador; abre/comenta issue `main-vermelha` se falhar | Não — é alarme, não portão |
| **deploy-celula** | push em `main` tocando `services/**` ou `painel/**` | `detectar` → `portao_de_deploy.py` (modo célula) → build+push da imagem (GHCR) → SSH: sobe só os serviços daquela célula | Portão interno faz as vezes de required check |
| **deploy-infra** | push em `main` tocando `infra/docker-compose.yml`, `infra/traefik/**`, `infra/sites.json`, `infra/sincronizar_sites.py` | `portao_de_deploy.py` (modo infra) → valida config, backup datado, troca arquivos, `up -d`, confere tudo `running`, roda sincronização de sites + smoke HTTP real (200 na raiz de cada host) | Portão interno |
| **rollback** | manual (`workflow_dispatch`) | `ci/rollback.py` valida (célula no manifesto; alvo é `main` ou sha ancestral; imagem existe) → SSH aplica só naquele `docker compose up -d`, sem persistir | Portão interno |

Nota histórica: como o repositório é privado numa conta pessoal, o GitHub por
muito tempo não ofereceu required checks nativos — por isso os "portões"
substitutos em Python (`mergear.py`, `portao_de_deploy.py`). Desde
26/08/2026 um ruleset nativo "main protegida" foi ligado (`muralhas` +
`ci-celula-gate` como required), mas os scripts continuam como segunda
camada, porque **nenhum required check nativo olha o deploy** — ele roda
depois do merge.

## Os scripts de `ci/` — muralhas, portões e ferramentas

Todos compartilham `ci/_nucleo.py`: a semântica de 4 estados **PASS · SKIP ·
FAIL · ERROR** que atravessa o repositório inteiro ([INV-CI01] — "ausência de
evidência nunca é evidência de sucesso"). Um portão que não conseguiu medir
devolve ERROR, nunca PASS.

| Script | Categoria | Faz |
|---|---|---|
| `_nucleo.py` | núcleo | `Estado`/`Resultado`/`Relatorio`, resolução fail-closed da raiz do repo, execução de subprocesso onde qualquer anomalia vira erro de instrumentação |
| `ci.py` | orquestração | Runner canônico local (`python ci/ci.py`); agrega freeze + muralhas + guardas + testador + `make ci` opcional de uma célula |
| `cerca-de-celula.sh` | muralha/PR | "1 PR = 1 célula": reprova diff tocando `services/` de mais de uma célula; exige label `contrato` se `contracts/` mudar |
| `orcamento-de-mudanca.sh` | muralha/PR | Teto de 15 arquivos por PR (label `arquitetural` libera; lane `traducoes` libera lotes restritos a dado) |
| `guarda-de-segredos.sh` | muralha/PR + alarme | `git grep` na árvore inteira por credencial de produção do Mercado Pago e cabeçalho de chave privada; confere que arquivos-molde mantêm `TROQUE_` |
| `muralha-do-painel.sh` | muralha/PR | Confere `painel/manifesto.js` em dia com `painel/registros/` e os testes-guarda em JS do painel |
| `contract_freeze.py` | muralha de contrato | Compara schema OpenAPI vivo × congelado; sonda a autenticação efetiva na fonte (django-ninja omite `security` em vez de emitir `[]` — cegueira que só a sonda pega) |
| `guarda_dos_guardas.py` | muralha/PR | Prova que `INVARIANTES.md` e o disco não divergem: todo teste-guarda citado existe e ainda morde (sem skip/xfail/corpo vazio) |
| `muralha_pasta_compartilhada.py` | hook do harness | Recusa edição/git-de-estado quando a sessão roda no clone principal (não é CI de PR, é hook local) |
| `mergear.py` | merge | Confere checks, labels, dívida do livro; mergeia via `gh pr merge`; **confere de novo no GitHub** que o estado virou `MERGED` — nunca confia no exit code do comando |
| `divida_do_livro.py` | merge/painel | Lista PRs mergeados sem registro citando o número, com graça de 90min |
| `indice_de_armadilhas.py` | documentação | Gera `armadilhas/INDICE.md`; reprova (ERROR) se dois arquivos colidirem no mesmo número |
| `doctor.py` | diagnóstico | Read-only: "este ambiente consegue rodar o trabalho?" — nunca conserta nada |
| `sessao.py` | bootstrap | Único script de `ci/` que escreve no mundo: cria worktree, venv, sobe Postgres/Redis com porta derivada da célula, roda baseline, só imprime a declaração de abertura se tudo passar |
| `portao_de_deploy.py` | deploy | Ver seção abaixo |
| `rollback.py` | deploy | Ver seção abaixo |
| `cross-smoke.sh` | teste | Só para `pagamentos`: se o diff mexe num método de pagamento, roda os testes de smoke do método oposto |
| `manifesto-de-contratos.json` | config | Lista autoritativa: qual célula tem contrato `required` vs `not-applicable` (com motivo obrigatório) |
| `guardas-nao-declarados.txt` | config | "Dívida catraca" de guardas que existem mas ainda não viraram invariante numerado — só encolhe |

`ci/tests/` (~23 arquivos, rodados por `--apenas testador` em todo PR e todo
push à `main`) **não testam o produto — testam os próprios portões**: cada
um monta um repositório falso em `tmp_path` e prova que o instrumento
reprova quando deveria (sabotagem deliberada) e passa quando deveria.

## Deploy e rollback, em detalhe

**`ci/portao_de_deploy.py`** é o substituto do required check que faltava:
antes de qualquer build/SSH, consulta a API do GitHub e espera os workflows
`ci-celula` e `alarme-main` concluírem `success` no commit, **e** `muralhas`
concluir `success` no PR de origem. `skipped`/`cancelled`/ausência não é
verde — só `success` explícito conta. Também varre o mesmo SHA por qualquer
outro workflow que tenha ficado vermelho fora da lista conhecida.

**`ci/rollback.py`** (único caminho `workflow_dispatch` do repositório) prova
três coisas antes de qualquer SSH: célula está no manifesto; alvo é `main`
ou sha comprovadamente ancestral via `git merge-base` (logo, um commit que já
passou pelo portão de deploy); imagem existe no registry. O pin **não
persiste** — o próximo deploy normal volta a `:main` sozinho. Isto mecaniza a
Lei 5 (2h da manhã): reverter produção deixa de depender de acordar o
mantenedor para colar comando SSH.

## Harness end-to-end (`e2e/esqueleto.sh`, via `make esqueleto`)

Sobe um compose próprio (só 4 células, buildadas do código LOCAL, não das
imagens de produção) e percorre via `curl` puro a transação de compra
inteira em 8 elos sequenciais, cada um ✅/❌: seed → sessão → pedido →
cobrança (Pix real contra a **sandbox real** do Mercado Pago) → webhook
(simulado mas assinado como um real) → outbox → relay → matrícula. Design
deliberadamente honesto: se um elo falhar por célula não implementada, o
script falha alto mesmo assim — "verde fabricado" nunca é o objetivo. **Gap
conhecido:** apesar da doutrina inicial prometer isso, o harness **não roda
dentro do CI automatizado** — só localmente (`RUNBOOK-FASE-D.md` já
documenta esse gap). Ver [07 — oportunidades](07-oportunidades-e-fronteiras.md).

## Integrações externas por célula (nomes de variável, nunca valores)

| Célula | Integração | Variáveis |
|---|---|---|
| `identidade` | Google OAuth (login do site) | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| `sugestoes` | Google OAuth (mesmo app) | idem |
| `pagamentos` | Mercado Pago — cobrança real | `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET` |
| `checkout` | Mercado Pago — só a chave pública (client-side, não é segredo) | `MP_PUBLIC_KEY` |
| `mensageria` | SMTP (e-mail transacional) | `SMTP_HOST/PORT/USER/PASSWORD/FROM` |
| `mensageria` | Gateway de WhatsApp | `WHATSAPP_GATEWAY_URL/TOKEN` |
| demais 7 células | só APIs internas entre células (tokens por par consumidor→provedor) | — |
| *(infra)* | Cloudflare, Let's Encrypt/ACME, GHCR | configurados fora de env de célula |

Desenho de isolamento notável: `checkout` (adjacente ao dinheiro, de frente
para o navegador) **nunca vê** a credencial secreta do Mercado Pago — só a
chave pública. A credencial secreta de produção existe em um único lugar no
universo do projeto: um arquivo `.env` escrito manualmente pelo mantenedor
diretamente na VPS, nunca visto por agente, nunca no Git — reforçado
mecanicamente por `guarda-de-segredos.sh`.

## O que este documento verificou e NÃO reproduz

Uma varredura dedicada confirmou: todos os `infra/env/*.env.exemplo` (12
arquivos) têm só placeholders; todas as senhas em
`infra/provisionamento-postgres.sql` são placeholders; nenhum workflow tem
segredo em texto puro (tudo via `${{ secrets.* }}`); nenhum IP real aparece
em nenhum arquivo versionado; a chave privada de deploy (`deploy_ci`, sem
`.pub`) está corretamente fora do controle de versão. O único IP real do
projeto (o da VPS) existe fora deste mapa, propositalmente — ver a nota de
segurança em [02 — armadilhas](02-armadilhas-e-padroes-recorrentes.md).
