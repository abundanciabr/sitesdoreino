// =============================================================================
// painel-10x-dados.js — O ESTADO do Painel 10X (cards, ondas, textos de despacho).
//
// Por que este arquivo existe (card C2 do PLANO-10X, Alavanca 2 — contexto):
// enquanto dados e renderizador moravam no mesmo HTML, qualquer atualização de
// um card obrigava a ler o arquivo inteiro. Separados, a edição típica toca só
// este arquivo, e o renderizador (painel-10x.html) fica estável.
//
// REGRAS DE EDIÇÃO (não são decoração — já quebraram o painel antes):
//  1. Carregado por <script src="..."> a partir de file://. NÃO vire .json com
//     fetch: o Chrome bloqueia fetch em file:// e o painel abre em branco.
//  2. Crase (`) dentro de template literal quebra tudo (ARMADILHAS §7.2). Se
//     precisar de crase no texto de um card, escreve \` ou use aspas simples.
//  3. Depois de editar, valide: node --check arquivos/painel-10x-dados.js
// =============================================================================

// Protocolo de evidência colado no rodapé de todo prompt de implementação.
const EVID = [
'',
'--- CONTRATO DE EVIDENCIA (nao negociavel) ---',
'Seu handoff SO vale com a saida CRUA colada, nunca com descricao dela:',
'1. make ci INTEIRO (ou os alvos manuais equivalentes), sem resumir, com a contagem de testes.',
'2. Para cada invariante/bug tocado: a saida do teste-guarda VERMELHO sem o fix e VERDE com o fix',
'   (protocolo git stash em ARMADILHAS.md 6.1 — nao crie branch descartavel).',
'3. git diff --name-only origin/main...HEAD (prova do escopo real) e a contagem de arquivos.',
'4. Se afirmar que algo "funciona", cole o comando que prova. "Deveria funcionar" nao e evidencia.',
'Se voce nao consegue colar a prova de um item do DoD, esse item NAO esta pronto: diga isso',
'em texto claro no handoff, nao o marque como feito. Um DoD honestamente incompleto e util;',
'um DoD falsamente completo custa a proxima sessao inteira mais a confianca do mantenedor.'
].join('\n');

const HOJE = [
  {id:'H0.1', titulo:'H11: o pipeline entrega o compose na VPS (DESPACHO-04)', area:'.github · agente', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #50 · plataforma NO AR',
   texto:
`[CONCLUÍDO EM 22/08/2026 — auditado pela janela raiz contra o GitHub e o ARMADILHAS]
PR #50 mergeado: deploy-infra.yml na main — e desde o PR #54 ele roda ATRÁS do mesmo
portão de deploy das células. O 1º run reprovou honesto DUAS vezes (1ª: H13 — a VPS
nunca tinha feito docker login no ghcr; 2ª: env sem DJANGO_SECRET_KEY) e ficou VERDE
na 3ª tentativa do MESMO commit: o "docker compose ps" impresso no run mostra os 16
serviços em running — 8 células healthy, os 4 *-consumer, o worker da mensageria,
traefik, postgres e redis. A PLATAFORMA SUBIU EM PRODUÇÃO PELA PRIMEIRA VEZ, com os
consumers do PR #45 no ar. H11 e H13 estão ✅ no ARMADILHAS (PR #52).
Run da prova: github.com/abundanciabr/sitesdoreino/actions/runs/32538231311
--- prompt original abaixo, só para referência histórica ---

SUBSTITUÍDO EM 21/08: este card era "copie o compose à mão". Decisão nova — em vez
do passo manual, despache docs/decisoes/DESPACHO-04-deploy-infra.md: um workflow
novo (deploy-infra.yml) que sincroniza infra/docker-compose.yml e infra/traefik/
para a VPS a cada merge, fail-closed, com backup e verificação — usando a chave que
o pipeline JÁ tem (a mesma do deploy de células). Agentes continuam sem chave (Lei 5);
o canal deles para a VPS é o pipeline, auditável e reversível.

O truque que elimina o passo manual: o próprio arquivo do workflow está nos paths de
gatilho — O MERGE DO PR JÁ DISPARA A PRIMEIRA SINCRONIZAÇÃO, que entrega os
consumers do PR #45 à produção.

O QUE FAZER: abra docs/decisoes/DESPACHO-04-deploy-infra.md, copie o prompt de lá
para um agente (worktree wt-infra-sync). Depois do SEU merge, abra o run do workflow
e confira o "docker compose ps" impresso no log: os serviços *-consumer e o worker
da mensageria devem estar "running". Essa saída é a evidência do H0.1 + H11 juntos.

NUNCA sincronizado: infra/env/ (segredos, INV-P8) — o despacho proíbe por escrito.`},
  {id:'H0.2', titulo:'✅ FEITO 22/08 (PR #59) — regra serial aposentada; lotes liberados', area:'raiz · decisão dada', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #59',
   texto:
`[EXECUTADO em 22/08/2026 — decisão "aposenta" dada em sessão; PR #59 mergeado
pelo agente pelo fluxo novo. Card mantido como registro histórico do despacho.]

DECISÃO SUA + edição pequena. A regra "serial, não paralelo" venceu por escrito
(PROMPTS-INICIAIS.md:7 diz "até o esqueleto andar" — e ele andou no PR #31), e o
painel da Fase D a atribui erradamente ao RITOS §1, onde a palavra "serial" nem
existe. O paralelo já rodou 2x sem colisão de código (7 células/51min; 6 PRs numa
noite). Codificar isso é a Alavanca 1 (5x de throughput já demonstrado).

Despacho para um agente (worktree wt-docs-paralelo, área: raiz/docs):

MISSÃO: aposentar a doutrina serial e codificar o padrão de lote paralelo.
1. Em arquivos versionados (NÃO no painel HTML, que é gitignored): onde houver
   afirmação de operação serial, corrigir para o padrão atual — 1 LOTE = N células
   DISTINTAS desenvolvidas em paralelo, 1 janela de merge, merge serial dentro da
   janela (make mergear um a um). A cerca (1 PR = 1 célula) é a proteção e não muda.
2. Manter serial APENAS onde há dependência real: Rito de Contrato (provedor antes
   dos consumidores) e o e2e de fechamento. Escrever isso explicitamente.
3. Corrigir a atribuição falsa (a frase não é do RITOS §1).
ALVOS: docs de raiz que afirmam serialidade. Não toque em services/**.
DoD: git grep -in "serial" mostra só as ocorrências corrigidas/contextualizadas.
Cole o git grep antes e depois.` + EVID},

  {id:'H0.3', titulo:'✅ FEITO 22/08 (PR #57) — docs reconciliados com o portão (H3, PROJETO, INVARIANTES)', area:'docs/raiz · agente', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #57',
   texto:
`# DESPACHO — docs: registrar no Git o que o portão de deploy mudou no mundo
ÁREA: docs/raiz (nenhuma célula) · WORKTREE: wt-docs-portao-reconciliacao

ANTES: leia ARMADILHAS.md §1 (H3, H11, H13), docs/decisoes/PROJETO-PORTAO-DEPLOY.md,
INVARIANTES.md ([INV-CI01] e a Escada da Imposição — se a Escada morar em RITOS §2,
é lá), e SOMENTE-LEITURA .github/workflows/deploy-celula.yml + deploy-infra.yml
(a verdade que você vai registrar). Declaração (RITOS §1).

CONTEXTO: o portão de deploy EXISTE e foi provado ao vivo em 22/08 (PR #54; prova:
PR #55 mergeado vermelho de propósito ⇒ run 32567765127 com portao-de-deploy=failure
e deploy=skipped; revert PR #56 ⇒ run 32567900961 verde). Mas os documentos canônicos
não sabem: a linha H3 do ARMADILHAS ainda diz "Enquanto A não existir…" (a saída A
FOI construída), o PROJETO-PORTAO-DEPLOY.md não diz que foi executado, e não há
registro do estado novo — o deploy é gateado (DEPLOY PROTECTED), o MERGE continua
desprotegido. A sessão que construiu o portão prometeu essa reconciliação no handoff
e ela não chegou ao Git. Este despacho a entrega. É SÓ REGISTRO — zero código.

MISSÃO:
1. ARMADILHAS §1/H3: manter o estado (a proteção de MERGE segue impossível — nada
   mudou nisso), mas atualizar o texto: a saída (A) foi construída e provada
   (PR #54, prova #55/#56, com os run ids); o que resta aberto no H3 é só o merge.
2. PROJETO-PORTAO-DEPLOY.md: bloco curto no TOPO — "EXECUTADO E PROVADO em
   22/08/2026 (PR #54)" — com os run ids da prova Nível B e as reconciliações
   conscientes da implementação: (a) sonda F5 atendida pelos healthchecks do compose
   + docker compose up -d --wait, sem sonda extra; (b) portão estendido ao
   deploy-infra (pedido do handoff do DESPACHO-04); (c) prova de "imagem intocada"
   dada por deploy=skipped, porque a API de packages responde 403 ao token atual;
   (d) recreate condicional do traefik no deploy-infra (bind mount prende inode).
   NÃO reescreva a especificação — só o cabeçalho de estado.
3. INVARIANTES.md (ou RITOS, onde a Escada morar): registrar o degrau DEPLOY
   PROTECTED com o limite honesto — remover o portão do YAML é DETECTADO por teste
   (test_workflow_de_deploy_exige_o_portao roda no muralhas e no alarme-main),
   não impedido.
4. Versionar docs/decisoes/DESPACHO-04-deploy-infra.md com uma nota "EXECUTADO
   (PR #50)" no topo — os despachos 01–03 estão no Git, o 04 ficou só na máquina
   do mantenedor. A janela raiz cola o conteúdo dele neste chat quando você pedir.

ALVOS: ARMADILHAS.md (linha H3), docs/decisoes/PROJETO-PORTAO-DEPLOY.md (topo),
INVARIANTES.md ou RITOS.md, docs/decisoes/DESPACHO-04-deploy-infra.md (novo).
FORA DE ESCOPO: services/**, ci/, .github/ (nem uma vírgula); painéis (janela raiz).
DoD: git grep "Enquanto A não existir" não devolve nada; o topo do PROJETO diz
EXECUTADO com os dois run ids; o degrau novo aparece onde a Escada mora.
python ci/ci.py --apenas muralhas VERDE. ORÇAMENTO: ≤ 5 arquivos.` + EVID},
];

