# ARMADILHAS — o que já custou tempo neste repositório

> Documento **vivo**. Cada entrada aqui é tempo que um agente já perdeu — e que o
> próximo não precisa perder. Leia antes de começar; acrescente ao terminar.

**Existe para uma coisa só: impedir que o mesmo problema seja resolvido do zero em
toda tarefa.** Cada redescoberta custa tokens, custa rodadas de teste e atrasa o
despacho. Se você gastou mais de dois minutos entendendo algo que não era a sua
tarefa, isso pertence aqui.

## Como usar (agente)

1. **Antes de codar:** leia o §1 (precisa de você) e o §2 (partida rápida), e dê um
   Ctrl+F pela tecnologia que vai tocar (`django-ninja`, `importlinter`, `respx`,
   `middleware`, `mypy`…).
2. **Quando bater de frente com algo:** procure a mensagem de erro crua aqui. As
   entradas começam pelo **sintoma** justamente para serem encontradas assim.
3. **Ao terminar o despacho — isto não é opcional:** acrescente o que você aprendeu,
   no formato `Sintoma → Causa → Solução → Origem`. Não crie seção nova se já existir
   uma que sirva. Entrada sem sintoma concreto não ajuda ninguém: descreva o erro real,
   não a lição abstrata.
4. **Se a solução definitiva não estiver nas suas mãos** — depende de instalar algo na
   máquina, de uma conta paga, de uma permissão, de uma decisão de arquitetura —
   **registre no §1 E avise o humano no seu relatório final, em texto claro.** Você
   contorna hoje para não travar; ele resolve de vez quando puder. Contornar em
   silêncio é o que faz o mesmo atrito voltar no próximo despacho, e no seguinte.

## Onde cada coisa mora (para não duplicar)

| Documento | Público | Guarda |
|---|---|---|
| `CONSTITUICAO.md` + `constituicoes/` | agentes | o que é **proibido** |
| `CAMINHO-DOURADO.md` | agentes | como fazer **certo** (receitas) |
| `INVARIANTES.md` | agentes | o que **não pode quebrar** |
| **`ARMADILHAS.md`** (este) | **todo agente, qualquer célula** | o que a **realidade cobrou** — vale em qualquer tarefa |
| `services/<celula>/LICOES.md` | agente **daquela** célula | decisões e armadilhas **só** daquela célula |
| `arquivos/painel-*.html` | **o humano** | status, fila, roadmap, incidentes |

Regra de bolso: **se serve para qualquer célula, é aqui. Se só faz sentido dentro de
uma célula, é no `LICOES.md` dela.**

> **Por que estes documentos são versionados e os painéis não:** um agente trabalha
> dentro de um `git worktree`, e worktree só contém arquivo rastreado. A pasta
> `arquivos/` está no `.gitignore` — ela **não existe** dentro do worktree, o agente
> não consegue abrir os painéis nem se quiser. Conhecimento destinado a agente
> precisa estar no git; painel é para o humano, e por isso fica de fora.

---

## §1 — PRECISA DE VOCÊ (humano) — atritos que só você resolve de vez

Cada linha aqui é um atrito que **todo agente contorna, toda vez**. O contorno
funciona, mas custa tempo e tokens em cada despacho. Resolver na raiz é de uma vez
para sempre.

