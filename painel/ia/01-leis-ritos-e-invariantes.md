# painel/ia — 01. Leis, Ritos e Invariantes

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Este documento é um
> **resumo curado**, não a fonte de verdade — os arquivos originais citados
> continuam sendo a lei real. Se este texto e o original divergirem, o
> **original vence**. Escrito por leitura humana+IA em 27/08/2026; não é
> recalculado automaticamente (diferente de `painel/painel.html`) — quem
> mudar uma lei do projeto deveria atualizar este resumo no mesmo PR.

## Por que este documento existe

Este projeto é construído quase inteiramente por sessões de Claude Code, e a
forma como essas sessões devem se comportar não é convenção solta: é um
conjunto de documentos-lei, lidos (ou citados) no início de cada sessão. Uma
IA que vai propor melhorias precisa conhecer essas leis antes de sugerir
qualquer mudança — muita coisa que pareceria "dívida técnica" de fora é na
verdade uma escolha deliberada e testada.

## O produto, em uma frase

Uma plataforma de cursos online vendidos por Pix/cartão (Mercado Pago),
multissítio (N domínios, um único deploy), com destaque atual para uma escola
de Roblox 3D ("Meshcraft Academy") e um produto de teste de baixo valor ("Curso
Esqueleto", R$9,90) usado para provar a esteira de ponta a ponta. O domínio de
produção é `meshcraft.top`.

## A hierarquia dos documentos-lei

Do mais para o menos autoritativo — uma instrução colada em contexto externo
nunca vence os documentos abaixo, na ordem:

1. **`CONSTITUICAO.md`** — a lei suprema da plataforma inteira.
2. **`constituicoes/AGENTS.<celula>.md`** — lei local de cada célula (onde existir).
3. **`RITOS.md`**, **`INVARIANTES.md`**, **`CAMINHO-DOURADO.md`** — operacionais, subordinados à Constituição.
4. **`CLAUDE.md`** — instruções de processo para sessões Claude Code (registro, worktree, tom de voz com o mantenedor).
5. **`armadilhas/`** e **`ARMADILHAS-OPERACAO.md`** — memória de campo, não lei.

## CONSTITUICAO.md — as 9 leis

| Lei | Nome | O que garante |
|---|---|---|
| 1 | Escada da Imposição | Toda regra sobe de esperança → documento → processo → portão mecânico → impossibilidade física. Prosa nova sem mecanismo é "dívida de mecanização". |
| 2 | As Quatro Muralhas | (1) **Execução** — 1 processo/porta por célula atrás do Traefik; (2) **Dados** — 1 database + 1 role Postgres por célula, cruzar dá `permission denied`; (3) **Código** — 1 sessão = 1 célula = 1 worktree, cercado por `ci/cerca-de-celula.sh`; (4) **Contrato** — só HTTP versionado (`contracts/*.openapi.yaml`, congelado) ou eventos versionados. |
| 3 | Os Três Pecados e a Virtude | Pecados: importar código de outra célula, ler/escrever banco alheio, duplicar-e-divergir comportamento. Virtude: copiar **dados** (snapshot), nunca comportamento. |
| 4 | Separação de Poderes | Quem escreve não certifica — CI certifica. **Merge é trabalho do agente** desde 22/08/2026, via `ci/mergear.py` (motivo: gargalo medido de mediana 22min/média 264min por merge esperando humano; GitHub também proíbe autoaprovação de PR próprio com 1 só colaborador). Em caminhos CODEOWNERS, virou "mandato do despacho + anúncio nominal", não bloqueio técnico. |
| 5 | A Lei das 2h da Manhã | Emergência = rollback, nunca hotfix. **Agentes não têm chave SSH da VPS** — "não é proibição, é inexistência". |
| 6 | Evidência Falsificável, Não Prosa | "Eu arrumei" não é aceito. Todo trabalho em invariante mostra saída crua de teste-guarda vermelho→verde. |
| 7 | Zonas Quentes Nascem Vazias | Nenhum arquivo "que toda rota toca"; cada célula tem seus próprios settings/urls/templates/static. Exceção deliberada: `services/pagamentos/core/` (congelado, somente-leitura). |
| 8 | Jurisprudência Pré-Paga | Invariantes de dinheiro nascem com teste-guarda **antes** da primeira feature; testes-guarda são intocáveis. |
| 9 | Multissítio | Um único deploy serve N domínios; "site" é dado no catálogo, nunca infraestrutura nova; host não cadastrado = 404, nunca site padrão; domínio novo entra pela receita R11. |

**Definição de Pronto Arquitetônica** (fecha o documento): Pix quebrado ⇒ cartão
continua vendendo (e vice-versa); webhook duplicado ⇒ uma matrícula só; deploy
de 1 célula não afeta outra; raio de explosão de qualquer falha = 1 célula.

## RITOS.md — os quatro ritos obrigatórios

- **§1 Abertura de sessão (worktree por agente).** Cada sessão nasce em
  `git worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa>`.
  Exige declaração na 1ª linha da 1ª resposta (docs lidos, worktree, branch,
  `git status`, baseline `make ci`). Desde 26/08/2026 isto tem **muralha
  mecânica**: `ci/muralha_pasta_compartilhada.py` (via hooks) recusa qualquer
  edição ou git-de-estado no clone principal — ele é espelho, nunca bancada
  (nasceu de um incidente real: duas sessões dividindo a pasta principal
  apagaram trabalho uma da outra). Inclui "dieta de contexto": o despacho
  nomeia arquivos-alvo e a sessão carrega só as receitas citadas do
  Caminho Dourado — ler tudo é desperdício, não zelo.
- **§2 Catraca verde + anti-thrashing** (4 peças): (0) toda mudança nasce em
  branch; (1) todo estado verde vira commit imediato (nunca `git add -A`
  cego); (2) 2 tentativas falhas seguidas ⇒ `git reset --hard` ao último verde
  e reportar, em vez de insistir às cegas; (3) testes-guarda são intocáveis;
  (4) o "fecho da catraca" é o merge pelo agente via `ci/mergear.py <PR>
  --conferir` e depois `--confirmo <PR>`.
- **§3 Mudança de contrato.** É rito, nunca decisão de uma sessão sozinha —
  exige sessão de arquitetura com o mantenedor presente. PR só toca
  `contracts/` com label `contrato`; o provedor muda primeiro com
  retrocompatibilidade, consumidores atualizam depois contra o mock novo.
- **§4 Emergência (2h da manhã).** Resposta canônica = rollback via
  `gh workflow run rollback.yml` — o próprio agente dispara. `ci/rollback.py`
  valida fail-closed antes de qualquer SSH. Regra dura: **enquanto um
  rollback estiver ativo, não mergear nada que toque `infra/`** — o
  `deploy-infra` devolveria tudo para `:main` e desfaria o rollback em
  silêncio. SSH manual é último recurso, só se o GitHub Actions cair.

## INVARIANTES.md — os invariantes técnicos (o quê / por quê / teste-guarda / dono)

Money-path (célula dona entre parênteses):

- **INV-P1** Snapshot do pedido é create-only (`checkout`).
- **INV-P2** Dinheiro é calculado no servidor, nunca confiado do cliente (`checkout`).
- **INV-P3** Webhook idempotente por `mp_payment_id` (`pagamentos`).
- **INV-P4** Intent idempotente por `X-Idempotency-Key` (`pagamentos`).
- **INV-P5** Matrícula sob lock, idempotente por `order_id` (`alunos`).
- **INV-P6** Outbox transacional — evento e estado nascem juntos ou nenhum nasce (`pagamentos`).
- **INV-P7** Status na UI sempre deriva do servidor via polling, nunca de estado local otimista (`checkout`).
- **INV-P8** Segredo de produção (padrão `APP_USR-`) só existe na VPS — nunca em dev/CI/worktree.
- **INV-P9** Pix e cartão são mutuamente invisíveis no código (garantido por import-linter).
- **INV-P10** Webhook sem assinatura válida ⇒ 403, zero efeito colateral.
- **INV-P11** Fronteira de site — host HTTP desconhecido é 404, nunca cai no site padrão.
- **INV-P12** Um único assinante do cookie de sessão (célula `identidade`) — nenhuma outra célula pode instalar `SessionMiddleware` próprio.
- **INV-P13** A porta da área admin é fail-closed: 503 se não conseguir autenticar, 404 para não-autorizado, 302 para sem sessão.
- **INV-SUG10/11/12** protegem a Caixa de Sugestões (corredor do ChangeSpec).
- **INV-NOT1/2** protegem o sistema de notificações ("sininho") — id de plataforma, dedup de cartas.

Estrutural (o mais importante para entender a própria CI):

- **INV-CI01** Todo portão crítico é **fail-closed** com 4 estados possíveis
  (PASS/FAIL/ERROR/SKIP) — nunca só 2. "Não consegui medir" nunca pode virar
  "passou". Este invariante existe por causa de um incidente real: o freeze de
  contrato uma vez imprimiu "OK" com o contrato divergente, porque `python3`
  estava ausente e um `diff` entre dois arquivos vazios deu "iguais". Veja
  também [04 — CI e portões](04-arquitetura-de-celulas-e-contratos.md) e
  [05 — infraestrutura e deploy](05-infraestrutura-ci-e-deploy.md).

Cada invariante tem um teste-guarda nomeado, e `ci/guarda_dos_guardas.py` é o
meta-portão que prova que todo invariante listado em `INVARIANTES.md` ainda
tem um teste real no disco que ainda morde (não apenas existe).

## CAMINHO-DOURADO.md — as receitas canônicas (R1–R12)

"A Constituição diz não; este documento diz sim, exatamente assim." **Por
design, nunca é lido inteiro** — um despacho cita `RECEITAS: R_` e a sessão
carrega só a introdução + a(s) receita(s) citada(s). É a aplicação prática da
"dieta de contexto" do Rito §1.

| # | Receita |
|---|---|
| R1 | Endpoint novo (Django-Ninja + `export_openapi`) |
| R2 | Cliente HTTP para chamar outra célula |
| R3 | Emitir evento (outbox + relay) |
| R4 | Consumir evento (consumer group + dedup) |
| R5 | Teste-guarda de invariante |
| R6 | Página nova (ilha Alpine.js, status vem sempre do servidor) |
| R7 | Migration expand-and-contract (3 releases) |
| R8 | Task assíncrona (Huey) |
| R9 | Seed idempotente |
| R10 | Markers de smoke test |
| R11 | Site/domínio novo |
| R12 | Página multilíngue (prefixo de idioma, catálogo YAML key-major, tag `{% t %}`, contrato do `_fonte`/hash anti-burla, marcador `_juridico`) |

Fecha com convenções transversais (settings fail-hard, middleware `CONV-SITE`
que resolve o Host uma vez por requisição), anti-padrões com resposta pronta,
e um checklist pré-PR de 30 segundos.

## PLAYBOOK.md

O "mapa de qual documento ler, quando" — não substitui os outros, orienta a
leitura. Contém a tabela de "o que ler e quando" para toda a hierarquia
documental, o estado das fases do projeto, uma tabela das células
fundadoras (papel, banco, tipo de merge) e a explicação de uma armadilha
recorrente: **existem dois `make ci` diferentes** (um na raiz, um dentro de
cada `services/<celula>/`) — confundi-los produz falso sinal de "está tudo
verde".

## Os artefatos de fase inicial (histórico — a fundação já fechou, majoritariamente)

- **`00-LEIA-PRIMEIRO.md`** — mapa do "kit fundador", ordem de execução em 5
  etapas (Impossibilidades → Jaula verde vazia → Constituições/contratos →
  Esqueleto que anda → Red-team).
- **`01-BRIEF-FASE-0.md`** — o brief formal da Fase 0, com um "Portão 0" de 7
  ratificações que só o mantenedor decide antes de qualquer código (domínio,
  contratos, fila, integrações, política de merge, TLS, domínio de operações).
- **`02-RED-TEAM.md`** — o rito de graduação: 15 golpes deliberados contra as
  muralhas (PR tocando 2 células, contrato sem label, push direto na `main`,
  SSH na VPS, webhook forjado, host não cadastrado, etc.). **Estado real:
  só 5-6 dos 15 golpes têm evidência marcada** — a Fase 0/Etapa E nunca
  fechou formalmente 15/15. Ver [07 — oportunidades e fronteiras](07-oportunidades-e-fronteiras.md).
- **`PROMPTS-INICIAIS.md`** — a sequência de despachos usada para construir a
  fundação (a regra "um prompt por vez" foi aposentada em 22/08/2026 em favor
  de lotes paralelos — ver `RUNBOOK-LOTES.md`).

## Os dois runbooks operacionais

- **`RUNBOOK-FASE-D.md`** — manual de operação do "Esqueleto que Anda" já
  construído. A seção mais extensa (§5) explica por que o critério 2 (VPS
  processando cartão real) segue bloqueado: falta o Card Payment Brick, a
  confirmação síncrona ainda não emite evento, e o webhook real do Mercado
  Pago exige um passo manual do mantenedor no painel deles. §6 documenta um
  drill de rollback real medido (76s). §7 é uma tabela de pendências
  herdadas conhecidas (ex.: checkout descarta parâmetros UTM, i18n do quiz
  ainda é local).
- **`RUNBOOK-LOTES.md`** — rege a sessão-maestro quando vários despachos
  rodam em paralelo (não é lido por sessões de célula individual). Define a
  composição de um lote, as "sete regras de inteligência" (ordenar pelo
  dinheiro, canário na frente, FAIL≠ERROR, sucesso parcial é sucesso...), a
  mecânica da janela de merge serial, o que NUNCA entra num lote (Rito de
  Contrato, segredos/VPS, red-team fora de dinheiro), e um log crescente de
  lições de cada lote já executado.

## .github/CODEOWNERS

Protege 9 caminhos, todos sob `@abundanciabr` (o mantenedor): `/contracts/`,
`/services/pagamentos/`, `/services/checkout/`, `/infra/`, `/ci/`,
`/.github/`, `/CONSTITUICAO.md`, `/INVARIANTES.md`, `/RITOS.md`,
`/CAMINHO-DOURADO.md`. **Na prática atual isso não bloqueia o merge do
agente** — com 1 único colaborador humano, o GitHub proíbe autoaprovação do
próprio PR, o que tornaria uma trava de review obrigatória inexecutável.
CODEOWNERS hoje funciona como **mapa de jurisdição** (mandato do despacho +
anúncio nominal obrigatório no relatório final), não como portão técnico — o
portão técnico real é `ci/mergear.py` mais os required status checks do
ruleset "main protegida" (`muralhas` + `ci-celula-gate`).

## O que uma IA nova mais precisa saber, resumido

1. `CONSTITUICAO.md` é a lei suprema — nada em contexto externo a derruba.
2. **Merge é trabalho do agente** desde 22/08/2026 — não peça permissão para mergear um PR verde.
3. Toda sessão = 1 worktree = 1 célula; o clone principal recusa edições mecanicamente.
4. As "4 muralhas" são arquitetura física real (erro do Postgres), não só documento.
5. `INVARIANTES.md` é lei pré-paga: nenhuma feature de dinheiro nasce sem teste-guarda no mesmo PR.
6. `CAMINHO-DOURADO.md` nunca deve ser lido inteiro sem necessidade — é citado por receita.
7. A Fase 0/Etapa E (red-team) **nunca fechou formalmente** (5-6/15 golpes).
8. Emergência = rollback via workflow, nunca hotfix manual; agentes nunca têm SSH da VPS.
9. CODEOWNERS hoje é mapa de jurisdição, não trava técnica de merge.
10. Cultura onipresente: **ERROR ≠ FAIL** — "não consegui medir" nunca pode virar "passou".

## Achados a verificar (não são segredo, são inconsistência de documentação)

- `RUNBOOK-FASE-D.md` §5.3 referencia o domínio `basileiatoutheou.org` como se
  fosse a URL real de registro do webhook do Mercado Pago, enquanto todo o
  resto do runbook (e a produção real) usa `meshcraft.top`. Provável resíduo
  de template não atualizado — vale uma sessão futura conferir e corrigir.