const ONDA1 = [
  {id:'A1', titulo:'checkout: relay do outbox (pedido.criado → Redis)', area:'checkout', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #67 · em produção',
   texto:
`# DESPACHO — checkout: relay do outbox (pedido.criado)
CÉLULA: checkout · WORKTREE: wt-checkout-relay · RECEITAS: R3, R8

ANTES: leia AGENTS.checkout.md, CAMINHO-DOURADO R3 (outbox+relay) e R8 (Huey),
services/checkout/LICOES.md, e services/pagamentos/pagamentos/core/models.py (é o
relay que JÁ funciona — copie o padrão dele, não invente outro). Declaração de
abertura (RITOS §1).

CONTEXTO: apps/pedidos/emitir.py só faz OutboxEvent.objects.create(...) — o evento
pedido.criado nasce no banco e NINGUÉM publica. A célula leads consome
eventos.pedido.criado de verdade (leads/apps/core/.../consume_eventos.py) e monta a
timeline — hoje quem abandona o carrinho é invisível, porque o evento nunca sai.

MISSÃO: instanciar o relay do outbox no checkout (config/huey.py + tasks.py +
relay chamado via transaction.on_commit logo após a gravação), publicando
pedido.criado no stream eventos.pedido.criado. Idempotente por event_id, mesmo
formato de envelope das outras células.

ALVOS: services/checkout/config/huey.py, .../tasks.py (ou onde a célula alojar),
apps/pedidos/emitir.py (chamar o relay), requirements.txt (huey/redis se faltarem),
services/checkout/tests/**, services/checkout/LICOES.md.
SOMENTE-LEITURA: contracts/eventos/pedido.criado.v1.json.
FORA DE ESCOPO: qualquer outra célula; o relay do quiz (é o card A2); as páginas
de produção (card A5). NÃO toque em arquivos/painel-*.html.

DoD:
- Teste vermelho→verde: sem o relay, publicar não acontece; com o relay,
  eventos.pedido.criado recebe o envelope na MESMA transação (INV-P6).
- transaction.on_commit NÃO dispara em teste django_db padrão (ARMADILHAS §6.5):
  use @pytest.mark.django_db(transaction=True) no teste específico.
- make ci + contrato-check VERDE.
ORÇAMENTO: ≤ 10 arquivos. Se estourar, pare e avise — NÃO funda arquivos para caber
(foi assim que este relay se perdeu na primeira vez: pagamentos/LICOES.md:262).` + EVID},

  {id:'A2', titulo:'quiz: relay do outbox (quiz.completado → Redis)', area:'quiz', merge:'auto', dep:'', done:'✅ 22/08 — PR #64 · em produção',
   texto:
`# DESPACHO — quiz: relay do outbox (quiz.completado)
CÉLULA: quiz · WORKTREE: wt-quiz-relay · RECEITAS: R3, R8

ANTES: leia AGENTS.quiz.md, CAMINHO-DOURADO R3/R8, services/quiz/LICOES.md, e o relay
que funciona em services/pagamentos/pagamentos/core/models.py. Declaração (RITOS §1).

CONTEXTO: quiz/apps/quiz/views.py grava quiz.completado na outbox, mas o quiz não
tem config/huey.py nem relay — o evento fica parado. leads consome
eventos.quiz.completado de verdade: hoje toda captura de lead via quiz está morta.

MISSÃO: mesma do card A1, para o quiz — relay via transaction.on_commit publicando
quiz.completado no stream eventos.quiz.completado, idempotente por event_id.

ALVOS: services/quiz/config/huey.py, .../tasks.py, o ponto de emissão em
apps/quiz/**, requirements.txt se faltar, services/quiz/tests/**, quiz/LICOES.md.
SOMENTE-LEITURA: contracts/eventos/quiz.completado.v1.json.
FORA DE ESCOPO: outras células; relay do checkout (card A1). NÃO toque nos painéis.

DoD: teste vermelho→verde de publicação transacional; on_commit com
django_db(transaction=True) (ARMADILHAS §6.5); make ci VERDE (quiz não tem contrato
REST — contrato-check pula, é esperado).
ORÇAMENTO: ≤ 10 arquivos. Estourou? Pare e avise.` + EVID},

  {id:'A3', titulo:'pagamentos: endurecer o webhook (data.id, ts, consulta ao MP)', area:'pagamentos', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #66 · em produção',
   texto:
`# DESPACHO — pagamentos: amarrar o webhook ao dado assinado
CÉLULA: pagamentos · WORKTREE: wt-pagamentos-webhook · RECEITAS: R5

ANTES: leia AGENTS.pagamentos.md, INVARIANTES INV-P3/INV-P10, services/pagamentos/
LICOES.md (seção webhooks, que documenta a decisão atual de confiar em data.status),
e core/webhook_signature.py + methods/pix/webhook.py + methods/card/webhook.py.
Declaração (RITOS §1).

CONTEXTO (3 furos medidos, todos no caminho do webhook):
1. A assinatura valida request.GET["data.id"] (query), mas o handler lê id e status
   do CORPO (webhook.py:34-35), que NÃO é coberto pela assinatura. Uma assinatura
   válida com status forjado no corpo aprovaria o pedido.
2. O data.id assinado (query) nunca é comparado com o data.id do corpo — uma
   assinatura legítima do pagamento X aprova o pagamento Y.
3. ts nunca é verificado quanto a frescor — um par assinado capturado uma vez vale
   para sempre.
Além disso, o webhook REAL do MP na VPS (critério 2 do ESQUELETO) NÃO manda
data.status — só data.id. Sem consultar o MP, _EVENTO_POR_STATUS.get("") devolve
None e o handler responde 200 "ignorado", falhando em silêncio.

MISSÃO:
- Comparar data.id da query (assinado) com o do corpo; divergência ⇒ 403.
- Janela de frescor no ts (ex.: 5 min); fora da janela ⇒ 403.
- Buscar o pagamento no MP por id (GET /v1/payments/{id}) e derivar o status DALI,
  não do corpo. É o que torna o webhook real da VPS funcional.
INVARIANTES TOCADOS: INV-P10 (assinatura antes de efeito), INV-P3 (idempotência).

ALVOS: pagamentos/core/webhook_signature.py, .../methods/pix/webhook.py,
.../methods/card/webhook.py, .../providers/mercadopago/client.py (o GET novo),
.../core/gateway.py (traduzir a consulta), tests/**, LICOES.md.
SOMENTE-LEITURA: contracts/pagamentos.openapi.yaml, contracts/eventos/*.json.
FORA DE ESCOPO: outras células; o fail-closed da CRIAÇÃO de intent (já feito, PR #44).
NÃO toque nos painéis.

DoD (todos com vermelho→verde):
- webhook assinado com data.id do corpo != da query ⇒ 403 + banco intacto + outbox vazia.
- ts fora da janela ⇒ 403.
- status derivado da consulta ao MP, não do corpo (mock respx do GET, cobrindo
  approved/rejected/pending).
- mesmo webhook 3x ⇒ 1 transição + 1 outbox (INV-P3 continua verde).
- make ci + cross-smoke + contrato-check VERDE.
ORÇAMENTO: ≤ 15 arquivos. Se o GET novo exigir mudar o contrato, PARE e reporte
(Rito de Contrato §3). Estourou o orçamento? Divida e avise, não funda testes.` + EVID},

  {id:'A5', titulo:'checkout: ligar a página para produção (4 quebras)', area:'checkout + infra', merge:'agente (portão)', dep:'A1', done:'✅ 22/08 — PRs #62/#65/#68 · em produção',
   texto:
`# DESPACHO — checkout: a compra precisa funcionar na VPS
WORKTREE: wt-checkout-producao · RECEITAS: CONV-SITE, R6

ANTES: leia services/checkout/LICOES.md, infra/traefik/dynamic/plataforma.yml,
infra/env/checkout.env.exemplo, services/checkout/config/urls.py e
services/checkout/static/checkout/api.js. Declaração (RITOS §1).

CONTEXTO — auditoria de 21/08 achou 4 quebras INDEPENDENTES que, juntas, fazem
NINGUÉM conseguir comprar em produção (mesmo com backend perfeito). Todas falham
para o lado seguro, mas bloqueiam o critério 2 da Fase D:
1. Traefik: não há rota /api/checkout — o PathPrefix é só "/checkout", então
   /api/checkout/... cai no catch-all do funil (404). (plataforma.yml)
2. Nenhum token de ENTRADA: checkout.env.exemplo não define TOKENS_ACEITOS_* —
   TOKENS_ACEITOS = set() ⇒ toda chamada à API responde 401. E views.py lê
   TOKENS_ACEITOS_PAGINAS, também ausente.
3. Estáticos: com DEBUG=0 e sem whitenoise (ausente do requirements), os .js não
   são servidos — a página fica em branco.
4. window.API_BASE não é definido em template nenhum (grep vazio) — api.js chamaria
   fetch("undefined/...").

CUIDADO DE ESCOPO: isto cruza services/checkout E infra/ (traefik + env). A cerca é
1 PR = 1 célula, e infra/ pode contar como área própria. Conte os arquivos e as
áreas ANTES de codar. Se não couber num PR limpo, DIVIDA: (PR-a) o lado da célula
checkout — servir estáticos (whitenoise ou rota), definir window.API_BASE no
template, base da API correta; (PR-b) o lado infra — rota /api/checkout no Traefik e
TOKENS_ACEITOS_* nos .env.exemplo. Diga a divisão na primeira resposta.

DoD — a prova NÃO é "deveria funcionar", é reprodução:
- Suba a célula em modo prod-like (DEBUG=0) localmente e mostre, com curl e/ou
  screenshot de log, a página carregando os .js (200, não 404) e uma chamada à API
  autenticada retornando 200 (não 401).
- Mostre window.API_BASE renderizado no HTML com o valor certo.
- Explique como o Traefik roteia /api/checkout depois do fix (a regra nova).
- make ci + contrato-check VERDE (a forma exportada da API não muda).
ORÇAMENTO: declare por PR. NÃO use label para inchar.` + EVID},

  {id:'AUD1', titulo:'AUDITORIA da Onda 1 — sessão independente', area:'auditoria', merge:'—', dep:'A1,A2,A3,A5', audit:true, done:true,
   texto:
`# AUDITORIA — Onda 1 (relays, webhook, checkout-produção)
Você é um AUDITOR. NÃO implementou nada desta onda e NÃO vai corrigir nada — só
verificar contra o repo real e reportar. Trabalhe em português. Comandos read-only,
git e gh são livres; não rode nada que mude estado.

CONTEXTO: os cards A1 (relay checkout), A2 (relay quiz), A3 (webhook pagamentos) e
A5 (checkout-produção) deviam estar mergeados. Confirme CADA afirmação de DoD deles
contra o código em origin/main — não contra o handoff dos agentes.

git fetch origin && git checkout origin/main (ou leia via git show origin/main:...).

VERIFIQUE, item a item, com evidência (caminho:linha ou saída de comando):
A1: existe config/huey.py + tasks.py no checkout? emitir.py chama o relay via
    on_commit? há teste com django_db(transaction=True) que prova a publicação?
    Rode: python -m pytest services/checkout/tests -q. Cole a saída.
A2: idem para quiz e eventos.quiz.completado.
A3: webhook_signature.py compara data.id query vs corpo? há janela de ts? o status
    vem de uma consulta ao MP (GET /v1/payments) e não do corpo? Existe teste
    vermelho→verde para cada um dos 3? Rode os testes de pagamentos e cole.
A5: a rota /api/checkout existe no plataforma.yml? há TOKENS_ACEITOS_* no
    checkout.env.exemplo? os estáticos são serviços com DEBUG=0? window.API_BASE é
    definido em algum template? (grep -rn "API_BASE" services/checkout/templates)

Para CADA item: PASS (com a evidência) / FAIL (com o que falta) / PARCIAL.
Desconfie de teste que passa mas nunca poderia falhar: para 2 invariantes, verifique
que o assert realmente morde (o guarda testa o comportamento, não uma tautologia).

RELATÓRIO: tabela item×veredito×evidência. No fim, uma linha: a Onda 1 pode ser
considerada FECHADA? Sim só se todos PASS. Liste o que impede, se não.`},
];