| # | O atrito (o que acontece hoje) | O que resolveria de vez | Estado |
|---|---|---|---|
| H1 | ~~`python3` era o stub da Microsoft Store ⇒ `make contrato-check` dava **"OK" falso**~~ | Shim `~/bin/python3` resolveu **a máquina**; o **portão** foi resolvido reescrevendo a lógica em Python, fail-closed por construção (PR #21 endureceu o Bash, PR #22 tirou a medição do Bash) | ✅ **resolvido 19/08/2026** — provado nos três estados: igual ⇒ PASS, divergente ⇒ FAIL, instrumento quebrado ⇒ ERROR (§3.2) |
| H2 | ~~`make` instalado mas invisível para o Bash do agente ⇒ todo comando virava `bash -lc`~~ | Pasta do `make` no PATH **do usuário** (Windows) | ✅ **resolvido 19/08/2026** — `make` roda direto, sem `-l` e sem `export PATH` |
| H3 | **Nenhum check é obrigatório para mergear.** Medido em 19/08/2026: a API responde `Upgrade to GitHub Pro or make this repository public` (HTTP 403). Todos os portões podem estar vermelhos e o botão de merge continua funcionando; `.githooks/pre-push` só barra push direto para `main` **desta** máquina, e não vê merge feito pelo site | GitHub Pro **ou** tornar o repositório público — as duas liberam required checks. Confirmado na documentação: **não há caminho grátis** para repo privado (rulesets exigem Team/Enterprise) | 🟡 **o MERGE segue sem proteção (impossibilidade de pagamento — NÃO é decisão de custo), mas desde 22/08/2026 o DEPLOY é protegido: a saída (A) está implementada E PROVADA — ver a atualização no fim desta célula.** Atualizado em 21/08/2026: o cartão de crédito do mantenedor **não é aceito pelo GitHub** e não há outra forma de pagamento disponível. GitHub Pro está descartado por impossibilidade, não por preferência — **não recomende "assine o Pro" ao mantenedor, essa porta está fechada.** (O registro anterior dizia "decisão de custo adiada enquanto o projeto não fatura"; era o entendimento da época e está incorreto.) Saídas reais, das quais só a primeira é imediata: **(A)** portão no workflow de deploy consultando `gh api repos/<owner>/<repo>/commits/<sha>/check-runs` e abortando se algo não estiver verde — grátis, mecânico, viabilidade confirmada em 21/08/2026; protege a VPS e o cliente, **não** a `main`; cuidado: `skipped` NÃO é verde (INV-CI01, §5.6). **(B)** migrar para GitLab, cujo plano gratuito teria branch protection em repo privado — **não verificado por nenhuma sessão, confirme antes de mover**. **(C)** tornar o repositório público — libera a proteção no plano grátis, mas publicaria este próprio arquivo, que é um mapa dos buracos abertos; só considerar depois de fechados os bugs de dinheiro, e exigindo varredura de segredos no histórico completo (`gitleaks`/`trufflehog`) antes. Enquanto A não existir: `python ci/mergear.py <PR>` recusa merge com check vermelho e `alarme-main` abre issue se a `main` quebrar — degraus da Escada da Imposição (RITOS.md §2), não substitutos (§5.9). É o que impede afirmar "CI fail-closed global" ([INV-CI01]). Análise completa: `docs/decisoes/SINTESE-E-PLANO.md` §1. **Atualização 22/08/2026 — a saída (A) EXISTE E ESTÁ PROVADA AO VIVO:** `ci/portao_de_deploy.py` + job `portao-de-deploy` nos DOIS workflows de deploy (PR #54, card B1; desenho em `docs/decisoes/PROJETO-PORTAO-DEPLOY.md`; 25 testes adversariais em `muralhas`/`alarme-main`). A prova, quatro saídas cruas no mesmo dia: PR #55 vermelho de propósito (`ci-celula: fail`) → mergeado pelo caminho sem guarda → run 32567765127: `portao-de-deploy: failure`, `deploy: skipped` (imagem intocada — o build mora no job pulado) → revert #56 verde → run 32567900961: portão `success`, deploy do quiz executado e `healthy` na VPS. O clique do botão continua livre; o que ele não alcança mais é a produção |
| H4 | Docker Desktop frio no início da sessão custa 1–2 min parados | Deixar o Docker Desktop iniciar junto com o Windows | 🔴 aberto |
| H5 | ~~`make esqueleto` local para no elo "cobrança": a intent Pix chama a API REAL da Mercado Pago (`services/pagamentos/pagamentos/providers/mercadopago/client.py`, `_BASE_URL` fixo, sem modo mock) mesmo em dev — só o webhook é simulado (ESQUELETO-QUE-ANDA.md). Sem uma credencial sandbox de verdade, a MP responde erro e a intent fica com `provider_payment_id` vazio~~ | Credencial `MP_ACCESS_TOKEN` (TEST-... sandbox real, nunca APP_USR-) de uma conta Mercado Pago Developers, colocada em `e2e/.env.e2e` (git-ignorado — ver `e2e/.env.e2e.exemplo`) | ✅ **resolvido 21/08/2026** — o mantenedor guarda essa credencial fora do repo (correto, INV-P8), num compartilhamento de rede pessoal; qualquer sessão futura que precise rodar `e2e/esqueleto.sh` local deve **pedir ao mantenedor onde está a credencial de teste** em vez de tentar gerar uma nova. **Nunca escreva o valor do token em nenhum arquivo versionado** (nem aqui) — só o `e2e/.env.e2e` local, git-ignorado. Com o token real, elos 1-7 (seed→sessão→pedido→cobrança→webhook→outbox→relay) rodaram verdes de ponta a ponta contra containers reais e a MP sandbox de verdade (`mp_payment_id` retornado por ela, não simulado) |

| H6 | ~~`python ci/mergear.py <PR>` confere tudo verde e então falha ao mergear de verdade: `gh pr merge <PR> --merge --yes` estoura `unknown flag: --yes` — o `gh` instalado nesta máquina (`gh version 2.97.0`) não tem essa flag para `pr merge`~~ | A correção escolhida (22/08/2026): `ci/mergear.py` deixou de usar `--yes` (`comando_de_merge()` monta o comando sem a flag), o stdin de TODO subprocesso de portão passou a ser fechado por construção (`_nucleo.executar`, `stdin=DEVNULL` — sem TTY o `gh` não faz segunda pergunta, age direto), e a conferência pós-merge (`state=MERGED` consultado no GitHub) ficou embutida no script | ✅ **resolvido 22/08/2026** — teste-guarda `test_comando_de_merge_nao_usa_yes` impede a flag de voltar; evidência vermelho→verde no PR do despacho governança/merge-pelo-agente; detalhe em §5.9.1 |
| H7 | `POST /intents` e `POST /intents/{id}/card` passaram a devolver **502** quando o Mercado Pago falha (antes devolviam 201 mentiroso). O 502 **não está no contrato congelado** — `contracts/pagamentos.openapi.yaml` lista só 201/200/401/422 — porque mudar o contrato é Rito de Contrato (RITOS §3), que exige sessão de arquitetura com o mantenedor e PR só de `contracts/` com a label `contrato`. Um agente de célula não pode fazer isso sozinho | Duas coisas, ambas em arquivo CODEOWNERS: (1) documentar `502` nas duas operações do contrato de pagamentos, pelo Rito §3; (2) decidir sobre o invariante novo proposto — *"resposta de provedor só vira sucesso interno após validação de status e payload"* — em `INVARIANTES.md` | 🔴 **aberto** — o código já falha fechado e está testado (PR do despacho 03); o que falta é só o registro formal. Enquanto não acontecer, o checkout precisa tratar 502 como "tente de novo com a mesma chave", e nenhum documento diz isso a ele |
| H8 | O e2e (`e2e/esqueleto.sh`) só roda **manualmente**: `grep -rn "esqueleto\|e2e" .github/` não devolve nada. E ele exige `MP_ACCESS_TOKEN` sandbox real (`docker-compose.e2e.yml:69` usa `${MP_ACCESS_TOKEN:?}`, que **recusa subir** sem ela) — logo é inexecutável em CI por construção. Nenhum PR é barrado hoje por quebrar o caminho ponta a ponta, apesar de `ESQUELETO-QUE-ANDA.md` afirmar que ele "roda no CI a cada PR de célula" | Colar o `MP_ACCESS_TOKEN` **sandbox** (`TEST-...`) em *Settings → Environments → Secrets* do GitHub, num environment protegido por *required reviewers* (compatível com INV-P8, que proíbe `APP_USR-` fora da VPS, não `TEST-`). Isso destrava a camada de e2e contra a MP real, agendada 1×/dia — as camadas mockadas por PR não dependem disso | 🔴 aberto — decisão do mantenedor |
| H9 | ~~**A Lei 4 (Separação de Poderes) é inexecutável, e não por falta de plano pago.** `gh api repos/<owner>/<repo>/collaborators` devolve **um único colaborador**, e o GitHub **proíbe aprovar o próprio PR**. Logo, exigir "revisão do dono" nos caminhos CODEOWNERS travaria todo PR para sempre — mesmo se a branch protection existisse. Medido: os PRs #38–#42 têm `reviews=0`, todos~~ | A saída escolhida NÃO foi a segunda conta revisora: em 22/08/2026 o mantenedor decidiu que **mergear é trabalho do agente**, e a Lei 4 foi reescrita — a aprovação humana prévia saiu do fluxo (era simultaneamente inexecutável E o maior gargalo medido: mediana 22 min, média 264 min por merge — PLANO-10X Alavanca 1); no lugar entraram mandato do despacho + anúncio nominal de merge em caminho CODEOWNERS + o portão de deploy provado (H3) como rede | ✅ **resolvido por decisão em 22/08/2026** — `docs/decisoes/DECISAO-merge-pelo-agente.md`; a Lei 4 deixou de ser prosa inexecutável |

| H10 | Duas correções de **código de célula** que o despacho "consumers em produção" só pôde **contornar**, porque `services/**` estava fora do escopo dele — e as duas ficam em caminho CODEOWNERS, logo dependem de você despachar e mergear. **(1) `checkout`:** `GET /healthz` responde **404** com o ambiente de produção — medido em 21/08/2026 (§4.10); o healthcheck dessa célula teve de virar sonda de TCP em `infra/docker-compose.yml`. **(2) `mensageria`:** não existe entrypoint de Huey na célula (§4.11), então o worker sobe por um bootstrap de 6 linhas embutido no `command:` do compose | **(1)** uma linha em `services/checkout/apps/core/middleware.py`: `request.path` → `request.path_info`. **(2)** `huey.contrib.djhuey` em `INSTALLED_APPS` (destrava `manage.py run_huey`) ou um management command próprio. Duas tarefas de célula normais, 1 PR cada, ambas pequenas | ✅ **resolvido 22/08/2026 (lote "ligar o checkout")** — as células foram corrigidas nos PRs do lote (checkout: `request.path_info`; mensageria: `djhuey` + `run_huey`) e o PR de infra do mesmo lote removeu os dois remendos do compose: o healthcheck do `checkout` voltou a ser o HTTP `/healthz` herdado e o `mensageria-huey` virou `command: python manage.py run_huey` — a convenção do lote é que TODO worker Huey sobe assim |

| H11 | **`infra/docker-compose.yml` não chega à VPS por pipeline nenhum.** `grep -rn "docker-compose" .github/` só encontra o `cd /opt/plataforma` do deploy: o arquivo é copiado **à mão** (passo 1 da lista final de `infra/provisionamento-vps.sh`). Consequência: todo PR que muda o compose — inclusive o que criou os consumers de evento — **não muda nada em produção** até você copiar o arquivo para lá. Não existe alarme para a divergência entre o compose do Git e o do servidor | Mecanizar: um passo no `deploy-celula` (ou um workflow próprio disparado por `paths: ['infra/**']`) que envie o compose para `/opt/plataforma/` antes do `up`. É a Lei 1 — hoje esta regra está no degrau "documento", o mais fraco da escada | 🟡 **mecanizado — aguardando prova do primeiro run** (despacho 04): `.github/workflows/deploy-infra.yml` sincroniza compose+traefik para `/opt/plataforma/` a cada merge na `main` que os toque, fail-closed (valida na VPS antes de trocar, backup datado, verificação de serviços rodando). O merge do próprio PR dispara o primeiro run — é ele que entrega os consumers do PR #45 à produção. Quem confirmar o run verde (mantenedor ou sessão seguinte) promove esta linha para ✅ **com o link do run**; a evidência é o `docker compose ps` impresso no run, com os `*-consumer` e o `mensageria-huey` em `running`. **1º run (21/08/2026, run 32538231311): VERMELHO — mas o canal em si funcionou:** staging, validação contra os `env/` reais, backup datado e troca dos arquivos aconteceram (o compose e o traefik do Git **JÁ estão** em `/opt/plataforma/`); morreu no `up -d`, em `unauthorized` do ghcr — causa **fora** do workflow: a VPS nunca fez `docker login` (ver **H13**). **✅ RESOLVIDO 22/08/2026 — primeiro run VERDE na 3ª tentativa do mesmo commit:** <https://github.com/abundanciabr/sitesdoreino/actions/runs/32538231311>. O `docker compose ps` impresso no run mostra os **16 serviços** declarados em `running`: as 8 células (todas `healthy`), os 4 `*-consumer`, o `mensageria-huey`, mais traefik (80/443 publicados), postgres e redis — **a plataforma subiu em produção pela primeira vez, com os consumers do PR #45 no ar**. As tentativas 1 e 2 reprovaram honesto (1ª: H13/ghcr; 2ª: env sem `DJANGO_SECRET_KEY`, preenchido pelo mantenedor em 22/08). O canal está provado: compose e traefik chegam à produção só por merge na `main` |
| H12 | O alvo `contrato-check` das 8 células decide pelo **disco** (`if [ -f ../../contracts/$(CELULA).openapi.yaml ]`) em vez do manifesto — é a linha "não conforme" da tabela do [INV-CI01]. **A correção já existe em `celula-template/Makefile`; nenhuma das 8 células a usa.** Efeito: apagar um contrato deixa o `make ci` local da célula **verde**, e é esse baseline que o agente usa para decidir se pode trabalhar (mitigado no CI: `test_manifesto_real_e_coerente_com_o_repositorio` reprova em `muralhas` e em `alarme-main`) | Decidir se a correção entra **de uma vez** (1 linha × 8 arquivos + 1 teste que proíba o `if [ -f`, cabe no orçamento) ou por célula, junto de outro trabalho | 🟡 mitigado no CI, aberto localmente |
| H13 | **A VPS não consegue puxar NENHUMA imagem do ghcr: `docker login` nunca foi feito lá** (o provisionamento não tinha esse passo). Medido em 21/08/2026: o 1º run do `deploy-infra` (32538231311) morreu em `error from registry: unauthorized` — e precisou tentar puxar até `traefik:v3.4` (imagem pública), prova de que o Docker local da VPS está **vazio**: a plataforma nunca subiu nesta VPS. Pior: os runs "verdes" do `deploy-celula` até 21:51 daquele dia rodavam o script **antigo** (sem `set -eu`, sem `--wait`) — o run do PR #47 mostra o MESMO `unauthorized` no pull E no up, um `docker compose ps` **vazio**, e "✅ Successfully executed" no fim, porque o último comando (`ps`) sai com 0. É o falso-verde do §5.6, medido em produção: **nenhum green histórico do deploy-celula provou deploy real**. O push das imagens no runner sempre funcionou (`docker/login-action` + GITHUB_TOKEN): as 8 imagens `plataforma-*:main` existem no registry — o buraco é só o pull do lado da VPS. O script novo do PR #45 já falha honesto daqui em diante | Uma vez, na VPS: entrar como `deploy` e rodar `docker login ghcr.io -u abundanciabr`, usando como senha um PAT (classic) com escopo **read:packages** (fica salvo em `/home/deploy/.docker/config.json`). Depois, re-rodar os jobs falhos: `gh run rerun 32538231311 --failed` — os arquivos já estão lá; o `up -d` finalmente puxa e sobe a plataforma inteira (traefik, postgres, redis, 8 células, 5 auxiliares). Se o rerun reprovar de novo com células caindo por erro de banco, o passo faltante é o `infra/provisionamento-postgres.sql` da lista final do provisionamento. O passo de login entrou na lista de `infra/provisionamento-vps.sh`. Alternativa de arquitetura, se preferir zero segredo de longa duração na VPS: login por run no pipeline, com GITHUB_TOKEN passado via `envs` da ssh-action — decisão sua, issue `arquitetura:` | ✅ **resolvido 22/08/2026** — o mantenedor fez o `docker login` pelo console do provedor (persistido em `/home/deploy/.docker/config.json`); prova: todos os pulls verdes na 3ª tentativa do run 32538231311, plataforma inteira no ar. O passo é o item 3 da lista final do provisionamento |

**Como manter esta tabela:** ao encontrar um atrito novo cuja correção definitiva não
está nas suas mãos, acrescente uma linha (`H5`, `H6`…) e **diga isso no relatório final
da sessão**. Ao ver que um item foi resolvido, marque ✅ com a data e mova o texto para
a seção técnica correspondente como registro histórico — a tabela é lista de trabalho,
não arquivo morto.

---

## §2 — Partida rápida (os 6 primeiros minutos de qualquer sessão)

```bash
# 1. Worktree próprio (RITOS.md §1) — nunca trabalhe no clone principal
git -C <raiz> fetch origin
git -C <raiz> worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa> origin/main

# 2. Docker JÁ (se a célula tem banco) — sobe em background enquanto você lê a constituição
docker run -d --name <celula>-pg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=<celula>_db -p 55432:5432 postgres:17

# 3. Ambiente da sessão (as 3 variáveis que todo make ci local precisa)
export PYTHONUTF8=1
export DJANGO_SECRET_KEY="ci-apenas-nunca-em-producao"
export DATABASE_URL="postgres://dev:dev@localhost:55432/<celula>_db"

# 4. Baseline VERDE antes de tocar qualquer arquivo (RITOS.md §1)
cd ../wt-<celula>-<tarefa>/services/<celula>
make ci
```

Se o baseline não estiver verde: **pare e reporte**. Consertar main quebrada não é
escopo de sessão de feature.

**Planeje a divisão ANTES de escrever código.** O orçamento de 15 arquivos é portão
mecânico (§5.1). Uma célula nova com modelo + migrations + clientes + middleware +
guardas de invariante **não cabe** em 15 arquivos junto com páginas. Conte os arquivos
no papel antes da primeira linha; se estourar, divida o despacho em dois PRs e diga
isso na primeira resposta, não no fim.

---

## §3 — Ambiente (Windows, esta máquina)

### 3.1 `make: command not found` — RESOLVIDO em 19/08/2026

**Era:** o Bash do agente não é login shell, não lia `~/.bashrc`, e o `make` do WinGet
só estava no PATH de lá — todo comando precisava virar `bash -lc 'make ...'`.
**Resolvido:** a pasta do `make` entrou no PATH do usuário (Windows). Hoje
`command -v make` responde direto no Bash do agente, sem `-l` e sem `export PATH`.
**Se voltar a falhar:** confira se o PATH do usuário ainda contém
`...\WinGet\Packages\ezwinports.make_.../bin` — o sintoma é exatamente este título.
**Origem:** Prompt 3a (pagamentos, PR #16) · corrigido pelo mantenedor.

### 3.2 `make contrato-check` dando "OK" falso — RESOLVIDO em 19/08/2026

**Era:** `python3` resolvia para o stub quebrado da Microsoft Store. O
`ci/freeze-de-contrato.sh` chama `python3` internamente, as duas pontas do diff falhavam
igual e "batiam" — **o portão dizia OK sem ter comparado nada**, e cada agente precisava
validar o contrato à mão.
**Resolvido em duas camadas, e a distinção importa:**

1. **A máquina:** shim `~/bin/python3` → Python 3.12 real. Isso desarmou o sintoma
   *aqui*. Não é a correção do portão: qualquer outra máquina (ou uma imagem de CI sem
   PyYAML) reproduziria o mesmo verde mentiroso.
2. **O portão:** a lógica saiu do Bash para `ci/contract_freeze.py` e passou a ser
   fail-closed por construção ([INV-CI01] em `INVARIANTES.md`). Ferramenta ausente,
   stdout vazio, contrato obrigatório ausente, congelado malformado ou raiz não
   resolvida ⇒ `ERROR` (exit 2) — nunca `PASS`. O `.sh` virou wrapper fino e procura
   `python` **antes** de `python3`, para que o shim seja conveniência local e não
   requisito arquitetural.

**Evidência de que valida de verdade (não só parou de reclamar):** com uma divergência
deliberada no `summary` de uma operação, o script imprimiu o diff e saiu com erro
(`make: *** [contrato-check] Error 1`); restaurado, voltou a `✅ OK`. Depois da
reescrita, a mesma prova foi refeita nos três estados: contrato igual ⇒ `PASS` (0),
divergente ⇒ `FAIL` (1), instrumento quebrado de propósito ⇒ `ERROR` (2).
**Ressalva histórica:** a nota original dizia *"no CI real (Linux) o script funciona de
verdade — o falso-positivo é só local"*. Isso estava **errado por sorte**. O mecanismo
nunca dependeu do sistema operacional, só de a normalização falhar nas duas pontas ao
mesmo tempo; bastava a imagem do runner não ter PyYAML para o mesmo verde aparecer no
CI. Se você encontrar essa frase em algum documento antigo, ela está incorreta.
**Se voltar a falhar:** desconfie de qualquer verde acompanhado de `command not found`.
Hoje isso é impossível por construção — `python ci/contract_freeze.py <celula>` mede e
diz em qual dos quatro estados parou.
**Origem:** Prompt 2 (catalogo, PR #15) · shim pelo mantenedor · endurecimento em Bash
no PR #21 · reescrita fail-closed no PR #22.

### 3.3 `UnicodeEncodeError` / acento virando lixo na saída de comando Django

**Sintoma:** saída com emoji ou acento quebra no terminal (cp1252).
**Solução:** `export PYTHONUTF8=1` antes de rodar qualquer coisa localmente.
**Origem:** Prompt 2 (catalogo, PR #15).

### 3.4 Docker Desktop frio no meio do trabalho

**Sintoma:** 1–2 minutos parado esperando o Docker subir, bem quando você ia rodar
os testes.
**Solução:** suba o container de banco **no início da sessão**, em background, em
paralelo com a leitura da constituição. Nunca no meio.
**Origem:** Prompt 2 (catalogo, PR #15).

### 3.5 `black` local reformata o que o CI aprovaria (e vice-versa)

**Sintoma:** `black --check` verde local, vermelho no CI (ou o contrário).
**Causa:** a versão instalada globalmente nesta máquina é mais nova que a pinada no
`requirements.txt` da célula (o CI instala a pinada).
**Solução:** rode `black .` antes do commit e prefira construções cuja formatação não
muda entre versões. Se o CI reclamar de formatação que passou local, é isto.
**Origem:** Prompt 4 (checkout).

### 3.6 Arquivo escrito no bash não é encontrado pelo Python em seguida

**Sintoma:** `> /tmp/x.json` funciona no bash, e o `open("/tmp/x.json")` do Python
logo depois estoura `FileNotFoundError: '\tmp\x.json'`.
**Causa:** o `/tmp` do Git Bash (MSYS) não é o mesmo `/tmp` que o `python.exe` nativo
do Windows enxerga.
**Solução:** para qualquer arquivo intermediário que um processo vá escrever e outro
ler, use o diretório de scratchpad da sessão, com **caminho absoluto do Windows**.
**A pegadinha fina:** `/tmp/x.json` pode significar **dois lugares na mesma linha de
comando**. Ao chamar um `.exe` nativo, o Git Bash *traduz* o argumento — `/tmp/x.json`
vira `C:\Users\<voce>\AppData\Local\Temp\x.json`. Mas `Path("/tmp/x.json")` **dentro**
do Python vira `C:\tmp\x.json`. Escrever por um caminho e ler pelo outro falha sem erro
óbvio: o arquivo existe, só não onde você olhou.
**Origem:** Prompt 3a (pagamentos) — repetido no Prompt 4 (checkout) e no PR #22.

### 3.7 Path `/c/Users/...` dentro de código Python não resolve

**Sintoma:** o mesmo caminho funciona como argumento no bash e falha dentro do script.
**Causa:** o `python.exe` nativo do Windows não entende paths estilo MSYS quando eles
são **literal de string no código** — só quando o próprio Bash converte o argv.
**Solução:** dentro de código Python, escreva `C:/Users/.../arquivo.json` (o Python
aceita `/` como separador no Windows).
**Origem:** Prompt 3a (pagamentos, PR #16).

### 3.8 `.venv` dentro do worktree é risco de commit acidental

**Causa:** o `.gitignore` das células não lista `.venv/`.
**Solução:** crie o venv **fora** do worktree (ex.: no scratchpad da sessão).
**Origem:** Prompt 3a (pagamentos, PR #16).

### 3.9 Subir a célula inteira só para rodar teste

**Solução:** só o banco basta — `docker compose -f docker-compose.dev.yml up -d db`.
Ou um container avulso, como no §2. As dependências (catálogo, pagamentos) nunca sobem:
elas existem como contrato mockado.
**Origem:** Prompt 3a (pagamentos, PR #16).

---

### 3.10 `shutil.which("bash")` no Windows acha o WSL, não o Git Bash

**Sintoma:** `<3>WSL (…) ERROR: CreateProcessCommon:800: execvpe(/bin/bash) failed:
No such file or directory` ao rodar um `.sh` do repositório a partir de Python.
**Causa:** `C:\Windows\System32\bash.exe` (o lançador do WSL) vem antes do Git Bash no
PATH. Ele existe, é executável, e não roda script do Git Bash.
**Solução:** não basta *encontrar* a ferramenta — é preciso **sondá-la**. Ver `_bash()`
em `ci/ci.py` e `bash_utilizavel()` em `ci/tests/conftest.py`: cada candidato roda
`bash -c "printf sondagem-ok"` antes de ser aceito. Vale como regra geral em portão de
CI: presença no PATH não é prova de que funciona.
**Origem:** PR #22.

### 3.11 `psql` num script de `docker-entrypoint-initdb.d/` conecta no banco errado

**Sintoma:** `FATAL: database "dev" does not exist` dentro do log do container
Postgres, mesmo com o container saudável e o `POSTGRES_DB` configurado.
**Causa:** `psql --username dev` **sem** `--dbname` tenta conectar num banco com o
MESMO NOME do usuário (`dev`) — comportamento padrão do cliente `psql`, não tem nada
a ver com `POSTGRES_DB` (`dev_db`), que só existe porque a imagem oficial cria esse
banco específico no boot.
**Solução:** em qualquer script de init que crie bancos adicionais (ex.: um Postgres
compartilhado por várias células num compose de e2e), passe sempre
`--dbname "$POSTGRES_DB"` explicitamente.
**Origem:** `e2e/postgres-init.sh` (despacho e2e/esqueleto — Postgres compartilhado
criando `catalogo_db`/`checkout_db`/`pagamentos_db`/`alunos_db`).

### 3.12 CRLF num `.sh` comitado a partir do Windows quebra dentro de container Linux

**Sintoma:** nada quebra localmente (o Git Bash tolera), mas o mesmo script rodando
dentro de um container Linux (ou clonado num runner Linux) falha com erros
estranhos de shebang ou parsing.
**Causa:** `core.autocrlf=true` (comum em máquina Windows) reescreve `.sh` para CRLF
no working tree; sem uma regra explícita, o `\r` pode entrar no blob comitado.
**Solução:** `.gitattributes` com `*.sh text eol=lf` na raiz do repo — força LF no
blob independente do `core.autocrlf` de quem commitou. Confira sempre com
`git show :<arquivo> | grep -c $'\r'` (deve dar 0) antes de considerar um `.sh`
pronto.
**Origem:** `e2e/esqueleto.sh` e `e2e/postgres-init.sh` (despacho e2e/esqueleto).

### 3.13 Dois containers rodando `migrate --noinput` ao mesmo tempo, banco novo

**Sintoma:** `django.db.utils.IntegrityError: duplicate key value violates unique
constraint "pg_type_typname_nsp_index"` / `MigrationSchemaMissing: Unable to
create the django_migrations table` — um dos dois containers simplesmente morre
no boot, o outro sobe normal.
**Causa:** dois processos Django apontando pro MESMO banco recém-criado (sem a
tabela `django_migrations` ainda) rodam `migrate --noinput` em paralelo — os
dois tentam criar a tabela ao mesmo tempo, um perde a corrida e estoura. Em
compose de e2e isso aparece fácil: célula com um servidor HTTP (roda `migrate`
no `CMD` do Dockerfile) + um sidecar da MESMA célula pra outro processo (ex.:
um consumer de eventos) também herdando esse `CMD`, ambos subindo juntos.
**Solução:** só UM container migra. O outro depende dele com
`condition: service_healthy` (exige um `healthcheck:` no primeiro — checar
`/healthz` já resolve) e roda só o comando dele (`command: python manage.py
consume_eventos`), sem `migrate` embutido.
**Origem:** `e2e/docker-compose.e2e.yml` — serviço `alunos-consumer`, subindo
junto com `alunos` contra `alunos_db` recém-criado (despacho e2e/esqueleto).

### 3.14 Portão roda com o Python ERRADO porque o PATH estava em formato Windows

**Sintoma:** `bash ci/cross-smoke.sh` fica **verde**, mas o traceback/warning na
saída mostra `C:\Users\...\Programs\Python\Python312\Lib\site-packages\...` —
o Python **global** da máquina, não o venv da célula com as versões pinadas.
**Causa:** `export PATH="C:/Users/.../venv/Scripts:$PATH"` **não funciona** no Git
Bash. A busca de executáveis do Bash espera caminhos POSIX; `C:/...` entra no PATH
como uma entrada inválida, é ignorada em silêncio, e o `python` do script resolve
para o primeiro do PATH herdado — o global. Nada falha, nada avisa.
**Solução:** no PATH, use a forma `/c/Users/...`:
`export PATH="/c/Users/davia/AppData/Local/Temp/claude/<venv>/Scripts:$PATH"`.
Confira antes de confiar no portão: `which python` tem de apontar para o venv.
(Isto é o oposto do §3.7 — *dentro* de código Python o caminho precisa ser
`C:/Users/...`; no PATH do Bash precisa ser `/c/Users/...`. Os dois formatos são
necessários, em lugares diferentes.)
**Por que importa mais aqui:** é um primo do §5.6 — portão verde que não mediu o
que você acha que mediu. Passou verde com o interpretador errado, e um `make ci`
que "passa" contra pacotes de outra versão não prova nada sobre o CI real.
**Origem:** despacho 03 (pagamentos, fail-closed do Mercado Pago).

### 3.15 Trocar por `mv`/`rm` um arquivo ou diretório bind-mounted não muda nada no container que já roda

**Sintoma:** você substitui, no servidor, um arquivo ou diretório que o compose
monta por bind (`./traefik/traefik.yml:...:ro`), roda `docker compose up -d`, nada
é recriado — e o container continua servindo a configuração **antiga**, sem erro
nenhum em lugar nenhum.
**Causa:** bind mount prende o **inode** resolvido na criação do container, não o
caminho. `mv novo antigo` e `rm -rf dir && mv dir.new dir` criam inodes novos; o
container em execução segue lendo o inode velho (que sobrevive enquanto montado,
mesmo "apagado" do disco). E `up -d` só recria serviço cuja **definição** no
compose mudou — conteúdo de arquivo montado não conta como mudança.
**Solução:** depois de trocar arquivo/diretório montado, force o recreate de quem
o monta: `docker compose up -d --force-recreate <servico>`. É o que
`.github/workflows/deploy-infra.yml` faz com o traefik, condicionado a um
`diff -r` entre o backup e o material novo — recriar sem necessidade seria um
blip de edge gratuito a cada sync de compose.
**Origem:** despacho 04 (deploy-infra), ao desenhar a troca fail-closed de
`/opt/plataforma/traefik/`.

### 3.16 `sed` no `sshd_config` não desliga login por senha no Ubuntu 24.04 — o cloud-init religa por baixo

**Sintoma:** o provisionamento rodou
`sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config`
e mesmo assim `ssh usuario@vps` **pede senha** (medido em 21/08/2026 nesta VPS).
**Causa:** o Ubuntu 24.04 entrega `/etc/ssh/sshd_config.d/50-cloud-init.conf` com
`PasswordAuthentication yes`, e o `Include` dos drop-ins vem **no topo** do
`sshd_config` — no sshd, **o primeiro valor lido vence**. O sed edita a linha do
arquivo principal, que é lida tarde demais para valer.
**Solução:** um drop-in que vença na ordem lexicográfica
(`printf 'PasswordAuthentication no\n' > /etc/ssh/sshd_config.d/00-endurecimento.conf`),
mais `rm -f` do `50-cloud-init.conf` e `systemctl reload ssh`. Nesta VPS foi aplicado
à mão em 22/08/2026; `infra/provisionamento-vps.sh` agora faz as duas coisas. O risco
real era limitado (deploy sem senha utilizável, root em `prohibit-password`), mas a
"impossibilidade" prometida não estava valendo.
**Como conferir:** `ssh conta-inexistente@vps` deve recusar com
`Permission denied (publickey)` **sem** oferecer campo de senha.
**Origem:** sessão deploy-infra (22/08/2026), ao notar o prompt de senha num teste
de SSH do mantenedor.

### 3.17 Cloudflare na frente do domínio ⇒ deploy morre em `dial tcp <host>:22: i/o timeout`

**Sintoma:** `deploy-celula`/`deploy-infra` falham na etapa de SSH com
`dial tcp ***:22: i/o timeout` — com runs verdes NO MESMO DIA, minutos antes, e a
VPS saudável (porta 22 respondendo o banner `SSH-2.0-...` no IP direto).
**Causa:** o segredo `VPS_HOST` guardava o **domínio** (`basileiatoutheou.org`). Ao
colocar o domínio atrás do Cloudflare (nuvem laranja/Proxied), o nome passa a
resolver para a borda do Cloudflare — que só repassa HTTP/HTTPS, nunca a porta 22.
A pegadinha: os primeiros deploys pós-mudança ainda PASSAM (cache de DNS com o IP
antigo), e a falha só aparece quando o cache vence — no lote 2 foram 4 deploys
verdes e o 5º vermelho, o que disfarça completamente a causa.
**Solução:** pipeline fala com a VPS por **IP**, nunca pelo domínio público
proxiado — `VPS_HOST=217.196.62.220` (trocado pelo mantenedor em 22/08/2026;
segredo de repositório é território dele). Regra geral: mudou DNS/proxy de um
host que algum pipeline usa ⇒ teste o canal do pipeline IMEDIATAMENTE, não espere
o próximo merge descobrir. Conferir SSH vivo de fora, sem ssh:
`exec 3<>/dev/tcp/217.196.62.220/22 && head -c 30 <&3` (imprime o banner).
**Origem:** janela de merge do lote 2 (22/08/2026), deploy do PR #75 — 2 reruns
para diagnosticar, causa externa, `gh run rerun <id> --failed` verde após a troca.

---

## §4 — Django e django-ninja

### 4.1 `AttributeError: DoesNotExist` / `AttributeError: objects`

**Sintoma:** `Session.objects` estoura `AttributeError: objects`, ou
`except Model.DoesNotExist` estoura `AttributeError: DoesNotExist` — vindo de dentro
do pydantic (`_model_construction.py`).
**Causa:** existe um `ninja.Schema` com o **mesmo nome** do model Django no mesmo
arquivo (ex.: `class Session(Schema)` e `from ...models import Session`). A classe
definida embaixo **sombreia silenciosamente** o import de cima.
**Solução:** importe o model com alias:

```python
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel
```

**Só aparece rodando os testes de verdade** — o import não falha, o lint não vê.
**Origem:** Prompt 2 (catalogo, PR #15) — e repetido em Prompt 4 (checkout), o que
mostra que a armadilha é estrutural, não distração.

### 4.2 `ConfigError: Schema for status 201 is not set in response`

**Sintoma:** handler devolve `(201, {...})` e a rota estoura.
**Causa:** rota **sem** `response=` no decorator só aceita 200.
**Solução:** devolva `django.http.JsonResponse(dict, status=N)` direto — passa batido
pelos `response_models` por completo.
**NÃO resolva com `response={200: ..., 201: ...}`:** qualquer valor não-`None` ali vira
um `ninja.Schema` dinâmico que pode vazar para `components.schemas` do documento
exportado e **quebrar o freeze de contrato**.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 4.3 `migrate` não encontra as migrations do app novo

**Sintoma:** app novo com modelo, migration criada, e o `migrate` ignora.
**Causa:** falta `apps/<novo>/migrations/__init__.py` — é **obrigatório**.
**Nota que economiza um arquivo no orçamento:** `apps/<novo>/management/commands/`
funciona **sem** `__init__.py` (namespace package — já usado em `apps/core`). O
próprio pacote do app também: `apps/core` não tem `__init__.py` e está em
`INSTALLED_APPS`.
**Conte esse arquivo no orçamento** de qualquer app novo com modelo próprio.
**Origem:** Prompt 2 (catalogo, PR #15) — confirmado de novo no despacho do quiz
(PR do Crivo): `apps/quiz/__init__.py` foi removido de propósito, só para caber no
orçamento de 15 arquivos, e `make ci` continuou verde.

### 4.4 `QuerySet.update()` fura o guarda escrito em `Model.save()`

**Sintoma:** o teste de imutabilidade passa por `save()` mas o campo muda via
`Model.objects.filter(...).update(campo=...)`.
**Causa:** `QuerySet.update()` **não passa** por `Model.save()`.
**Solução:** guarda de imutabilidade precisa existir nos **dois** caminhos — override
de `save()` **e** de `update()` num `QuerySet` customizado. (O `save()` interno do
Django usa `_update()`, com underscore, então não entra em laço com o seu override.)
**Origem:** Prompt 4 (checkout, INV-P1).

### 4.5 Middleware intercepta `/healthz` e derruba a sonda

**Sintoma:** `/healthz` passa a devolver 404 depois de instalar o middleware
CONV-SITE; o teste de fumaça quebra e, em produção, o container ficaria "unhealthy".
**Causa:** o middleware roda em **toda** requisição. `/healthz` chega sem Host de site
(é sonda do container e do gateway) e não pode depender do catálogo estar de pé.
**Solução:** isente os caminhos que não pertencem a nenhum site:

```python
CAMINHOS_SEM_SITE = ("/healthz", "/static/")
if request.path.startswith(CAMINHOS_SEM_SITE):
    return self.get_response(request)
```

**Origem:** Prompt 4 (checkout).

### 4.6 Middleware roda ANTES da autenticação do django-ninja

**Sintoma:** teste que espera 401 (sem token) recebe 404, ou tenta uma conexão HTTP
real e estoura.
**Causa:** ordem real da pilha: middleware → view/auth. O CONV-SITE resolve o site
(e chama o catálogo) **antes** de o Bearer ser conferido.
**Solução:** todo teste que bate na API precisa de Host válido **e** do mock de rede
ativo — inclusive os testes de "sem token".
**Origem:** Prompt 4 (checkout).

### 4.7 Cache de módulo vaza entre testes

**Sintoma:** teste passa sozinho e falha na suíte (ou o contrário), envolvendo
resolução de site/host.
**Causa:** o cache do CONV-SITE é um `dict` de nível de módulo — sobrevive entre
testes, inclusive cacheando o 404.
**Solução:** exponha uma função de limpeza (`limpar_cache_de_sites()`) e chame numa
fixture `autouse` antes e depois de cada teste.
**Origem:** Prompt 4 (checkout).

### 4.8 `IntegrityError` capturado sem savepoint quebra a transação do teste inteira

**Sintoma:** um `except IntegrityError:` que deveria simplesmente ignorar uma
duplicata (dedup por `unique=True`, padrão da Receita R4) funciona isolado, mas a
**query seguinte** — no mesmo teste, ou até um teste depois que reusa a conexão —
estoura `django.db.transaction.TransactionManagementError: An error occurred in the
current transaction. You can't execute queries until the end of the 'atomic' block.`
**Causa:** `Model.objects.create(...)` dentro de um `try/except IntegrityError` sem
`transaction.atomic()` próprio roda na transação corrente inteira (a que o
`pytest.mark.django_db` já abriu para o teste). Quando o INSERT viola a constraint
`UNIQUE`, o Postgres marca **essa transação inteira** como abortada — o Django só
descobre isso na tentativa de query seguinte, não na hora do `except`.
**Solução:** todo `create()` que pode legitimamente colidir com uma constraint única
(dedup de evento, corrida de criação idempotente) precisa do próprio savepoint:

```python
try:
    with transaction.atomic():          # savepoint — só ISTO é desfeito no IntegrityError
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return
```

**Atenção — a Receita R4 em `CAMINHO-DOURADO.md` (bloco `apps/eventos/management/
commands/consume_eventos.py`) mostra o `create()` sem esse `with transaction.atomic()`
aninhado.** Reproduz o bug assim que dois eventos (ou o mesmo evento 2×) passarem pelo
mesmo teste. Quem copiar a receita ao pé da letra herda o bug — considere `issue
arquitetura:` para corrigir a receita na fonte. **Atualização (21/08/2026):** isso
deixou de ser suspeita — ver §4.12, onde a mesma receita produziu um segundo bug, pior,
em três das quatro células consumidoras.
**Origem:** alunos (matrícula por evento, R4/INV-P5) — descoberto ao escrever o
teste-guarda de reentrega de `event_id`. **Redescoberto de forma independente** em
leads (timeline por evento) na sessão seguinte, mesmo sintoma, mesma causa — reforça
que é falha da receita, não acidente de uma célula: qualquer célula que testar o
handler de R4 direto (sem passar pelo loop do Redis) bate nisso.

### 4.9 Cliente de provedor externo que só levanta em 5xx **falha aberto**

**Sintoma:** a API responde **201/200 de sucesso** com os campos do recurso vazios
(`"qr_code": ""`, `provider_payment_id=""`). Nada nos logs, nenhum teste vermelho.
**Causa:** o cliente HTTP só trata o erro grosso:

```python
if resp.status_code >= 500:          # ⟵ 400/401/403/404/429 passam batido
    raise ProviderError(...)
data = resp.json()                   # corpo de ERRO lido como se fosse o recurso
```

O corpo de erro do provedor não tem os campos que o tradutor procura, e
`resposta.get("id", "")` transforma **campo ausente em string vazia** — o erro vira
um objeto de aparência normal e segue adiante como sucesso.
**Três buracos, sempre os mesmos:**
1. **status** — qualquer não-2xx tem de levantar, não só 5xx;
2. **corpo** — `resp.json()` levanta `JSONDecodeError`, que é `ValueError` e **não**
   `httpx.HTTPError`: um `except httpx.HTTPError` não pega uma página HTML de erro
   de CDN/WAF, e ela vira 500 não tratado;
3. **payload** — 2xx não é prova: valide os campos sem os quais o recurso é inútil,
   e **nunca** traduza ausente para `""`.

**Solução:** falhe fechado nos três, com a causa nomeada na mensagem (autenticação,
rejeição, rate limit, indisponibilidade, timeout, corpo ilegível) — no meio de um
incidente, "credencial recusada" e "rate limit" levam a ações opostas. Capture
`httpx.TimeoutException` **antes** de `httpx.HTTPError` (é subclasse dela), porque
num timeout a operação pode ter acontecido do outro lado e um erro de conexão não.
**Onde já estava certo:** `services/checkout/apps/core/clients.py` e
`services/funil/apps/core/clients.py` (`raise_for_status()` / `else None`) — a
armadilha era só de pagamentos, mas confira o seu ao escrever um cliente novo.
**Ao consertar, cuidado com o status novo:** devolver um 502 **não** pode virar
`response={...}` no decorator do django-ninja (§4.2) nem entrar no `openapi_extra`
sem Rito de Contrato — use `JsonResponse(dict, status=502)` direto.
**Origem:** despacho 03 (pagamentos) — o bug estava em produção desde o Prompt 3a e
nenhum dos 19 testes da célula o via (ver §6.9).

### 4.10 `/healthz` responde 404/500 em produção, mas 200 em dev — `SCRIPT_NAME` + Django 5.0

**Sintoma:** a mesma imagem que devolve `200 {"status": "ok"}` em `GET /healthz`
localmente devolve **404** (ou 500, se a resolução de site fizer uma chamada HTTP que
falha) quando sobe com o `env/*.env` de produção. Efeito prático: healthcheck de
container nunca fica `healthy`, e qualquer serviço com
`depends_on: condition: service_healthy` **nunca sobe**.
**Causa:** a isenção do middleware CONV-SITE (§4.5) é escrita como
`request.path.startswith(("/healthz", "/static/"))`, e `request.path` **inclui o
script name**. Com `SCRIPT_NAME=/checkout` no env de produção, `FORCE_SCRIPT_NAME`
faz `request.path` virar `/checkout/healthz` — a isenção não casa, o middleware tenta
resolver o site a partir do Host `localhost`, não acha, e levanta `Http404`.
`request.path_info` continua `/healthz` (por isso a URL **resolve** normalmente; quem
erra é só a comparação).

E depende da versão do Django — as duas convivem neste repositório:

| Django | `ASGIRequest.__init__` | `request.path` com `FORCE_SCRIPT_NAME=/checkout` |
|---|---|---|
| **5.0.9** (alunos, catalogo, checkout, leads, pagamentos) | `self.path = script_name.rstrip("/") + "/" + path_info[1:]` | `/checkout/healthz` ⇒ **quebra** |
| **5.1.4** (funil, mensageria, quiz) | `self.path = scope["path"]` | `/healthz` ⇒ funciona |

Ou seja: a armadilha só dispara onde as **três** coisas coincidem — `SCRIPT_NAME` no
env, middleware CONV-SITE na célula, e Django 5.0.x. Hoje isso é **só `checkout`**
(medido nas 8 células em 21/08/2026 com `infra/env/*.exemplo`: 7 respondem 200,
`checkout` responde 404). `quiz` tem `SCRIPT_NAME` e middleware, mas está em 5.1.4;
`alunos` tem `SCRIPT_NAME` e 5.0.9, mas não tem middleware. Qualquer uma das três
muda ⇒ mais uma célula cai, **em silêncio**.

**Solução:** no middleware, comparar `request.path_info`, não `request.path` — é o
caminho independente de prefixo de gateway. Enquanto a célula não for corrigida
(ARMADILHAS §1/H10), o contorno em `infra/docker-compose.yml` é sondar o socket TCP
em vez do HTTP: prova que o `migrate` do `CMD` terminou e o uvicorn subiu, que é tudo
o que o `depends_on` precisa saber.

**Como medir sem adivinhar** (roda contra a imagem, com o env real da célula):

```bash
docker run -d --name sonda --env-file infra/env/<celula>.env <imagem>
docker exec sonda python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/healthz').status)"
```

⚠ **No Git Bash, passe o env por `--env-file`, nunca por `-e SCRIPT_NAME=/checkout`:**
o MSYS converte o `/checkout` em `C:/Program Files/Git/checkout` (§3.7) e o teste
mede outra coisa — foi exatamente isso que fez a primeira rodada desta medição dar
um resultado sem sentido (`quiz` "passando" por motivo errado).

**De quebra:** `ALLOWED_HOSTS` nos `infra/env/*.exemplo` é decorativo — as 8 células
têm `ALLOWED_HOSTS = ["*"]` fixo no `config/settings.py` e **não leem** essa variável.
Por isso a sonda com `Host: localhost` passa mesmo em `catalogo`/`leads`/`mensageria`,
cujo exemplo diz `ALLOWED_HOSTS=<nome-da-célula>`.
**Origem:** despacho infra/consumers — ao acrescentar healthcheck ao bloco `x-celula`.
**Atualização (lote 2, 22/08/2026) — Django 5.1 NÃO imuniza quando o acesso vem
pelo gateway:** a tabela acima mede a sonda INTERNA (request line `/healthz`, sem
prefixo). Pela borda pública o Traefik NÃO remove o prefixo — a request line é
`/quiz/healthz` — e aí `request.path` contém o prefixo em QUALQUER versão do
Django. Medido: `quiz` (5.1.4) respondia 404 em `/quiz/healthz` pela internet até
o PR #71 trocar a comparação para `request.path_info`. A regra vale para toda
célula com middleware: a isenção compara `path_info`, sempre.

### 4.11 Worker do Huey não executa nada: `TaskRegistry` vazio ou `AppRegistryNotReady`

**Sintoma:** o `huey_consumer.py` sobe e loga
`The following commands are available:` **sem nada listado** — e nenhuma task jamais
roda. Trocando o caminho do módulo para o das tasks, o processo nem sobe:
`django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.`
**Causa:** duas peças que precisam acontecer **nesta ordem** e que o
`huey_consumer.py` não faz sozinho:
1. `huey_consumer.py <caminho>` importa **só** o módulo que você nomeou. Apontando
   para `config.huey.huey`, ele acha a instância do Huey — mas `apps/eventos/tasks.py`
   nunca é importado, então o `@huey.task` nunca se registra. Registro vazio ⇒ o
   worker não reconhece nenhuma mensagem da fila.
2. Apontando para `apps.eventos.tasks.huey` o registro seria preenchido, mas o import
   estoura antes: `tasks.py` importa models, e model fora de `django.setup()` é
   `AppRegistryNotReady`. `DJANGO_SETTINGS_MODULE` sozinho **não** resolve — ele
   configura as settings, não o registro de apps.

Isso só não aparece antes porque `huey.contrib.djhuey` (que traria `manage.py
run_huey`, que faz o setup e o autodiscover) **não** está em `INSTALLED_APPS`.
Medido em 21/08/2026, dentro da imagem de `mensageria`; `grep -rn
"run_huey\|huey_consumer\|djhuey" .` no repositório inteiro não devolve nada — não
havia comando canônico a copiar.

**Solução (a definitiva):** `huey.contrib.djhuey` em `INSTALLED_APPS` e
`python manage.py run_huey` — uma linha de `command:`. Enquanto isso não entra
(ARMADILHAS §1/H10), o contorno que **funciona e está medido** é fazer o bootstrap no
próprio `command:` do compose, nesta ordem:

```python
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
import apps.eventos.tasks              # é este import que popula o TaskRegistry
from huey.bin.huey_consumer import consumer_main
consumer_main()                        # lê o caminho da instância de sys.argv[1:]
```

Sinal de que deu certo, no log do worker: a linha
`+ apps.eventos.tasks.enviar_notificacao` logo abaixo de
`The following commands are available:`. Se essa linha não aparecer, o worker está
de pé e inútil — e nada no `docker compose ps` vai dizer isso.
**Origem:** despacho infra/consumers — ao subir o worker Huey de `mensageria`.
### 4.12 Marcar o evento como processado ANTES de aplicar o efeito descarta reentrega em silêncio

**Sintoma:** nenhum — e é esse o problema. Um pagamento aprovado não vira matrícula, uma
timeline fica com buraco, um e-mail de boas-vindas nunca sai. Não há erro, log nem
alerta: a célula reporta "evento já processado" para um evento cujo efeito nunca
aconteceu.
**Causa:** a Receita R4 grava a linha de dedup (`EventoProcessado`) numa transação que
**commita**, e só então chama o handler:

```python
try:
    with transaction.atomic():
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return
handlers[envelope["event"]](envelope["data"])   # ← FORA da transação acima
```

Basta o handler falhar por motivo transitório (deadlock, conexão caída, timeout num
pico) para o evento ficar marcado como visto. Toda reentrega futura — e o transporte é
at-least-once **de propósito** — cai no `except IntegrityError` e é descartada.
**Solução:** duas transações aninhadas, com o handler dentro do `atomic` externo mas
**FORA do `try`**:

```python
with transaction.atomic():          # (1) registro e efeito: vivem ou morrem juntos
    try:
        with transaction.atomic():  # (2) savepoint: SÓ o create
            EventoProcessado.objects.create(event_id=envelope["event_id"])
    except IntegrityError:
        return                      # já processado de verdade
    handlers[envelope["event"]](envelope["data"])
```

**A armadilha da correção óbvia:** mover o handler para dentro do `try` conserta a
atomicidade e planta um bug novo — um `IntegrityError` vindo do handler (qualquer
constraint sem relação com `event_id`) passa a ser lido como "já processado". Não é
hipótese: em `leads` é `uniq_lead_site_email`, disputada por `get_or_create()`; em
`mensageria` é `uniq_envio_por_order_tipo_canal`. É o mesmo bug de antes, só que mais
difícil de enxergar — o savepoint interno existe para que o `except` enxergue apenas o
`create()`.

**É falha da receita, e agora há contagem em vez de suspeita.** Das quatro células que
consomem eventos, **três** tinham o bug: `alunos` (PR #43), `leads` (#46) e `mensageria`
(#47). A quarta, `checkout`, escapou por **não usar a tabela de dedup** — o handler dela
é idempotente por construção (`UPDATE ... WHERE status=aguardando_pagamento`), então não
existe a fenda entre marcar e aplicar. O lado **produtor** está íntegro: o relay de
`pagamentos` publica no Redis **antes** de marcar `published_at`, então falha ali
republica em vez de perder.

**Variante mais afiada, em `mensageria`:** lá o caminho de dedup chamava `r.xack(...)`
antes do `continue`, então a reentrega descartada era **removida do stream** — não
sobrava nem a mensagem na PEL para recuperar depois. Com o fix o `xack` volta a ser
seguro, porque "já processado" passou a significar o que diz.

**Relação com o §4.8:** aquele item cobre **metade** disto — a necessidade do savepoint
para a transação não ficar abortada. Esta é a outra metade: por que existe uma transação
**externa** em volta, e por que o handler fica fora do `try`. Os dois `atomic` parecem
redundantes e não são; remover qualquer um reabre um bug silencioso. Escreva o comentário
no código dizendo isso — o próximo agente vai olhar e achar que é gordura.

**O que este item NÃO resolve:** devolver a *possibilidade* de reentregar não é
reentregar. A mensagem que fez o handler estourar fica na PEL do grupo e ninguém a
reclama — medido pelo despacho infra/consumers e registrado no §9, com a peça que falta
(`XAUTOCLAIM` ou releitura do próprio PEL) nomeada lá. Não abra linha nova para isso.

**O que ainda não foi feito:** a receita R4 em `CAMINHO-DOURADO.md` continua mostrando a
forma errada. Arquivo sob CODEOWNERS ⇒ decisão do mantenedor, com Rito — não de sessão.
Enquanto isso, **qualquer célula nova que copiar R4 nasce com este bug**.
**Origem:** varredura das quatro células consumidoras (21/08/2026), depois de o bug
aparecer em `alunos` e ser reencontrado em `leads` e `mensageria`.

---

## §5 — Portões mecânicos do CI (eles reprovam de verdade)

### 5.0 Como rodar os portões sem adivinhar (comece por aqui)

Dois comandos, com perguntas **diferentes**:

```bash
python ci/doctor.py     # "este ambiente consegue executar o trabalho?"
python ci/ci.py         # "esta mudanca respeita as invariantes?"
```

`make doctor` / `make ci` na raiz fazem exatamente isso — o Makefile é fachada, a
implementação é o Python. Se `make` faltar numa máquina, os comandos acima continuam
sendo o caminho oficial.

**Leia o estado, não a cor.** Os portões falam quatro palavras ([INV-CI01]):

| Estado | Significa | Exit |
|---|---|---|
| `PASS` | mediu e está correto | 0 |
| `FAIL` | mediu e achou violação — **conserte o código** | 1 |
| `ERROR` | **não conseguiu medir** — conserte o ambiente | 2 |
| `SKIP` | declarado não aplicável, com motivo escrito | 0 |

`ERROR` nunca é "quase passou": é a CI dizendo que não sabe. Se aparecer
`ERROR contrato/<celula>` localmente, quase sempre falta variável de ambiente do §2 —
o detalhe do erro traz o comando, o exit code e o stderr crus.

`python ci/ci.py --apenas freeze,muralhas` roda um subconjunto;
`python ci/ci.py --listar` mostra o que existe.

### 5.1 `❌ ORÇAMENTO: N arquivos sem a label 'arquitetural'`

**Sintoma:** o workflow `muralhas` reprova o PR.
**Causa:** `ci/orcamento-de-mudanca.sh` conta
`git diff --name-only origin/main...HEAD | wc -l`. O limite é **15**, e é mecânico —
não é autoavaliação do agente.
**Solução:** rode esse diff **antes** de abrir o PR:

```bash
git diff --name-only origin/main...HEAD | wc -l
bash ci/orcamento-de-mudanca.sh
```

Se estourou, **divida em PRs**, não peça label. Vários despachos proíbem
explicitamente usar label para inchar escopo.
**Origem:** Prompt 2 (catalogo, PR #15 — 16 arquivos, reprovado, corrigido para 15).

### 5.2 `❌ MURALHA: este PR toca N células`

**Causa:** `ci/cerca-de-celula.sh` — 1 PR = 1 célula, sem exceção. `contracts/` nunca
muda junto com `services/` (Rito de Contrato, RITOS.md §3).
**Nota útil:** arquivos de raiz e de `ci/` **não** contam como célula — dá para
corrigir um script de CI no mesmo PR sem violar a cerca (mas eles contam no
orçamento).
**Origem:** Prompt 3a (pagamentos, PR #16 — o fix do `cross-smoke.sh` entrou junto).

### 5.3 CI vermelho por variável de ambiente que existe só na sua máquina

**Sintoma:** `make ci` verde local, `ImproperlyConfigured: variável obrigatória
ausente: X` no CI.
**Causa:** toda variável **nova e fail-hard** (`env()`, convenção CONV v1) declarada
em `config/settings.py` precisa ser espelhada no bloco `env:` do job **`rodar`** em
`.github/workflows/ci-celula.yml` — é o único lugar que fornece env vars para o
`make ci` do CI real. Seu `.env.dev` local (gitignored) sobrevive entre sessões e
**mascara** o esquecimento.
**Solução:** ao adicionar `env("NOVA")`, abra o workflow no mesmo PR. Ou, quando fizer
sentido, **evite o problema**: leia a variável no ponto de uso (`os.environ[...]`
dentro do cliente/middleware, como fazem as receitas R2 e CONV-SITE) em vez de no
`settings.py` — aí nada é fail-hard no import e o CI não precisa conhecê-la.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 5.4 `lint-imports` reprova a rota que a própria constituição manda usar

**Sintoma:** contrato `forbidden` do import-linter acusa
`methods.pix -> core.gateway -> providers...` — exatamente o caminho aprovado.
**Causa:** `type = forbidden` checa a cadeia de imports **transitiva** por padrão.
**Solução:** `allow_indirect_imports = True` no contrato — restringe a checagem ao
import **direto**, que é o que "só fale com X através de Y" realmente significa.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 5.5 `Wrong expression passed to '-m'` no cross-smoke

**Causa:** `IFS=' or '` em bash é um **conjunto** de separadores (espaço, `o`, `r`),
não a string `" or "`.
**Solução:** `printf '%s or ' "${MARKERS[@]}"` + strip do sufixo.
**Origem:** PR #14 — já corrigido em `ci/cross-smoke.sh`; fica registrado porque o
mesmo erro de `IFS` é fácil de repetir em qualquer script novo.

---

### 5.6 Portão de CI que fica verde porque *não conseguiu* medir

**Sintoma:** um portão imprime `✅ ... OK` (exit 0) e, logo acima, o `git`/`python`
gritou `fatal:` ou `command not found`.
**Causa:** o padrão `X=$(comando || true)` seguido de `if [[ -z "$X" ]]; then
echo "nada a fazer"; exit 0; fi`. Falha da ferramenta e "não há nada a verificar"
chegam ao `if` com o mesmo valor — vazio.
**Solução:** separar os três casos. Modelo usado em `ci/cerca-de-celula.sh`,
`ci/cross-smoke.sh` e `ci/orcamento-de-mudanca.sh`:

```bash
if ! DIFF="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR <portao>: não foi possível calcular o diff."   # não consegui medir
  exit 2
fi
if [[ -z "$DIFF" ]]; then echo "SKIP <portao>: git leu o diff e não há nada"; exit 0; fi
```

O mesmo vale para `git grep`, cujo exit code tem TRÊS significados: `0` achou, `1` não
achou, `>1` **erro** (ver `ci/guarda-de-segredos.sh`). Tratar `>1` como "não achou" faz
a guarda de segredos passar sem ter varrido nada.
**A versão em YAML da mesma armadilha:** em `.github/workflows/ci-celula.yml`, o
`git diff ... | head -1 || true` fazia falha de git virar "nenhuma célula tocada" ⇒ job
de teste pulado ⇒ veredito final aceitava `skipped` como verde ⇒ **merge sem um único
teste ter rodado**. Hoje a detecção usa `python ci/ci.py --detectar-celulas` e carimba
que concluiu; sem o carimbo, o gate é vermelho.
**Origem:** auditoria dos portões no PR #22.

### 5.7 O freeze passa verde e a mudança de API é real

**Sintoma:** `contrato/<celula>  PASS`, e mesmo assim o comportamento público mudou.
**Causa:** a comparação documental só enxerga o que o exportador da célula emite. Duas
perdas conhecidas, ambas medidas:

1. **`auth=None` some do documento.** O django-ninja 1.3 **omite** a chave `security`
   das operações com `auth=None`, em vez de emitir `security: []`. Pela especificação,
   operação sem `security` **herda** a do documento — então o schema descreve uma rota
   pública como se fosse autenticada.
2. **Os exportadores apagam o resto.** `catalogo`, `checkout`, `alunos` e `leads` fazem
   `operation.pop("security", None)` sem condição em `export_openapi.py` (`pagamentos`
   já faz o certo: só remove quando é igual à global).

Somadas, tornar `/sites/by-host/{host}` público em catalogo produziu **zero diferença**
no contrato exportado — freeze verde.
**Solução (já no lugar):** `ci/contract_freeze.py` mede a autenticação na **fonte**
(`op.auth_callbacks` do ninja), não no documento, e reprova divergência — linha
`seguranca/<celula>` do relatório.
**Se você mexer em `export_openapi.py`:** qualquer campo que você remova ali deixa de
ser protegido pelo freeze. Remova só ruído do gerador (ex.: `title` do pydantic), nunca
informação contratual — e escreva o porquê no comentário.
**Origem:** PR #22.

### 5.8 Portão verde não significa merge bloqueado

**Sintoma:** confia-se que a CI "não deixa passar", mas nada impede o merge.
**Causa:** branch protection exige GitHub Pro em repositório privado pessoal — ver §1,
linha H3. **Não há required check nenhum.**
**Solução:** distinga sempre os três conceitos ao relatar estado de CI:

```text
LOCAL VERIFIED   rodou na máquina do agente
CANONICAL CI     rodou no GitHub Actions
MERGE PROTECTED  o GitHub EXIGE o check para permitir merge  <- hoje: nenhum
```

Dizer "CI verde" quando você só rodou local é a mesma família de erro que este
documento inteiro combate. Ver a tabela de escopo em `INVARIANTES.md` ([INV-CI01]).
**Origem:** PR #22.

### 5.9 Como se mergeia aqui: o agente, pelo portão — nunca pelo site

**Contexto:** este repositório não tem required check (§1, H3) — o botão verde do
GitHub funciona com tudo vermelho. E desde 22/08/2026 **mergear é trabalho do
agente** (Lei 4; `docs/decisoes/DECISAO-merge-pelo-agente.md`): não se pede ao
humano, não se espera janela de atenção.
**O que já custou:** em 19/08/2026 o PR #21 foi mergeado no lugar do #20 — números
parecidos, recomendações opostas, e nada na tela dizia qual era qual. E a espera
pelo merge humano custava **mediana 22 min, média 264 min por PR** (medido —
PLANO-10X, Alavanca 1): era o maior gargalo do projeto inteiro.
**O caminho (RITOS.md §2 peça 4):**

```bash
python ci/mergear.py 22 --conferir    # os checks acabaram? tudo verde?
python ci/mergear.py 22 --confirmo 22 # mergeia e confere state=MERGED no GitHub
```

Ele mostra **número e título em destaque**, consulta o estado real de cada check e
recusa se algo não estiver verde. O `--confirmo` exige REPETIR o número do PR — não
é "s/n", porque o erro que já aconteceu foi de identidade, não de intenção (sem
`--confirmo`, a pergunta interativa de digitar o número continua existindo, para
uso humano). Semântica [INV-CI01]: reprovou = `FAIL` (1), não consegui consultar =
`ERROR` (2). **Nenhum check reportado é `ERROR`**, nunca sinal verde: um PR sem
check é indistinguível de um PR cujos workflows não dispararam. Depois do merge o
próprio script confere `state=MERGED` — mas o painel e o veredito do run de deploy
(CLAUDE.md) continuam sendo seus.
**Merge em caminho CODEOWNERS** (`contracts/`, `pagamentos`, `checkout`, `infra/`,
`ci/`, `.github/`, arquivos-lei da raiz): só com mandato do despacho, e anunciado
nominalmente no relatório final (Lei 4).

**Detecção por trás (site, push direto):** o `alarme-main` abre issue (label
`main-vermelha`) se a `main` quebrar — alarme, não portão. E o **portão de deploy**
impede commit não-verde de alcançar a VPS (provado ao vivo, ver H3). O clique no
site continua fisicamente possível e continua **proibido** — não confunda os três
estados do §5.8 ao relatar.
**Origem:** decisão de custo consciente, 20/08/2026; reescrito em 22/08/2026,
quando o merge passou ao agente.

### 5.9.1 `ci/mergear.py` estoura `unknown flag: --yes` nesta máquina — RESOLVIDO 22/08/2026

**Sintoma:** `python ci/mergear.py <PR>` confere tudo verde (PASS em todos os checks),
você digita o número do PR para confirmar, e o comando interno falha:
`ERROR ao mergear: ... gh pr merge <PR> --merge --yes ... stderr: unknown flag: --yes`.
**Causa:** `gh pr merge` **nesta instalação** (`gh version 2.97.0`) não tem a flag
`--yes`/`-y` — confirmado com `gh pr merge --help`, a lista de FLAGS não a inclui.
`ci/mergear.py` (linha ~371) assume que ela existe, para evitar que o próprio `gh`
faça uma SEGUNDA pergunta de confirmação depois da que o script já fez.
**Contorno que funcionou:** chamar o `gh` direto, sem `--yes`, com stdin explicitamente
não-interativo — não trava esperando resposta, e não faz segunda pergunta:

```bash
gh pr merge <PR> --merge --delete-branch < /dev/null
```

Se o PR estiver checked out num worktree separado (comum neste repositório — RITOS.md
§1), `--delete-branch` falha só nessa etapa (`cannot delete branch ... used by
worktree`) — o merge em si já aconteceu; confira com
`gh pr view <PR> --json state,mergedBy,mergeCommit` e depois
`git worktree remove <caminho>` + `git branch -D <branch>` na sequência certa.
**RESOLVIDO em 22/08/2026** — a decisão saiu, junto com a de o merge passar ao
agente: `ci/mergear.py` não usa mais `--yes` (`comando_de_merge()` monta o comando
sem a flag; teste-guarda `test_comando_de_merge_nao_usa_yes` impede a volta), o
stdin de TODO subprocesso de portão é fechado por construção (`_nucleo.executar`,
`stdin=DEVNULL` — sem TTY o `gh` não pergunta, age; era exatamente o comportamento
do contorno acima), e a conferência `state=MERGED` ficou embutida no próprio script.
O contorno fica como registro histórico; o comando que o script imprime voltou a
ser o comando que funciona. A ressalva do `--delete-branch` com worktree continua
valendo para quem o usar à mão — o script não o usa.
**Origem:** despacho red-team, golpe 1 (PR #35), 21/08/2026; correção no despacho
governança/merge-pelo-agente, 22/08/2026.

### 5.10 O exit de um pipeline é do ÚLTIMO comando — veredito de run nunca vem de `| tail`

**Sintoma:** `gh run watch <id> --exit-status | tail -25` termina com exit 0 e o
agente anuncia o run como verde — mas o run tinha **FALHADO**. Aconteceu de verdade
em 21/08/2026, no 1º run do `deploy-infra`: o exit era do `tail`, não do `watch`.
**Causa:** em `A | B`, o status do pipeline é o de **B**. Qualquer `| head`,
`| tail`, `| grep` pendurado num comando cujo exit importa mascara a falha — é a
versão de shell do §5.6.
**Solução:** o veredito de um run vem de
`gh run view <id> --json status,conclusion` DEPOIS do watch. Se precisar limitar a
saída do watch, capture o exit antes do pipe (`watch ...; ec=$?`) ou descarte a
saída (`>/dev/null`) e confira o JSON. Regra geral: **exit que decide algo nunca
atravessa pipe sem ser capturado**.
**Origem:** sessão deploy-infra (21-22/08/2026) — o agente reproduziu em si mesmo o
falso-verde que este repositório combate; corrigido na mesma sessão, veredito
refeito pelo JSON.

## §6 — Testes

### 6.1 Evidência vermelho→verde sem criar branch descartável

O protocolo (INVARIANTES.md, Lei 3) exige a saída **crua** do guarda vermelho sem o
fix e verde com o fix. O jeito rápido:

```bash
git stash push -- <arquivo-do-handler>   # tira só a proteção
python -m pytest tests/test_inv_pX_*.py -q   # VERMELHO
git stash pop                                 # devolve
python -m pytest tests/test_inv_pX_*.py -q   # VERDE
```

Mais rápido e limpo que criar branch/commit só para isso.
**Origem:** Prompt 2 (catalogo, PR #15).

### 6.1.1 Em LOTE paralelo, `git stash pop` pode devolver o stash de OUTRO agente

**Sintoma:** o `git stash pop` do protocolo acima devolve arquivos de OUTRA
célula (e o seu trabalho "some"), sem erro nenhum. Medido em 22/08/2026, no
primeiro lote paralelo: a pilha de stash é ÚNICA por repositório — todos os
worktrees a compartilham. Duas sessões usando §6.1 ao mesmo tempo intercalam
push/pop: cada uma popou o stash da outra (o trabalho de checkout apareceu
não-commitado no worktree do quiz, e vice-versa).
**Causa:** `git stash` guarda na ref global `refs/stash`, não por worktree nem
por branch. `pop` sem argumento pega o topo da pilha, seja de quem for.
**Solução:** em lote, NÃO use stash para o vermelho→verde — use patch, que é
local ao worktree por construção:

```bash
git diff -- <arquivo-do-fix> > "$SCRATCH/fix.patch"   # guarda o fix
git checkout -- <arquivo-do-fix>                       # tira o fix
python -m pytest tests/test_x.py -q                    # VERMELHO
git apply "$SCRATCH/fix.patch"                         # devolve o fix
python -m pytest tests/test_x.py -q                    # VERDE
```

Se precisar mesmo de stash, sempre por ref explícita (`git stash pop
'stash@{N}'` depois de conferir `git stash list`) — nunca `pop` seco. E se
popar o stash alheio por engano: devolva-o à pilha imediatamente
(`git stash push -m "RESGATE ..." -- <caminhos-da-outra-celula>`) antes de
qualquer outra coisa — o conteúdo é do outro agente, não seu.
**Origem:** lote de 22/08/2026 — corrida de stash entre as sessões checkout e
quiz; os dois conteúdos foram recuperados íntegros.

### 6.2 `respx.models.AllMockedAssertionError: ... not mocked!`

**Sintoma:** o teste do caminho "recurso inexistente" estoura em vez de receber 404.
**Causa:** o `respx` só responde o que foi registrado; rota não registrada é erro, não
404. E ele resolve as rotas **na ordem de registro** — a primeira que casar ganha.
**Solução:** registre as rotas específicas primeiro e um catch-all por último:

```python
mock.get(url__regex=r".*/sites/[^/]+/ofertas/.+").mock(return_value=httpx.Response(404))
```

**Origem:** Prompt 4 (checkout).

### 6.3 Comparação de data/hora falha por 3 horas

**Sintoma:** o mesmo instante "não bate" antes vs. depois de um `save()`+`fetch`.
**Causa:** o Postgres normaliza `timestamptz` para UTC ao persistir — `-03:00` vira
`+00:00` na string.
**Solução:** compare via `datetime.fromisoformat(...)`, nunca string ou dict cru.
**Origem:** Prompt 3a (pagamentos, PR #16).

### 6.4 Teste-guarda é intocável

Proibido deletar, desativar, comentar ou afrouxar teste para passar (RITOS.md §2.3).
Se o teste parece errado: **pare e reporte**, não ajuste o assert. Duas tentativas
consecutivas de correção falharam ⇒ `git reset --hard <último-verde>` e reporte —
a terceira tentativa é onde nascem labirintos.

### 6.5 `transaction.on_commit(...)` nunca dispara no teste

**Sintoma:** o código chama `on_commit` (relay de outbox, por exemplo) e o teste jura
que nada foi publicado.
**Causa:** o `@pytest.mark.django_db` padrão embrulha cada teste numa transação que
sofre **rollback** no fim — nunca há COMMIT, então os callbacks são descartados.
**Solução:** no teste específico que precisa disso,
`@pytest.mark.django_db(transaction=True)` (sobrescreve o `pytestmark` do módulo).
**Origem:** Prompt 3b (pagamentos, PR #19).

### 6.6 `@patch.object` como decorator de função auxiliar embaralha os argumentos

**Sintoma:** `AttributeError: 'str' object has no attribute 'post'` — silencioso até
quebrar longe da causa.
**Causa:** decorar uma função **auxiliar** (não um método de teste) injeta o mock como
**último** argumento posicional, depois dos que o chamador passou. E sob `mypy --strict`
o decorator não esconde o parâmetro: toda chamada reprova com `Missing positional
argument`.
**Solução:** não decore a auxiliar — use `with patch.object(...):` **dentro** dela.
Resolve a ordem dos argumentos e o mypy de uma vez.
**Origem:** Prompt 3b (pagamentos, PR #19).

### 6.7 `mypy --strict` + `redis`: o ignore vai na chamada, não no import

**Sintoma:** `# type: ignore[import-untyped]` no `import redis` vira erro de "unused
ignore"; sem ele, `redis.from_url(...)` acusa `no-untyped-call`.
**Causa:** o redis-py ≥ 5 já traz `py.typed` (o import é tipado), mas a assinatura de
`from_url` não está totalmente anotada.
**Solução:** o ignore vai na linha da **chamada**.
**Origem:** Prompt 3b (pagamentos, PR #19).

### 6.8 `mypy --strict` + `django.test.Client` com headers desempacotados

**Sintoma:** `Argument 4 ... incompatible type "**dict[str, str]"; expected "bool"`.
**Causa:** o stub do `Client` tem parâmetros nomeados tipados (`follow: bool`, …) e o
mypy não consegue casar as chaves de um dict dinâmico com eles.
**Solução:** passe os headers como kwargs explícitos
(`HTTP_X_SIGNATURE=...`, `HTTP_X_REQUEST_ID=...`) em vez de `**{...}`.
**Origem:** Prompt 3b (pagamentos, PR #19).

### 6.9 `patch.object` no método do cliente esconde a camada onde o bug mora

**Sintoma:** suíte inteira verde, cobertura aparentemente boa — e um bug de
integração vivo há semanas exatamente no cliente HTTP.
**Causa:** `@patch.object(Cliente, "criar_pagamento_pix", return_value=...)`
substitui o **método inteiro**. Tudo abaixo dele — montagem do request, headers,
checagem de status, parsing do corpo — **nunca roda** em teste nenhum. O mock
devolve um dicionário perfeito que o código real nunca teria produzido.
**Solução:** desça o mock para o **transporte** com `respx` (já pinado em
`checkout`, `funil` e `pagamentos`: `respx==0.23.1`) — falsifique a *rede*, não o
seu próprio código:

```python
with respx.mock(assert_all_called=True) as mp:
    rota = mp.post("https://api.provedor.com/v1/recurso").mock(
        return_value=httpx.Response(401, json={"message": "invalid access token"})
    )
    resp = client.post("/api/celula/recurso", ...)   # atravessa a pilha inteira
assert rota.calls.last.request.headers["X-Idempotency-Key"] == chave
```

**Dois ganhos, não um:** além de enxergar o bug, você passa a poder afirmar coisas
sobre o **request que saiu** (headers, corpo, contagem de chamadas). O INV-P4 de
pagamentos tem uma cláusula — "toda escrita ao MP leva `X-Idempotency-Key` própria"
— que era **impossível de verificar** com mock de método: o header nem existia no
mundo do teste.
**Regra prática:** se o despacho fala em falha de integração (status, timeout,
payload torto), mock de método **não serve como evidência** — ele prova o
comportamento do mock. Verifique em qual camada o teste entra antes de confiar nele.
**Origem:** despacho 03 (pagamentos, fail-closed do Mercado Pago).

---

## §7 — Coordenação (humano, painéis, outros agentes)

### 7.1 Mais de uma IA no mesmo repositório

**Sintoma:** PRs aparecem mergeados sem que esta sessão tenha pedido; arquivos mudam
sozinhos no meio do trabalho.
**Causa real (investigada em PR #2 e #5):** não foi invasão — o usuário seguia, em
paralelo, instruções de **outra IA**, e rodou comandos dela sem cruzar com o que esta
sessão pediu para segurar.
**Solução:** quando mais de um agente atua no mesmo repo, cheque cada `merge`/`push`
contra o que qualquer sessão pediu para segurar; e antes de editar um arquivo
compartilhado (painéis, docs de raiz), releia-o do disco — ele pode ter mudado.
**Origem:** incidentes dos PRs #2 e #5.

### 7.2 Painel HTML "some" / cards desaparecem

**Sintoma:** os cards do painel somem; a página renderiza só o cabeçalho.
**Causa:** o JS quebrou. O caso concreto: uma crase (`` ` ``) usada para formatar
código **dentro de um template literal** — que também é delimitado por crases — fecha
a string mais cedo e quebra o parse.
**Solução:** ao editar os painéis, valide antes de considerar pronto:

```bash
node -e "const fs=require('fs');const h=fs.readFileSync('arquivos/painel-X.html','utf8');
const s=h.split('<script>')[1].split('</script>')[0];
global.document={getElementById:()=>({innerHTML:'',style:{},textContent:'',addEventListener:()=>{},querySelectorAll:()=>[]})};
new Function(s)();console.log('JS OK');"
```

**Origem:** sessão de 18/08/2026, painel da Fase D.

### 7.3 O despacho colado no chat pode divergir do card do painel

**Sintoma:** o agente entrega exatamente o que foi pedido — e mesmo assim está
desalinhado com o que o painel prometia.
**Causa concreta:** o texto cru de `PROMPTS-INICIAIS.md` foi colado no chat, mas o
card do catalogo em `painel-prompts-fase-d.html` já tinha uma versão **mais segura**
(exigia `--host` obrigatório no `seed_esqueleto`, nunca hardcoded). Ninguém percebeu
até a retrospectiva, depois do merge.
**Solução:** ao receber um despacho, se houver card correspondente no painel, compare
os dois antes de começar. Divergência é decisão do humano, não do agente.
**Origem:** Prompt 2 (catalogo, PR #15) — pendência ainda aberta.

### 7.4 O painel é parte de terminar a tarefa

`arquivos/painel-fundacao.html` é o checklist vivo do dono do projeto (leigo em
código). Atualizá-lo depois de cada mudança de estado é obrigatório e **não se
pergunta antes** (`CLAUDE.md`). Só marque item como concluído com evidência real —
confirmação de merge do usuário é **gatilho para conferir** (`gh pr view <N> --json
state,mergedBy,mergeCommit`), não substituto da conferência.

### 7.5 `AGENTS.<celula>.md` diz se a célula chama outra API — leia Fronteiras E Comunicação juntas

**Sintoma:** a receita genérica (`CAMINHO-DOURADO.md` §3, CONV-SITE) manda toda
célula pública chamar a API do catálogo para resolver Host→Site — mas seguir a
receita ao pé da letra, sem checar a constituição da célula, pode implementar uma
dependência de rede que a célula nunca deveria ter.
**Causa:** as duas seções de `AGENTS.<celula>.md` são redundantes de propósito:
toda vez que uma célula realmente consome a API de outra, isso aparece **nas duas**
— `Fronteiras → SOMENTE LEITURA` lista o `.openapi.yaml` da célula consumida, E
`Comunicação → Consome` nomeia a célula. Compare `AGENTS.checkout.md` (`SOMENTE
LEITURA: contracts/catalogo.openapi.yaml, contracts/pagamentos.openapi.yaml`;
`Consome: catalogo (ofertas/preços), pagamentos (intents)`) com `AGENTS.quiz.md`
(`SOMENTE LEITURA: contracts/eventos/quiz.completado.v1.json` — só isso; `Consome:
nada`). Ausência dos dois ao mesmo tempo não é esquecimento do autor do documento,
é a célula deliberadamente isolada — mesmo que a receita genérica a liste como
usuária de CONV-SITE.
**Solução:** antes de implementar qualquer chamada de rede a outra célula (mesmo
uma convenção "óbvia" como CONV-SITE), leia as duas seções de
`AGENTS.<sua-celula>.md` juntas. Se a constituição não autoriza (nem em Fronteiras
nem em Comunicação), a receita genérica não vale sozinha — é desvio consciente
(Lei 2 do `CAMINHO-DOURADO.md`: precisa de issue `arquitetura:`), não improviso.
No caso do quiz, a solução foi um cadastro `Site` **local** à célula (seedado via
R9), em vez do `CatalogoClient` que a receita sugere — ver
`services/quiz/LICOES.md` para o raciocínio completo e o alerta para o mantenedor
revisar essa leitura.
**Origem:** despacho do quiz (PR do Crivo), ao decidir a resolução de site.

### 7.6 Fase E (red-team): golpes paralelos colidem na MESMA linha da tabela

**Sintoma:** `git push origin main` (ou merge de um PR de docs) recusa com
"non-fast-forward", e o `git merge`/`rebase` seguinte estoura `CONFLICT (content)`
bem na tabela de `02-RED-TEAM.md` — mesmo as duas sessões tendo editado **linhas
diferentes** da tabela (uma marca o golpe 2, outra marca o golpe 3, por exemplo).
**Causa:** durante a Fase E é normal ter mais de uma sessão rodando golpes
diferentes ao mesmo tempo (§7.1) — cada uma parte do MESMO commit de
`origin/main` no início, edita sua própria linha da tabela de resultados, e a
segunda a empurrar sempre encontra a primeira já mergeada. Git resolve isso como
merge de texto puro; se as linhas tocadas forem realmente diferentes, o conflito é
só de proximidade (blocos de diff adjacentes), não de conteúdo — resolve-se
mantendo as DUAS marcações lado a lado, nunca escolhendo uma em vez da outra.
**Solução:** antes de tentar `push`/merge de uma marcação de golpe,
`git fetch origin && git rebase origin/main` (ou `git merge origin/main`) no branch
de docs; se aparecer conflito só na tabela, é quase sempre "as duas linhas devem
sobreviver" — edite o bloco de conflito juntando as duas marcações, nunca descarte
a alheia. Depois disso, o push volta a ser fast-forward.
**Origem:** golpe 2, PR #41 — colidiu com a marcação do golpe 3 (PR #34) feita por
outra sessão entre o commit local e o push.

### 7.7 LOTE: outra sessão escrevendo no SEU worktree — `git stash pop` devolve o arquivo SEM a sua edição

**Sintoma:** durante um lote paralelo, `git status` no seu worktree mostra arquivos
de OUTRA célula modificados (que você nunca tocou); e um `git stash push -- <arq>` /
`git stash pop` seu, usado para a evidência vermelho→verde (§6.1), termina "com
sucesso" (`Dropped refs/stash@{0}`) mas o arquivo volta **sem a sua edição** — ela
simplesmente evapora, sem erro nenhum.
**Causa:** duas sessões operando no MESMO diretório de worktree. A pilha de stash é
uma só por worktree: se a outra sessão empilha/desempilha entre o seu `push` e o seu
`pop`, o `stash@{0}` que você desempilha pode ser o dela (foi assim que arquivos de
checkout "apareceram" aqui), e o seu se perde na corrida. Nada valida que o stash
desempilhado é o que você empilhou.
**Solução:** (1) **commite cedo e commite para proteger** — arquivo commitado no seu
branch sobrevive a qualquer corrida; a evidência vermelha via stash deve ser feita
o mais perto possível do commit, conferindo `git stash list` antes e depois;
(2) antes de qualquer stash/rebase, `git status --porcelain` — arquivo alheio
modificado no seu worktree é sinal de colisão: **não** o commite, **não** o
descarte (é trabalho de outra sessão), siga com `git add` só dos SEUS caminhos e
`git rebase --autostash`, e **reporte a colisão no relatório final** para a
sessão-maestro resolver quem está no worktree errado; (3) se a sua edição sumiu,
reaplique-a do contexto/histórico da conversa — o Edit da ferramenta não deixa
reflog, mas o conteúdo está na sessão.
**Origem:** despacho quiz/relay-outbox (lote de 22/08/2026) — o `on_commit` de
`views.py` evaporou num stash pop; arquivos da célula checkout apareceram
modificados no worktree wt-quiz-relay, que era exclusivo do quiz.

---

## §8 — Ferramentas do agente (o harness também tem armadilha)

### 8.1 Agente delegado nasce num worktree diferente do que o despacho manda

**Sintoma:** as ferramentas de edição recusam mecanicamente qualquer caminho fora de
um worktree que o despacho nunca mencionou (`.claude/worktrees/agent-<id>`), inclusive
operações git contra o worktree que é claramente o alvo legítimo.
**Causa:** um agente disparado com `isolation: worktree` recebe um worktree **próprio**
criado pelo harness, e as ferramentas ficam confinadas a ele.
**Solução que funcionou:** não lute contra a ferramenta. Como os dois worktrees nascem
do mesmo commit, desenvolva e teste no worktree do agente e, no fim, copie os arquivos
prontos para o worktree do despacho (a ferramenta PowerShell não tem a mesma trava de
caminho), onde acontecem commit/push/PR.
**Melhor ainda:** se o despacho nomeia um worktree, dispare o agente **sem**
`isolation: worktree` — deixe-o criar o worktree do jeito que o RITOS §1 manda.
**Origem:** Prompt 3b (pagamentos, PR #19).

### 8.2 Heredoc dentro de heredoc com o mesmo delimitador

**Sintoma:** `SyntaxError: unterminated triple-quoted string literal` no Python, seguido
de `bash: syntax error near unexpected token`.
**Causa:** escrever um script Python via `python - <<'PY'` cujo conteúdo contém outro
heredoc `<<'PY'` — o delimitador interno fecha o externo antes da hora.
**Solução:** delimitadores distintos (`<<'PYEOF'` dentro de `<<'PY'`), ou escreva o
arquivo com a ferramenta de escrita em vez de heredoc. Vale para qualquer par aninhado.
**Origem:** sessão de 19/08/2026, ao endurecer `ci/freeze-de-contrato.sh`.

---

## §9 — Pendências conhecidas (não são armadilhas, são dívidas abertas)

| O quê | Estado |
|---|---|
| `seed_esqueleto` do catalogo usa env `DOMINIO_OPERACOES` com fallback hardcoded, em vez do `--host` obrigatório que o card do painel pedia | sem decisão do mantenedor |
| **Cobrança REAL em produção depende de credenciais Mercado Pago de verdade** — `MP_ACCESS_TOKEN`/`MP_WEBHOOK_SECRET` em `/opt/plataforma/env/pagamentos.env` e `MP_PUBLIC_KEY` no de checkout. A plataforma está no ar e navega sem isso (22/08/2026); a primeira venda de verdade é que não passa — e falha fechado, com 502 e log claro. De quebra: sobrou `/home/deploy/provisionamento-postgres.sql` na VPS (cópia com senhas usada no provisionamento) — apagar | mantenedor, antes do primeiro teste de venda real |
| Proteção de branch nativa do GitHub exige plano Pro; hoje o fallback é `.githooks/pre-push` | issue `mecanizar:` #1 |
| Relay do outbox (Huey → Redis Streams, R3) ainda não instanciado no checkout — o evento é gravado transacionalmente, mas ninguém publica | Fase D, despacho seguinte |
| ~~alunos não tem consumer de `pagamento.aprovado`~~ **RESOLVIDO em parte** (PR #26, `agent/alunos/matricula`): hoje existe `apps/eventos/management/commands/consume_eventos.py` + `apps/matriculas/` (models/services/handlers, idempotente por `order_id`, INV-P5) e `POST /matriculas` funciona de verdade. Confirmado rodando ao vivo em `e2e/esqueleto.sh` (container `alunos-consumer` dedicado): o evento `pagamento.aprovado` publicado por pagamentos é consumido e a `Matricula` nasce com `status=ativa` no banco de alunos, ponta a ponta. **O que falta é só** `GET /alunos/{email}/matriculas` — ainda `HttpError(501)` por design (`apps/core/api.py`, comentário "listEnrollments segue fora de escopo desta sessão") — é esse endpoint de LEITURA, sozinho, que segura o elo 8 do esqueleto e o critério 1 do DoD de `ESQUELETO-QUE-ANDA.md` | despacho pequeno e focado: implementar só `list_enrollments` lendo `Matricula.objects.filter(email=email)` — o resto da célula já funciona |
| ~~checkout não consome `pagamento.aprovado`~~ **RESOLVIDO**: `apps/pedidos/management/commands/consume_eventos.py` existe e funciona — confirmado ao vivo em `e2e/esqueleto.sh` (container `checkout-consumer` dedicado), `GET /api/checkout/pedidos/{id}.status` vai de `aguardando_pagamento` para `pago` de verdade depois do webhook aprovado | — |
| **Evento que faz o handler estourar fica pendente para sempre — a reentrega é possível, mas ninguém a executa.** Medido em 21/08/2026 (despacho infra/consumers), já com o `alunos` **depois** do PR #43: publiquei um `pagamento.aprovado` sem `customer`; o handler estourou `KeyError`, a transação externa desfez o registro (`EventoProcessado = 0` — **o fix do #43/#46 faz exatamente o que promete**), o container morreu e o `restart: unless-stopped` o trouxe de volta. Um evento bom publicado em seguida foi processado normal: **não é crash-loop**. Mas o envenenado segue em `XPENDING` do grupo com `delivery-count = 1`, **nunca reentregue** — `xreadgroup(..., ">")` só entrega mensagem nova, e nenhum consumer chama `XAUTOCLAIM` nem relê o próprio PEL com `XREADGROUP ... 0`. Os PRs #43/#46/#47 devolveram a *possibilidade* de reentregar (`alunos`, `leads` e `mensageria` já registram e efetivam na mesma transação; `checkout` não tem `EventoProcessado`, o handler dele é um `.update()` idempotente) — **o que falta é a peça que de fato reentrega**, e ela não existe em nenhuma das quatro | ✅ **RESOLVIDO 22/08/2026 (lote 2)** — as 4 células reivindicam presas (`XAUTOCLAIM`, idle ≥ 60s, constantes `IDLE_MS_REENTREGA`/`MAX_ENTREGAS` iguais nas quatro) e movem para `<stream>.dlq` na 5ª entrega (payload original + motivo/delivery_count/movida_em, ACK na origem, log ERROR com o event_id): PRs #74 alunos, #72 leads, #73 mensageria, #75 checkout, todos com teste-guarda contra Redis real e evidência vermelho→verde por patch. O que resta em aberto: a `.dlq` ainda NÃO tem consumidor — reprocessar é manual (`XRANGE` + `XADD` de volta) e o alarme é o log ERROR; se aparecer volume, é despacho pequeno |
| ~~**pagamentos não valida o status HTTP da resposta da Mercado Pago ao criar uma intent Pix**~~ **RESOLVIDO** (despacho 03, `agent/pagamentos/failclosed`): `_post` falha fechado em todo não-2xx, em timeout e em corpo não-JSON; `core/gateway.py` recusa traduzir 2xx incompleto e levanta `FalhaNoProvedor`; a API devolve **502** em vez de 201, e o replay de INV-P4 virou o caminho de reparo que não existia (completa a intent incompleta com a MESMA `X-Idempotency-Key`, que o MP deduplica). Evidência vermelho→verde no caso 401 colada no PR; testes descem para o transporte com `respx` (§6.9) | **falta só o registro formal:** o 502 ainda não está no contrato congelado e o invariante novo ainda não está em `INVARIANTES.md` — os dois são CODEOWNERS, ver §1 H7 |
