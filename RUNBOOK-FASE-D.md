# RUNBOOK — Fase D: o Esqueleto que Anda

> **Para quem:** qualquer agente que precise RODAR, VERIFICAR, DEPURAR ou
> ESTENDER a transação sandbox de ponta a ponta entregue na Fase D. Isto não é
> um brief de tarefa nova — é o manual de operação do que **já existe e já
> está em `main`**. Para o mapa geral do projeto, veja `PLAYBOOK.md` primeiro.
> Para o que a transação representa e por que ela existe, veja
> `ESQUELETO-QUE-ANDA.md` (não duplicado aqui).

## 1. O que a Fase D entregou (fato, não plano)

8 elos, de ponta a ponta, confirmados verdes contra sandbox real do Mercado
Pago em 21/08/2026 (PRs #15, #16, #17, #19, #24, #25, #26, #27, #28, #29,
#30, #31, #32):

```
seed (catalogo) → sessão (checkout) → pedido/snapshot (checkout) →
cobrança (pagamentos, intent REAL na MP sandbox) → webhook assinado
(pagamentos, DEBUG=1) → outbox (pagamentos) → relay/Redis Streams →
matrícula (alunos)
```

| Elo | Célula | Onde mora |
|---|---|---|
| 1. seed | catalogo | `services/catalogo/apps/core/management/commands/seed_esqueleto.py` |
| 2. sessão | checkout | `POST /api/checkout/sessoes` — `services/checkout/apps/pedidos/` |
| 3. pedido/snapshot | checkout | `POST /api/checkout/sessoes/{id}/pedido` — INV-P1/P2 |
| 4. cobrança | pagamentos | `services/pagamentos/pagamentos/core/gateway.py` + `providers/mercadopago/` |
| 5. webhook | pagamentos | `POST /debug/simulate-webhook` (só com `DEBUG=1`) — `pagamentos/api/webhooks.py` |
| 6. outbox | pagamentos | `core/models.py` (`OutboxEvent`, `emitir()`, `transicionar_e_emitir()` — INV-P6) |
| 7. relay | pagamentos → Redis | `relay_outbox()`, stream `eventos.pagamento.aprovado` |
| 8. matrícula | alunos | consumer em `apps/eventos/management/commands/consume_eventos.py` + `apps/matriculas/` (INV-P5) |

Em paralelo, dentro do que o e2e realmente exercita: `checkout` marca o pedido
como `pago` via seu próprio consumer
(`apps/pedidos/management/commands/consume_eventos.py`, container
`checkout-consumer`) — o script confere isso como diagnóstico, não como elo
numerado.

**`mensageria` e `leads` NÃO participam do `make esqueleto`.** O diagrama de
`ESQUELETO-QUE-ANDA.md` menciona mensageria, mas isso é o plano, não o que
roda: `e2e/docker-compose.e2e.yml` sobe apenas `postgres`, `redis`, `catalogo`,
`pagamentos`, `checkout`, `checkout-consumer`, `alunos`, `alunos-consumer`, e
as duas células não aparecem em `e2e/esqueleto.sh`. As duas têm consumer
próprio testado no `make ci` da célula — só não são cobertas de ponta a ponta
por este harness.

## 2. Rodar localmente

Pré-requisitos: Docker rodando (suba o Docker Desktop no INÍCIO da sessão, em
background — `ARMADILHAS.md` §1 item H4: parti-lo frio no meio do trabalho
custa 1–2 min parados) e `e2e/.env.e2e` preenchido (copie de
`e2e/.env.e2e.exemplo` — precisa de `MP_ACCESS_TOKEN` **sandbox real**, não o
fake de CI; ver §3 e `ARMADILHAS.md` §1 item H5 se não souber onde conseguir
um).

**Estado agora:** `e2e/.env.e2e` **não existe no disco** — só o `.exemplo`.
Até o mantenedor restaurar a credencial (§3), `make esqueleto` sai com exit 2
e uma mensagem clara, sem tentar rodar. Isso é o comportamento correto, não
uma falha do harness.

```bash
make esqueleto          # == bash e2e/esqueleto.sh
```

O script sobe `e2e/docker-compose.e2e.yml` (serviços: `postgres`, `redis`,
`catalogo`, `pagamentos`, `checkout`, `checkout-consumer`, `alunos`,
`alunos-consumer`), roda o seed, e percorre os 8 elos via `curl`, imprimindo
`✅`/`❌` elo a elo. Qualquer `❌` falha o script (exit ≠ 0) e imprime o motivo
mais provável — leia a mensagem antes de investigar do zero.

**Saída esperada no final:** `✅ ESQUELETO ANDOU — todos os 8 elos verdes.`

**`make esqueleto` é MANUAL — não roda no CI, apesar do que a doutrina promete.**
`ESQUELETO-QUE-ANDA.md` afirma que ele roda "no CI a cada PR de célula que
participe do caminho". Isso não acontece: `esqueleto` não aparece em nenhum
workflow de `.github/workflows/` — existe só como alvo do `Makefile` da raiz.
Ou seja, **nenhum PR é barrado hoje por quebrar o caminho ponta a ponta**;
quem roda é você, quando lembrar. Se isso for indesejado, é issue
`mecanizar:`, não conserto de sessão.

## 3. Credencial sandbox do Mercado Pago (pré-requisito do elo 4)

O elo "cobrança" chama a API **real** do Mercado Pago
(`services/pagamentos/pagamentos/providers/mercadopago/client.py`, sem modo
mock) mesmo em dev local — só o webhook é simulado (`/debug/simulate-webhook`,
elo 5). Sem um `MP_ACCESS_TOKEN` `TEST-...` real (não o fake usado no CI), o
elo 3/4 falha com erro de autenticação da própria MP, não um bug do script.

O mantenedor guarda essa credencial fora do repo, num compartilhamento de rede
pessoal (correto, por INV-P8 — nunca deveria estar num arquivo versionado).
**Se você precisa rodar `make esqueleto` e não tem a credencial: peça ao
mantenedor onde está**, em vez de tentar gerar uma nova ou de commitar
qualquer valor de teste. Nunca escreva o valor real em nenhum arquivo
versionado (nem aqui) — só em `e2e/.env.e2e`, git-ignorado.

## 4. Verificar cada elo isoladamente (se precisar depurar 1 sem rodar tudo)

Comandos extraídos ao pé da letra de `e2e/esqueleto.sh` (não invente variação
própria — o script já resolve `DOMINIO_OPERACOES` do `.env.e2e` e usa tokens
fixos de dev, sem segredo real envolvido). Rode a partir de `e2e/`.

**O `--env-file` não é opcional.** `docker-compose.e2e.yml` declara
`MP_ACCESS_TOKEN: ${MP_ACCESS_TOKEN:?...}` — a forma `:?` aborta **qualquer**
subcomando do compose (inclusive `exec`) se a variável não estiver carregada, e
não existe `.env` para o compose pegar sozinho. Por isso o script define uma
função e a usa em toda invocação; copie-a em vez de digitar `docker compose`
na mão:

```bash
# a mesma função de e2e/esqueleto.sh:39 — use DC no lugar de `docker compose`
DC() { docker compose -f docker-compose.e2e.yml --env-file .env.e2e "$@"; }

DC up -d          # sobe o compose, se ainda não estiver de pé

DOMINIO_OPERACOES="$(grep -E '^DOMINIO_OPERACOES=' .env.e2e | cut -d= -f2-)"
DOMINIO_OPERACOES="${DOMINIO_OPERACOES:-esqueleto.e2e.local}"
TOKEN_CHECKOUT="e2e-token-e2e-para-checkout"
TOKEN_PAGAMENTOS="e2e-token-checkout-para-pagamentos"
TOKEN_ALUNOS="e2e-token-e2e-para-alunos"

# elo 1 — seed idempotente (rodar 2x não duplica). SEM --host: o comando lê a
# env DOMINIO_OPERACOES, já injetada no container pelo compose (pendência
# conhecida, RUNBOOK §7 — não invente uma flag --host, ela não existe).
DC exec -T catalogo python manage.py seed_esqueleto

# elo 2 — sessão (o header Host: é OBRIGATÓRIO — é dele que o CONV-SITE resolve
# o site; sem ele, 404 "site desconhecido", não um bug de sessão)
curl -sS -X POST "http://localhost:8002/api/checkout/sessoes" \
  -H "Host: ${DOMINIO_OPERACOES}" -H "Authorization: Bearer ${TOKEN_CHECKOUT}" \
  -H "Content-Type: application/json" -d '{"offer_slug":"curso-esqueleto"}'
# guarde o "id" da resposta como SESSION_ID

# elo 3 — pedido (snapshot congela — INV-P1/P2; a cobrança em pagamentos
# acontece embutida aqui, síncrona — não é uma chamada separada)
curl -sS -X POST "http://localhost:8002/api/checkout/sessoes/${SESSION_ID}/pedido" \
  -H "Host: ${DOMINIO_OPERACOES}" -H "Authorization: Bearer ${TOKEN_CHECKOUT}" \
  -H "Content-Type: application/json" \
  -d "{\"customer\":{\"email\":\"${EMAIL}\",\"name\":\"Aluno Esqueleto\"},\"method\":\"pix\"}"
# guarde "order_id" e "payment.intent_id" da resposta

# elo 4 — intent na MP sandbox
curl -sS "http://localhost:8003/api/pagamentos/intents/${INTENT_ID}" \
  -H "Authorization: Bearer ${TOKEN_PAGAMENTOS}"

# elo 4b — o mp_payment_id NÃO vem nesse GET (provider_payment_id não existe no
# contrato público). O script o lê direto do banco — é este valor que prova que
# a MP respondeu de verdade: vazio = credencial TEST- inválida, ver §3.
MP_PAYMENT_ID="$(DC exec -T pagamentos python manage.py shell -c "
from pagamentos.core.models import Intent
print(Intent.objects.get(id='${INTENT_ID}').provider_payment_id)" | tr -d '\r' | tail -n1)"
echo "mp_payment_id=$MP_PAYMENT_ID"

# elo 5 — webhook simulado (só existe com DEBUG=1; DEBUG=0 ⇒ 404). SEM
# Authorization — o payload usa o mp_payment_id do elo 4b, não intent_id.
curl -sS -X POST "http://localhost:8003/debug/simulate-webhook" \
  -H "Content-Type: application/json" \
  -d "{\"method\":\"pix\",\"mp_payment_id\":\"${MP_PAYMENT_ID}\",\"status\":\"approved\"}"

# elo 6 — outbox (via shell da célula, não existe endpoint HTTP para isto)
DC exec -T pagamentos python manage.py shell -c "
from pagamentos.core.models import OutboxEvent
print(OutboxEvent.objects.filter(event='pagamento.aprovado', payload__order_id='${ORDER_ID}', published_at__isnull=False).exists())"

# elo 7 — relay (Redis Streams)
DC exec -T redis redis-cli XRANGE eventos.pagamento.aprovado - +

# elo 8 — matrícula (o critério de aprovação é este GET, não o estado do banco)
curl -sS "http://localhost:8004/api/alunos/alunos/${EMAIL}/matriculas" \
  -H "Authorization: Bearer ${TOKEN_ALUNOS}"
```

Portas fixas do compose de e2e: catalogo `:8001` (sem rota HTTP no caminho
numerado — só o seed via `manage.py`), checkout `:8002`, pagamentos `:8003`,
alunos `:8004`. Os tokens acima são fixos de dev/e2e (definidos no topo de
`e2e/esqueleto.sh` e no `environment:` do compose) — nunca confunda com
credencial de produção (INV-P8); a única credencial real neste caminho é o
`MP_ACCESS_TOKEN` da §3.

## 5. Rodar na VPS (staging) com webhook REAL do MP + cartão sandbox APRO

**Ainda sem evidência registrada** (critério 2 de `ESQUELETO-QUE-ANDA.md`) —
isto é uma pendência aberta, não um "já fizemos e esqueci de documentar".

Diferença do caminho local: não existe `/debug/simulate-webhook` em
`DEBUG=0` — o webhook chega de verdade em
`/api/pagamentos/webhooks/mp/card` (ou `/pix`), assinado pelo MP real, ao
usar o cartão de teste **APRO** (aprova automaticamente) contra a credencial
sandbox. `deploy-celula.yml` já publica cada célula na VPS a cada merge em
`services/**` — a infraestrutura para este passo já existe, falta rodar o
teste manual e colar a evidência crua no PR de fechamento da Fase D/E.

## 6. Rollback (RITOS.md §4 — a resposta canônica a qualquer emergência)

**Pelo pipeline — o agente dispara sozinho, não há passo humano** (desde
23/08/2026; antes disto o rollback só existia como bloco de SSH, e agente não
tem chave — Lei 5):

```bash
gh workflow run rollback.yml -f celula=checkout -f alvo=<sha-anterior> -f motivo="..."
gh run list --workflow=rollback.yml --limit 1     # pegue o id
gh run view <id> --json status,conclusion         # veredito REAL (§5.10 das ARMADILHAS)
```

`<sha-anterior>` é o sha COMPLETO de um commit da `main` em que **esta** célula
foi construída — histórico do `deploy-celula` (cada deploy publica `:sha` e
`:main` em `ghcr.io/abundanciabr/plataforma-<celula>`), ou:

```bash
gh api users/abundanciabr/packages/container/plataforma-checkout/versions \
  --jq '.[] | {tags: .metadata.container.tags, created: .created_at}'
```

`ci/rollback.py` valida antes de qualquer SSH (célula do manifesto · alvo
ancestral da `main` · imagem existente no registry) e o job que entra na VPS é
pulado se algo reprovar. **Desfazer: o mesmo comando com `alvo=main`** — e o pin
não persiste sozinho, o próximo deploy da célula já volta para `:main`.

Rollback de uma célula não toca nenhuma outra — mas toca TODOS os serviços dela
(`checkout`, `checkout-consumer`, `checkout-relay`), pela mesma razão do
`deploy-celula`: deixar o auxiliar na imagem nova seria rodar duas versões do
mesmo código, em silêncio, no meio de uma emergência.

### Critério 3 de `ESQUELETO-QUE-ANDA.md` — ✅ EXECUTADO em 23/08/2026

Drill cronometrado (< 5 min do "decidi" ao "voltou"), na VPS de produção, com o
`checkout` — é também o golpe 14 de `02-RED-TEAM.md`, o único golpe "do bem" do
rito. Alvo escolhido de propósito: `825ff857` (o commit ANTES do PR #77), cuja
diferença é visível de fora — as páginas do checkout respondiam 404 sem o fix
das rotas sem prefixo. Assim o drill não prova só "o container reiniciou": prova
que a produção passou a servir a outra versão, medido pela internet pública.

| | run | veredito | medido de fora | na VPS |
|---|---|---|---|---|
| **volta** (`alvo=825ff857`) | [32678099024](https://github.com/abundanciabr/sitesdoreino/actions/runs/32678099024) | success | mudou em **t+30s**, run verde em **t+76s** | `SEGUNDOS_NA_VPS=42` |
| **desfaz** (`alvo=main`) | [32678175555](https://github.com/abundanciabr/sitesdoreino/actions/runs/32678175555) | success | voltou em **t+58s**, run verde em **t+69s** | `SEGUNDOS_NA_VPS=32` |

**76 segundos** do "decidi" ao "voltou", contra os 300 do critério. Os três
serviços da célula (`checkout`, `checkout-consumer`, `checkout-relay`) trocaram
juntos e terminaram `healthy` nos dois sentidos — `docker compose images` no log
de cada run mostra a tag antes e depois. Amostras externas:
`https://meshcraft.top/checkout/curso-teste/` 200 → 404 → 200; `INV-P11` (host
desconhecido = 404) intacto no fim.

**O que o drill ensinou e não estava escrito em lugar nenhum:** existe uma
janela de ~30s de **502** durante a troca — o Traefik fica sem backend saudável
enquanto o container é recriado. Rollback não é instantâneo do ponto de vista de
quem está no site; é rápido. Numa emergência real isso é aceitável (trocar 502
por 502) e é bom saber de antemão, para não achar que o rollback falhou ao ver
502 no primeiro `curl`. Registrado em `ARMADILHAS.md` §5.14.

Falta para fechar a Fase D: o critério 2 (esqueleto na VPS com cartão APRO e
webhook real do MP — §5 acima) e o critério 4 (PR de fechamento com a saída crua
dos dois runs).

## 7. Pendências herdadas — o que ainda NÃO é "de verdade" (não confunda com bug)

Lista viva. `ARMADILHAS.md` §9 cobre o mesmo terreno, mas **está parcialmente
desatualizada** — ela ainda descreve `GET /alunos/{email}/matriculas` como stub
501 "e o que falta é só" implementá-lo, quando o PR #32 já o fechou (o elo 8
deste runbook depende dele funcionando, e funciona). Cruze as duas listas em
vez de confiar numa só; se for corrigir §9, isso é PR de docs à parte.

| Pendência | Onde | Por quê ficou assim |
|---|---|---|
| `seed_esqueleto` usa env `DOMINIO_OPERACOES` com fallback, não `--host` obrigatório | catalogo | Divergência entre o despacho colado e a versão mais seg do painel — nunca resolvida; decisão do mantenedor |
| ~~`pagamentos` não valida o status HTTP da resposta da MP~~ **RESOLVIDO** (PR #44, 21/08/2026): resposta do provedor só vira sucesso depois de validada (status + payload), testes na camada de transporte com `respx`. **Efeito colateral aberto:** `POST /intents` agora devolve 502 quando o MP falha, e 502 não está no contrato congelado — ver `ARMADILHAS.md` §1 H7 | pagamentos | — |
| ~~Consumers de evento não existiam em produção~~ **RESOLVIDO NO GIT** (PR #45, 21/08/2026): 4 consumers + worker Huey + healthchecks no `infra/docker-compose.yml`, e o deploy descobre os auxiliares do próprio compose. ~~MAS o compose não chega à VPS por pipeline nenhum~~ **mecanizado** (despacho 04): `.github/workflows/deploy-infra.yml` sincroniza compose+traefik para `/opt/plataforma/` a cada merge na `main` que os toque — o merge do próprio PR dispara a primeira sincronização, que entrega estes consumers; **provado em 22/08/2026** (H11 ✅): run 32538231311 verde, `docker compose ps` com os 16 serviços em `running` — células `healthy`, consumers e worker Huey no ar em produção. Dois remendos moram no compose até as células serem corrigidas (H10: healthcheck TCP do checkout, bootstrap Huey da mensageria) | infra | — |
| Dedup de evento commitava ANTES do efeito — **RESOLVIDO em 3 células** (alunos PR #43, leads PR #46, mensageria PR #47; lição em `ARMADILHAS.md` §4.12). O consumer do checkout não tinha o bug (idempotência por estado, sem `EventoProcessado`) | alunos, leads, mensageria | — |
| **`checkout` NÃO publica `pedido.criado` — ninguém faz o relay** | checkout | `apps/pedidos/emitir.py` só grava a linha na outbox; não há `on_commit`, `xadd`, `config/huey.py` nem `tasks.py` na célula. O evento nasce e **fica parado no banco** — não chega ao Redis Streams nem a consumidor nenhum. Não confunda com o caso de pagamentos (linha abaixo): aqui não é "falta a rede de segurança", é "falta o relay inteiro" |
| Relay do outbox sem periodic task Huey (rede de segurança) em `pagamentos` | pagamentos | Aqui o relay EXISTE (`core/models.py`: `relay_outbox()` + `transaction.on_commit`) e publica na hora; o que falta é só o periodic task de retry — se a publicação falhar, o evento só é republicado por chamada manual |
| `alunos` bridge (integração externa) desligado | alunos | Fora de escopo da Fase 0 por design — `apps/bridge` existe, flag off |
| `mensageria` com provedores stub (só loga) | mensageria | SMTP/WhatsApp reais ficam para despacho futuro |
| `quiz` resolve Host→Site por cadastro LOCAL, não via API do catalogo | quiz | Decisão aceita, `AGENTS.quiz.md` autoriza; nada verifica automaticamente se o `site_id` do seed bate com o do catálogo — ver `services/quiz/LICOES.md` |
| VPS com webhook real + cartão APRO (critério 2) | e2e/VPS | Ver §5 acima |
| Drill de rollback cronometrado (critério 3) | e2e/VPS | Ver §6 acima — é também o golpe 14 da Fase E |

## 8. Troubleshooting rápido (sintoma → onde procurar)

| Sintoma | Vá direto para |
|---|---|
| Elo 3/4 falha com erro de autenticação da MP | §3 acima — credencial `TEST-` sandbox real ausente/inválida |
| `make esqueleto` trava ou os dois consumers morrem no boot com erro de `django_migrations` | `ARMADILHAS.md` §3.13 (migrate concorrente) |
| `psql`/init do compose conecta no banco errado (`database "dev" does not exist`) | `ARMADILHAS.md` §3.11 |
| Container Postgres do compose de e2e falha por causa de um `.sh` com CRLF | `ARMADILHAS.md` §3.12 |
| `respx`/mocks de webhook não batem, ou fura assinatura sem 403 | `INVARIANTES.md` INV-P10 + `ARMADILHAS.md` §6.2 |
| `AttributeError: DoesNotExist`/`objects` num handler | `ARMADILHAS.md` §4.1 (model Django sombreado por `ninja.Schema` de mesmo nome) |
| `/healthz` começou a devolver 404 depois de mexer em middleware | `ARMADILHAS.md` §4.5 |
| `make contrato-check` "OK" mas você alterou a API | `ARMADILHAS.md` §5.7 + `INVARIANTES.md` INV-CI01 |
| Ambiente Windows: `python3`/`make` não encontrados, acento quebrado, path `/tmp` sumindo | `ARMADILHAS.md` §3 inteiro |
| Run do `deploy-infra`/`deploy-celula` vermelho no passo da VPS | `gh run view <id> --log-failed` diz onde parou. Causas já mapeadas: ghcr sem login (H13), env incompleto — `DJANGO_SECRET_KEY` etc. (§3.16 vizinho), banco não provisionado. Repetir sem novo merge: `gh run rerun <id> --failed`. Veredito SEMPRE por `gh run view --json status,conclusion` (§5.10) |

## 9. O que NÃO fazer aqui

- Não "conserte" a credencial de MP gerando uma nova sem falar com o
  mantenedor (§3).
- Não trate uma pendência da §7 como bug de sessão — são decisões já
  registradas; se for reabrir alguma, é `issue arquitetura:`, não edição
  silenciosa.
- Não confunda "rodou local verde" com "rodou na VPS real" — são linhas
  diferentes na tabela de `INVARIANTES.md` ("LOCAL VERIFIED" vs "CANONICAL CI"
  vs "MERGE PROTECTED"), e este runbook trata do primeiro; §5/§6 são o que
  ainda falta para fechar os outros.