const ONDA2 = [
  {id:'D1', titulo:'reconciliação diária + alarme ("quem pagou e não recebeu")', area:'ci/ ou célula nova de operação', merge:'agente (portão)', dep:'',
   texto:
`# DESPACHO — reconciliação: o detector de divergência silenciosa
WORKTREE: wt-reconciliacao · RECEITAS: (referência R4)

ANTES: leia INVARIANTES.md (INV-P5, INV-P6), o relatório do caminho do dinheiro em
docs/decisoes/ se disponível, e como alarme-main.yml abre issue automática (é o
padrão de alerta a reusar). Declaração (RITOS §1).

CONTEXTO: hoje TODO caminho de falha do dinheiro é descoberto pela reclamação do
cliente — não há reconciliação, alarme ou consulta. Há ao menos 4 caminhos
independentes para "pago sem matrícula" (PEL do Redis, relay ausente, corrida do
place_order, webhook). Este card é o que transforma todos eles de silenciosos em
avisados. É o item de maior retorno da Onda 2.

DESAFIO DE ARQUITETURA (decida e justifique no handoff): a reconciliação precisa
cruzar dados de células isoladas (Intent em pagamentos, Order em checkout, Matricula
em alunos). Ela NÃO pode ler o banco de outra célula (Lei 3). As opções: (a) cada
célula expõe um endpoint de leitura de reconciliação e um verificador central cruza
via API (R2); (b) a reconciliação roda por evento (compara o que passou pelos
streams). Proponha a que respeita as muralhas com menos peças novas — e lembre do
congelamento arquitetural: nada de célula nova sem necessidade real.

MISSÃO: um comando/rotina que responda e ALARME quando achar divergência:
- Intents approved sem transição/evento correspondente;
- OutboxEvent com published_at nulo há mais de N minutos (em qualquer célula);
- (se viável pela arquitetura escolhida) pagamento aprovado sem matrícula.
Agendar 1x/dia; divergência ⇒ abre issue (label reconciliacao), como o alarme-main.

DoD: teste que injeta uma divergência sintética e prova que o comando a DETECTA e
sinaliza; e um caso limpo que prova que ele NÃO alarma falso-positivo. make ci VERDE.
ORÇAMENTO: declare. Se exigir endpoints novos em várias células, isso é vários PRs —
diga o plano na primeira resposta, não funda tudo num só.` + EVID},

  {id:'A4a', titulo:'consumers: recuperação de mensagem presa (PEL do Redis)', area:'por célula: alunos', merge:'auto', dep:'', done:'✅ 22/08 — PRs #72/#73/#74/#75 (4 células)',
   texto:
`# DESPACHO — alunos: recuperar mensagem presa na PEL do Redis
CÉLULA: alunos · WORKTREE: wt-alunos-pel · RECEITAS: R4

(Este é o PRIMEIRO de uma série idêntica — o MESMO fix vale para leads, mensageria e
checkout, cada um em SEU PR próprio, porque 1 PR = 1 célula. Faça alunos primeiro;
os outros copiam este padrão. NÃO tente os quatro num PR só.)

ANTES: leia services/alunos/apps/eventos/management/commands/consume_eventos.py,
services/alunos/LICOES.md (menciona xautoclaim), ARMADILHAS §4.8/§4.12. Declaração.

CONTEXTO: o laço do consumer (while True + xreadgroup ">") lê SÓ mensagens novas e
NÃO tem try/except em volta do handler. Se o handler estoura (KeyError, deadlock), a
exceção mata o processo, o r.xack nunca roda, e a mensagem fica na Pending Entries
List do grupo — que NADA no código relê. xautoclaim/xpending não existem em lugar
nenhum do repo. Somado ao dedup atômico (já corrigido no #43), um evento preso é
perdido em silêncio.

MISSÃO:
- Envolver o processamento de cada mensagem em try/except: falha ⇒ logar, NÃO
  ackear, NÃO derrubar o processo (a próxima iteração segue).
- Na partida (e periodicamente), xautoclaim das mensagens pendentes há mais de N ms
  do próprio grupo, reprocessando-as pelo mesmo handler idempotente.
- Um limite de tentativas (dead-letter ou log de alerta) para veneno que nunca
  processa, para não girar em loop.
INVARIANTES: idempotência por event_id continua sendo o guarda (já existe).

ALVOS: alunos/apps/eventos/management/commands/consume_eventos.py, tests/**, LICOES.
DoD (vermelho→verde): um handler que estoura na 1ª entrega ⇒ a mensagem é reclamada
e processada na recuperação, SEM perder e SEM duplicar (o dedup segura). Um teste que
prova que o processo NÃO morre quando um handler levanta. make ci VERDE.
ORÇAMENTO: ≤ 6 arquivos.

AO TERMINAR: registre em ARMADILHAS (ou confirme que já está) que este mesmo fix
precisa ser replicado em leads, mensageria e checkout — cada um seu PR.` + EVID},

  {id:'B3', titulo:'ci: alarme-main roda a muralha repo-wide na main', area:'ci/', merge:'agente (portão)', dep:'', done:'✅ 25/08 — PR #171 · só a guarda de segredos, por medição',
   texto:
`# DESPACHO — ci: fechar dois buracos de portão medidos
ÁREA: ci/ e .github/ (não conta como célula na cerca) · WORKTREE: wt-ci-alarme

ANTES: leia ARMADILHAS §5 inteiro, .github/workflows/alarme-main.yml,
ci/guarda-de-segredos.sh, e-INV-CI01 em INVARIANTES.md. Declaração (RITOS §1).

CONTEXTO — dois furos medidos:
1. alarme-main.yml roda só "--apenas testador". As muralhas (cerca, orçamento,
   guarda de segredos) NUNCA rodam na main — só em PR. Ou seja, a guarda de segredos
   jamais varreu a main.
2. ci/guarda-de-segredos.sh:18 — o padrão "git grep ... > saida || status=$?": se a
   REDIREÇÃO falhar (disco cheio/somente-leitura), bash retorna 1 sem executar o git,
   e o script lê isso como "nenhuma ocorrência" — passa sem ter varrido nada.
   (Também: e2e/esqueleto.sh:100 usa curl sem -f e sai 0 em HTTP 500 — mesma família,
   corrija junto se estiver no escopo de ci/.)

MISSÃO:
- alarme-main.yml passa a rodar "--apenas muralhas,testador" (a guarda de segredos
  existe na main).
- guarda-de-segredos.sh: separar "não consegui procurar" de "procurei e não achei"
  (o modelo fail-closed já usado em cerca-de-celula.sh; git grep retorna 0=achou,
  1=não achou, >1=ERRO ⇒ exit 2).
DoD (vermelho→verde): commitar APP_USR-fake numa branch de teste da main ⇒ o alarme
abre issue (prove com o run); e um teste que prova que redireção falha vira ERROR,
não "OK". make ci / testador VERDE.
ORÇAMENTO: ≤ 5 arquivos.` + EVID},

  {id:'D2', titulo:'checkout: fechar a corrida do place_order (double-click)', area:'checkout', merge:'agente (portão)', dep:'',
   texto:
`# DESPACHO — checkout: double-click não pode gerar 500 nem pedido órfão
CÉLULA: checkout · WORKTREE: wt-checkout-corrida · RECEITAS: R1

ANTES: leia services/checkout/apps/core/api.py (place_order), INVARIANTES INV-P1/P4,
checkout/LICOES.md. Declaração (RITOS §1).

CONTEXTO: em api.py, a checagem de idempotência (filter(session).first()) e a criação
do Order estão em transações separadas, com uma chamada HTTP de até 10s no meio
(criar_intent). Duas requisições concorrentes (double-click, retry) passam ambas pela
checagem. A intent é uma só (idempotency_key = session.id — INV-P4 segura a cobrança
dupla), MAS: o perdedor do INSERT recebe IntegrityError não tratado ⇒ HTTP 500; e o
order_id gravado na intent pode não ser o order_id do Order que sobreviveu ⇒ webhook
aprova um order_id fantasma, pedido preso em aguardando_pagamento para sempre.

MISSÃO: criar o Order (status provisório) ANTES da chamada externa, dentro da
transação, de forma que o order_id da intent SEMPRE bata com o Order persistido; e
tratar IntegrityError da corrida devolvendo o 409 idempotente (não 500).
INVARIANTES: INV-P1 (snapshot create-only) continua intocado; INV-P4 idem.

ALVOS: checkout/apps/core/api.py, apps/pedidos/** se preciso, tests/**, LICOES.
DoD (vermelho→verde): duas requisições concorrentes (threads/barrier) ⇒ 1 Order,
1 intent, e o segundo recebe 409 (não 500); order_id da intent == Order.id sempre.
make ci + contrato-check VERDE.
ORÇAMENTO: ≤ 10 arquivos.` + EVID},

  {id:'AUD2', titulo:'AUDITORIA da Onda 2 — sessão independente', area:'auditoria', merge:'—', dep:'D1,A4a,B3,D2', audit:true,
   texto:
`# AUDITORIA — Onda 2 (reconciliação, PEL, alarme-main, place_order)
Você é AUDITOR independente. Não corrige nada; verifica contra origin/main e reporta.

Confirme cada DoD com evidência real (não handoff):
D1: existe a rotina de reconciliação? Ela respeita a Lei 3 (não lê banco alheio —
    confirme que cruza via API/evento, não via conexão cruzada)? Há teste que injeta
    divergência e prova detecção E um que prova ausência de falso-positivo? Rode-os.
A4a: o consumer de alunos tem try/except que impede o processo de morrer? Há
    xautoclaim/xpending recuperando a PEL? Teste que prova reprocessamento sem perda
    e sem duplicação? (grep -rn "xautoclaim\\|xpending" services/alunos)
B3: alarme-main.yml roda muralhas agora (não só testador)? guarda-de-segredos separa
    ERRO de "não achei"? Prova do run que abre issue com APP_USR-fake?
D2: place_order cria o Order antes da chamada externa? IntegrityError vira 409, não
    500? Teste concorrente com barrier provando 1 Order + order_id consistente?

Para cada: PASS/FAIL/PARCIAL com evidência. Cheque que os testes MORDEM (rode um
deles com o fix revertido via git stash, se conseguir, e confirme que fica vermelho).
RELATÓRIO: tabela + veredito de fechamento da Onda 2.`},
];

const ONDA3 = [
  {id:'B1', titulo:'ci: o portão de deploy (o required check que o GitHub não vende)', area:'ci/ + .github', merge:'agente (portão)', dep:'', done:'✅ 22/08 — PR #54 + prova viva #55/#56',
   texto:
`[CONCLUÍDO EM 22/08/2026 — adiantado da Onda 3, auditado pela janela raiz]
PR #54 mergeado: ci/portao_de_deploy.py + 25 testes adversariais + o job
portao-de-deploy rodando ANTES do build no deploy-celula.yml E TAMBÉM no
deploy-infra.yml (o handoff do DESPACHO-04 pedia exatamente isso). A sonda
pós-deploy virou "docker compose up -d --wait": container que não fica healthy
reprova o deploy (F5 fechado).
NÍVEL B EXECUTADO AO VIVO: o PR #55 mergeou um teste quebrado DE PROPÓSITO ⇒
run 32567765127: portao-de-deploy=FAILURE, deploy=SKIPPED — nenhuma imagem
publicada, porque o build mora no job que foi barrado. O PR #56 reverteu ⇒
run 32567900961: portao=success, deploy(quiz)=success. Vermelho→verde MEDIDO
em produção. De agora em diante, merge com check vermelho NÃO vira deploy.
--- prompt original abaixo, só para referência histórica ---

# DESPACHO — ci: portão de deploy fail-closed
ÁREA: ci/ + .github/ · WORKTREE: wt-ci-portao-deploy

ANTES: leia docs/decisoes/PROJETO-PORTAO-DEPLOY.md INTEIRO (é a especificação
completa — fatos medidos, decisões, contrato de comportamento, tabela de 14 estados,
vetores de burla e a prova exigida). Leia também INVARIANTES INV-CI01, ci/_nucleo.py,
ci/ci.py (padrão _blindar), .github/workflows/{deploy-celula,ci-celula,alarme-main}.yml.
Declaração (RITOS §1).

MISSÃO: implementar ci/portao_de_deploy.py + revisar deploy-celula.yml + a suíte
adversarial ci/tests/test_portao_de_deploy.py, exatamente conforme PROJETO-PORTAO-
DEPLOY.md. Inclui a sonda pós-deploy no workflow (o healthcheck já está no compose
desde #45; o workflow ainda declara sucesso sem olhar — F5 do projeto).

PONTOS QUE O PROJETO EXIGE E SÃO FÁCEIS DE ERRAR:
- Chavear por PATH de workflow, nunca por nome (há dois checks "detectar" no mesmo SHA).
- skipped/cancelled NÃO é verde; ci-celula skipped com services/** tocado ⇒ ERROR.
- Evidência das muralhas vem do head do PR de origem (muralhas só roda em PR).
- Polling com gh api (sem action de terceiro); timeout ⇒ ERROR; graça p/ run aparecer.
- Recusar event_name != push; len(celulas) > 1 ⇒ FAIL.
- _blindar: exceção interna ⇒ exit 2, nunca 1.

DoD — SEM ISTO NÃO ESTÁ PRONTO:
- Nível A: os 14 casos da tabela do PROJETO, cada um afirmando o exit code exato,
  com um gh falso no PATH (padrão do conftest de ci/tests). Cole a saída do pytest.
- test_workflow_de_deploy_exige_o_portao: lê o YAML e afirma a forma (needs, if, sem
  workflow_dispatch), roda no muralhas E no alarme-main.
- make ci / testador VERDE.
- O Nível B (ao vivo, mergear com CI vermelha e provar deploy pulado + imagem não
  republicada) é do MANTENEDOR — deixe no corpo do PR as 4 etapas prontas para ele.
ORÇAMENTO: ≤ 10 arquivos (é ci/, não conta na cerca de célula, mas conta no orçamento).` + EVID},

  {id:'B2', titulo:'ci: guarda-dos-guardas (o teste-guarda não pode sumir sem alarme)', area:'ci/', merge:'agente (portão)', dep:'', done:'✅ 25/08 — PR #173 · catraca com 37 na dívida',
   texto:
`# DESPACHO — ci: INVARIANTES.md como fonte executável
ÁREA: ci/ · WORKTREE: wt-ci-guarda-dos-guardas

ANTES: leia INVARIANTES.md (o formato "- Teste-Guarda: caminho — ..."), ARMADILHAS
§5, CONSTITUICAO Lei 1 (Escada da Imposição). Declaração (RITOS §1).

CONTEXTO — teatro medido: (a) o guarda do INV-P9 é @if [ -f .importlinter ] no
Makefile — apagar o arquivo deixa make ci VERDE, nada acusa; (b) 7 das 8 células não
têm mypy.ini nem .importlinter, mas o step do CI se chama "lint + import-linter +
type + testes"; (c) RITOS §2.3 diz "teste é intocável" — hoje é só prosa. Nada
verifica que um teste-guarda continua existindo e mordendo.

MISSÃO: um portão que faz o parse de INVARIANTES.md e afirma, para cada invariante:
- o(s) arquivo(s) citado(s) em "Teste-Guarda:" existe(m);
- arquivos .py de guarda contêm ao menos um "def test_";
- nenhum guarda tem @pytest.mark.skip/xfail ou corpo que é só pass/return;
- INVERSO: todo services/*/tests/test_inv_*.py em disco está declarado no documento
  (hoje há guardas em disco sem invariante numerado — liste-os).
Integrar ao runner (python ci/ci.py) e rodar no muralhas + alarme-main.

DoD (vermelho→verde): git mv de um test_inv_*.py para /tmp ⇒ o portão fica VERMELHO;
restaurado ⇒ verde. Enfraquecer um guarda (trocar o assert por pass) ⇒ vermelho.
Cole as duas provas. make ci / testador VERDE.
ORÇAMENTO: ≤ 8 arquivos.` + EVID},

  {id:'C1', titulo:'contexto: particionar ARMADILHAS.md (−86% de tokens + mata conflito de merge)', area:'raiz/docs', merge:'agente (portão)', dep:'', done:'✅ 23/08 — PR #100 · leitura −80%',
   texto:
`# DESPACHO — docs: ARMADILHAS.md de monólito para índice + entradas
ÁREA: raiz · WORKTREE: wt-docs-armadilhas

ANTES: leia ARMADILHAS.md inteiro, CLAUDE.md (a regra de manter ARMADILHAS),
docs/decisoes/PLANO-10X.md (Alavanca 2). Declaração (RITOS §1).

CONTEXTO: ARMADILHAS.md = 15.406 tokens = 48% da carga de contexto de todo despacho,
cresceu +131% em 3 dias, é append-only por lei. ~38% é inútil para um despacho de
célula (histórico RESOLVIDO, seções do humano). E é a fonte nº 1 de conflito de merge
em trabalho paralelo (duas sessões escrevem no mesmo hunk).

MISSÃO (preservar 100% do conteúdo — isto é REORGANIZAÇÃO, nada some):
- armadilhas/NNN-slug.md, uma entrada por armadilha (são ~48), preservando texto.
- armadilhas/INDICE.md GERADO, 1 linha por entrada, com a MENSAGEM DE ERRO CRUA como
  chave de busca (as entradas já começam pelo sintoma — use isso).
- docs/historico/RESOLVIDAS.md para as entradas ✅ RESOLVIDO.
- ARMADILHAS-OPERACAO.md para as seções do humano (§1 PRECISA DE VOCÊ, §5.8/5.9 como
  mergear, §7.1-7.4 painéis) — fora da dieta do agente.
- ARMADILHAS.md vira um ponteiro curto: "leia armadilhas/INDICE.md e abra só o que
  casa com sua tarefa". Atualizar CLAUDE.md e CAMINHO-DOURADO §0 para a nova regra.
- Um script que regenera o índice (para o crescimento não voltar a inchar).

CUIDADO: muitos documentos referenciam "ARMADILHAS §X.Y". Faça um mapa de-para e
atualize as referências (grep -rn "ARMADILHAS" no repo), OU mantenha âncoras
equivalentes. Não quebre os links internos — liste no handoff cada referência migrada.
DoD: nenhuma entrada perdida (conte antes/depois); todas as referências resolvem;
make ci VERDE (se algum portão lê ARMADILHAS, ajuste). Cole o antes/depois da contagem.
ORÇAMENTO: alto por natureza (é split de arquivo) — declare o número e explique.` + EVID},

  {id:'C2', titulo:'contexto: separar dados do renderizador dos painéis (−94% por edição)', area:'arquivos/ (fora do Git)', merge:'—', dep:'', done:'✅ 23/08 — janela raiz · PR #102 registra',
   texto:
`# DESPACHO — painéis: dados em .js separado do HTML
ÁREA: arquivos/ (gitignored — este trabalho é da janela raiz, não vai a PR)
WORKTREE: nenhum (arquivos/ não existe em worktree). Rode na janela raiz.

CONTEXTO: painel-fundacao.html = ~34k tokens, e CLAUDE.md manda editá-lo a cada
tarefa. Como a ferramenta de edição exige ler antes, cada atualização custa ~34k
tokens — mais que toda a governança de um despacho. Separar o estado num .js reduz a
edição típica para ~2k.

MISSÃO: extrair o estado (o conteúdo que muda — itens, incidentes, checklist) para
arquivos/painel-dados.js como const DADOS = {...}, e o HTML passa a carregá-lo via
tag script com src="painel-dados.js" + renderizar. ATENÇÃO: tem que ser .js com
src, NÃO .json via fetch — o painel abre por file:// e o Chrome bloqueia fetch nesse
esquema. Validar o JS com node depois (ARMADILHAS §7.2 — crase em template literal
quebra o painel).
DoD: o painel renderiza idêntico ao atual (compare visualmente); editar um item passa
a tocar só painel-dados.js. Node valida o JS de ambos os arquivos.
NÃO É PR (arquivos/ é gitignored). É melhoria de processo da janela raiz.`},

  {id:'C3', titulo:'contexto: make sessao (os 6 primeiros minutos viram 1 comando)', area:'raiz/ci', merge:'agente (portão)', dep:'', done:'✅ 25/08 — PR #174 · execução real colada',
   texto:
`# DESPACHO — ci: bootstrap de sessão de agente
ÁREA: raiz + ci/ · WORKTREE: wt-ci-make-sessao

ANTES: leia ARMADILHAS §2 (partida rápida) e §3 (todas as armadilhas de ambiente
Windows), ci/doctor.py, RITOS §1. Declaração (RITOS §1).

CONTEXTO: os "6 primeiros minutos" de toda sessão (worktree + venv fora do worktree +
docker do Postgres + env vars + baseline) são manuais e já causaram N rodadas de erro
(§3.3 python3, §3.6 /tmp, §3.8 venv, PATH, UTF-8). doctor.py diagnostica mas, por
design, não conserta. Não existe bootstrap.

MISSÃO: make sessao CELULA=x TAREFA=y (fachada de um script Python, como o resto do
ci/) que faça, idempotente: git fetch + worktree add + venv FORA do worktree +
pip install -r da célula + docker run -d do Postgres da célula em background + escrever
.env de sessão (PYTHONUTF8=1, DJANGO_SECRET_KEY de dev, DATABASE_URL, scratch com
caminho absoluto Windows) + rodar doctor + rodar make ci de baseline + imprimir a
Declaração de Abertura preenchida. Mantê-lo read-safe: doctor continua read-only;
o novo é um subcomando/alvo EXPLÍCITO, nunca o comportamento padrão.
DoD: numa máquina limpa (ou worktree novo), make sessao leva de zero a "make ci
verde" sem o agente consultar ARMADILHAS §2/§3. Cole a saída completa de uma execução.
ORÇAMENTO: ≤ 8 arquivos.` + EVID},

  {id:'B5', titulo:'ci: e2e em camadas (roda no CI sem credencial real)', area:'e2e/ + ci', merge:'agente (portão)', dep:'B1',
   texto:
`# DESPACHO — e2e: rodar no CI, em camadas, com MP mockado
ÁREA: e2e/ + .github/ · WORKTREE: wt-e2e-camadas

ANTES: leia ESQUELETO-QUE-ANDA.md, e2e/esqueleto.sh, e2e/docker-compose.e2e.yml,
ARMADILHAS §1 (H5, H8 credencial MP), §3.11-3.13. Declaração (RITOS §1).

CONTEXTO: make esqueleto NÃO roda em workflow nenhum (grep confirma) e exige
MP_ACCESS_TOKEN sandbox real (compose usa a forma :? do MP_ACCESS_TOKEN) — inexecutável em CI
por construção. ESQUELETO-QUE-ANDA.md afirma que ele "roda no CI a cada PR" — falso.

MISSÃO (estratégia em camadas, detalhada no relatório de CI se disponível):
- e2e/mp-fake: um fake server stateful de ~80 linhas (http.server puro, sem
  dependência) que responde /v1/payments de forma determinística, com cenários por
  header (401/429/500/timeout/corpo-sem-id), semeado de uma captura sandbox sanitizada.
- e2e/esqueleto.sh aceita MODO=mock (usa mp-fake, sem credencial, pula a exigência de
  .env.e2e) e MODO=sandbox (atual). client.py lê MP_API_BASE_URL do ambiente (no
  ponto de uso, não settings — ARMADILHAS §5.3), default api.mercadopago.com.
- Workflow: MODO=mock a cada PR que toca o caminho, e sempre no push da main.
- Promover o elo "pedido → pago" de "diagnóstico, não bloqueia" para BLOQUEANTE
  (hoje esqueleto.sh:252-266 deixa passar 8/8 com o pedido preso).
- Corrigir esqueleto.sh:100 (curl sem -f sai 0 em HTTP 500).
DoD: MODO=mock com cenário 401 ⇒ o elo de cobrança fica VERMELHO (reproduz o bug do
201 mecanicamente, agora fechado — prove que reprova). Workflow verde no caminho
feliz. Cole a saída de ambos.
ORÇAMENTO: declare. A camada sandbox real (1x/dia) depende do secret H8 — deixe
pronta mas documentada como "aguarda o mantenedor colar o secret".` + EVID},

  {id:'AUD3', titulo:'AUDITORIA da Onda 3 — sessão independente', area:'auditoria', merge:'—', dep:'B1,B2,C1,C3,B5', audit:true,
   texto:
`# AUDITORIA — Onda 3 (portão deploy, guarda-dos-guardas, contexto, e2e)
Você é AUDITOR independente. Não corrige; verifica contra origin/main e reporta.

B1: ci/portao_de_deploy.py existe? Rode ci/tests/test_portao_de_deploy.py e cole —
    confirme que cobre os 14 estados (conte os casos). O deploy-celula.yml tem o job
    portao com needs/if corretos e SEM workflow_dispatch? test_workflow_de_deploy_
    exige_o_portao existe e roda no muralhas+alarme? Há sonda pós-deploy no workflow?
B2: o guarda-dos-guardas existe e roda no runner? Faça a prova adversarial: git stash
    de um test_inv_*.py e rode o portão — fica vermelho? (reverta o stash depois)
C1: ARMADILHAS foi particionado sem perder entradas? Conte ### no histórico antigo vs
    entradas em armadilhas/. As referências "ARMADILHAS §X" pelo repo resolvem? (grep)
C3: make sessao existe e é idempotente? Leia o script; confirme que doctor continua
    read-only e que o bootstrap é subcomando explícito.
B5: e2e roda em workflow agora? MODO=mock existe? o elo pedido→pago é bloqueante?
    esqueleto.sh usa curl -f? mp-fake existe e é stateful?

Para cada: PASS/FAIL/PARCIAL com evidência. Rode os testes você mesmo.
RELATÓRIO: tabela + veredito de fechamento da Onda 3.`},
];

const PARALELO = [
  {id:'P1', titulo:'Validar demanda com link de pagamento (sem código, começa hoje)', area:'negócio · você', merge:'—', dep:'',
   texto:
`ESTE NÃO É UM DESPACHO DE AGENTE — é a Alavanca 5, e é a mais importante de todas
segundo as 4 consultorias. O maior risco do projeto não é técnico: é a fortaleza
perfeita que ninguém visita.

O que fazer (você, em paralelo a TODAS as ondas, desde já):
1. Crie um link de pagamento do Mercado Pago (Pix) para UM curso. Não precisa da
   plataforma — o primeiro real não precisa passar pelo nosso código.
2. Coloque numa página simples / anúncio / grupo. Meça se alguém compra.
3. Entrega manual (concierge): você mesmo manda o acesso ao comprador. Aceitável até
   ~20 clientes.
4. Antes da venda 1, os mínimos legais: CDC art. 49 (7 dias), Decreto 7.962/2013
   (identificação, preço, contrato, atendimento), LGPD. ECA Digital se o público
   inclui menores (cursos de Roblox). Defina PF/PJ e nota fiscal.

PERGUNTA QUE DECIDE O CAMINHO CRÍTICO (responda antes de investir mais na plataforma):
o conteúdo do curso existe e está pronto para entregar? Se não, o gargalo é o
conteúdo, não a arquitetura — e seu tempo rende mais lá. As ondas 1-3 rodam por
agentes sem você; a oferta e o conteúdo, não.`},
];

const WAVES = [
  {tag:'Hoje', cls:'hoje', nome:'Antes de tudo — H0.1, H0.2 e H0.3 FEITOS', desc:'H0.1 FEITO em 22/08: o pipeline entrega infra/ na VPS sozinho e a plataforma está NO AR (16 serviços). H0.2 FEITO em 22/08 (PR #59): regra serial aposentada — lotes paralelos liberados de direito. H0.3 FEITO em 22/08 (PR #57): o portão registrado no Git. De quebra, fora do plano: o MERGE passou ao agente (PR #58, Lei 4 reescrita) — a Onda 1 está destravada e pode ser despachada em lote.', cards:HOJE},
  {tag:'Onda 1', cls:'', nome:'O dinheiro chega ao cliente — ✅ FECHADA (auditada em 25/08)', desc:'AUD1 rodou em 25/08/2026 (sessão independente, só leitura) e o veredito é FECHADA: A1, A2, A3 e A5 todos PASS, conferidos contra origin/main e confirmados ao vivo em produção por HTTP. Os guardas foram provados por MUTAÇÃO — 5 quebras deliberadas em worktree descartável, 5 suítes vermelhas: nenhum teste passa por acidente. Sobraram 4 buracos de COBERTURA (não de comportamento), anotados no §9 do ARMADILHAS-OPERACAO.md — o mais caro é a rota /api/checkout do plataforma.yml, que existe e está no ar mas nenhum teste afirma que existe (foi esse buraco que produziu o incidente de 22/08).', cards:ONDA1},
  {tag:'Onda 2', cls:'', nome:'Rede de segurança — A4a feito, B3 pela metade, D1/D2 parados', desc:'A4a ✅ em 4 células (PRs #72–#75). B3 tem metade no Git (guarda-de-segredos fail-closed) e metade em aberto (alarme-main ainda roda só o testador). D1 e D2 estão ENCOSTADOS por decisão do mantenedor: são pagamento/checkout, e pagamento é por último.', cards:ONDA2},
  {tag:'Onda 3', cls:'', nome:'Confiança mecânica + custo de produção — é AQUI que a retomada mora', desc:'B1 ✅ feito. O resto desta onda é a fábrica: B2 (guarda-dos-guardas), C1 e C2 (corte de contexto — Alavanca 2) e C3 (make sessao). Nenhum deles toca pagamento, então nenhum esbarra na ordem de 22/08. B5 fica encostado com o pagamento.', cards:ONDA3},
  {tag:'Paralelo', cls:'audit', nome:'Alavanca 5 — o gargalo que não é de engenharia', desc:'Corre ao lado de todas as ondas, desde já. Nenhum agente faz isto por você.', cards:PARALELO},
];

