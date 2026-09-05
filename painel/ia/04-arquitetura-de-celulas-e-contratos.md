# painel/ia — 04. Arquitetura de Células e Contratos

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Resumo curado — a fonte
> de verdade é `celula-template/`, `constituicoes/`, `contracts/` e cada
> `services/<celula>/`. **Os números abaixo (quantas células têm contrato,
> quantos eventos existem) mudam conforme o projeto cresce — antes de
> confiar numa contagem para uma decisão importante, confira ao vivo com
> `git ls-files` em vez de aceitar este snapshot (27/08/2026).**

## O padrão (`celula-template/`)

Toda célula é um projeto **Django 5 + django-ninja** completo e autônomo,
gerado a partir de `celula-template/`. Árvore canônica: `manage.py`,
`requirements.txt`, `Makefile`, `Dockerfile`, `docker-compose.dev.yml` (sobe
só aquela célula + Postgres + Redis + mocks Prism das dependências — nunca a
plataforma inteira), `.env.dev` (gitignored), `config/{settings,urls,asgi}.py`
(o projeto Django sempre se chama `config`), `apps/` (domínio), `templates/`
e `static/` próprios (não existe `base.html` compartilhado entre células —
Lei 7 da Constituição), `tests/`, `pytest.ini`.

Convenções mecânicas que atravessam as 13 células:
- **Fail-hard de settings** — `SECRET_KEY`/`DATABASE_URL` ausentes ⇒
  `ImproperlyConfigured`, nunca fallback silencioso.
- **`SCRIPT_NAME`/`FORCE_SCRIPT_NAME`** lido do env — o urlconf nunca conhece
  o prefixo público; mover a célula de endereço é editar Traefik + env,
  nunca o código.
- **Dinheiro é sempre `amount_cents` inteiro** — float é proibido em toda a
  plataforma, models, APIs e eventos.
- **Migrations Expand-and-Contract** — nunca remover coluna/tabela em uso
  (Receita R7 do Caminho Dourado).
- **Outbox transacional** nas células emissoras (evento gravado na mesma
  transação do estado; relay Huey publica em Redis Streams) e **consumer
  idempotente** (grupo = nome da célula, dedup por `event_id`) nas ouvintes.
- **`make ci` = lint + type + test + contrato-check**, e `contrato-check`
  delega a decisão "esta célula tem contrato?" a `ci/manifesto-de-contratos.json`
  — nunca à presença do arquivo em disco.
- Módulo extra opcional (`celula-template/pagamentos-extra/`) para células
  que precisam do isolamento reforçado que hoje só `pagamentos` usa.

## As 13 células

| Célula | Domínio (por `apps/`) | LICOES.md | Constituição | Contrato OpenAPI |
|---|---|---|---|---|
| `admin` | `core` apenas — sem app de domínio próprio | ✓ | ✓ | — (só consome) |
| `alunos` | `bridge`, `core`, `eventos`, `matriculas` | ✓ | ✓ | ✓ |
| `catalogo` | `core`, `ofertas`, `produtos`, `sites` | ✓ | ✓ | ✓ |
| `checkout` | `core`, `pedidos` | ✓ | ✓ | ✓ |
| `forum` | `core`, `forum` | ✓ | ✓ | ✓ (3 operações; nasceu sem contrato por lei de gênese e virou `required` depois) |
| `funil` | `core`, `i18n` | ✓ | ✓ | — (páginas HTML, sem API JSON) |
| `identidade` | `core`, `identidade` | ✓ | ✓ | ✓ |
| `leads` | `core` apenas | ✓ | ✓ | ✓ |
| `mensageria` | `core`, `eventos` | ✓ | ✓ | — (esqueleto: só `/healthz`) |
| `notificacoes` | `core`, `eventos`, `notificacoes` | ✓ | ✓ | ✓ (4 operações; nasceu sem contrato por lei de gênese e virou `required` depois) |
| `pagamentos` | sem `apps/`: `core`, `methods/{pix,card}`, `providers/mercadopago`, `api` | ✓ | ✓ | ✓ |
| `quiz` | `core`, `quiz` | ✓ | ✓ | — (só páginas HTML) |
| `sugestoes` | `core`, `sugestoes` | ✓ | ✓ | ✓ (1 operação) |

**Todas as 13 células têm `LICOES.md` e constituição própria** — não é um
subconjunto (um levantamento anterior a este mapa presumia só 8; foi
corrigido nesta pesquisa). **9** células têm contrato OpenAPI `required`
(alunos, catalogo, checkout, forum, identidade, leads, notificacoes,
pagamentos, sugestoes); as outras **4** (admin, funil, mensageria, quiz) são
`not-applicable` por motivo escrito em `ci/manifesto-de-contratos.json`
— recontado em 30/08/2026, contra o manifesto e o disco. (A contagem
anterior deste mapa, "7 required + 5 not-applicable", somava 12 num projeto
de 13 células: sinal exato do padrão 2 da retrospectiva — número escrito à
mão em documento que nada recalcula. Recontar é sempre mais confiável que
confiar na linha acima.)

> **A 14ª célula, `gamificacao`, nasceu:** aprovada pelo mantenedor em
> 30/08/2026 e em `services/` desde o mesmo dia (PR #629). Ela tem seção
> própria logo abaixo — leia-a antes de propor qualquer mecânica de ponto,
> selo, ranking ou recompensa em qualquer outra célula.
>
> **A 15ª nasceu em 03/09/2026:** `encomendas`, a Fila do Primeiro Dólar,
> lei aprovada pelo mantenedor e esqueleto em `services/` no mesmo dia. Seção
> própria mais abaixo — leia-a antes de desenhar qualquer coisa que pareça
> marketplace, fila de trabalho remunerado, oferta a aluno ou portfólio de
> encomenda em outra célula.
>
> **A 16ª nasceu em 04/09/2026:** `metricas`, o livro de fatos da plataforma
> (degrau 7.1 do `PLANO-PAINEL-DE-GESTAO.md`). Seção própria mais abaixo. Ela
> é a única célula que não terá tela nenhuma, e a única cuja razão de existir
> é o TEMPO: as demais respondem "como está agora", e ela responde "como
> estava". Antes de propor que qualquer célula guarde histórico próprio de
> contagem, leia a seção dela.
>
> **A 17ª nasceu em 04/09/2026:** `cursos`, a sala de aula da Meshcraft (o
> conteúdo do curso, o progresso, o checkpoint e o laudo, e os agentes de IA
> que trabalham nela), lei aprovada pelo mantenedor e esqueleto em `services/`
> no mesmo dia. Seção própria mais abaixo — leia-a antes de desenhar aula,
> progresso de aluno, checkpoint, laudo ou agente de IA em outra célula.
>
> **A 18ª ainda NÃO nasceu:** `pages`, a casa das páginas do aluno (o portfólio
> é a primeira delas, e a vitrine pública em `/estudio/<apelido>` sai dela). A
> casa foi escolhida pelo mantenedor em 01/09/2026, renomeada por ele em
> 02/09/2026 e liberada para construção em 05/09/2026, mas `services/pages` não
> existe: ela nasce no degrau 01 da escada. Seção própria mais abaixo, escrita
> antes do código de propósito, para que ninguém desenhe portfólio de aluno ou
> vitrine de obra dentro de outra célula.

**Nota de método para medir tamanho de célula:** use `git ls-files
services/<celula> | wc -l`, nunca `find`. O caso `services/pagamentos`
chegou a mostrar 2073 arquivos num `find` cru — investigado a fundo, **96%
era `.mypy_cache/`** de uma sessão anterior (gitignored, não existe em clone
limpo). Contado certo (`git ls-files`), `pagamentos` tem 48 arquivos — menor
que `funil` (54) e pouco maior que `checkout` (44), apesar de ser o domínio
mais crítico. Por código real versionado, quem lidera é `sugestoes` (114
arquivos), de longe a célula mais extensa; a mais recente das 13 é `forum`
(51 arquivos). *Contagens de 30/08/2026 — recontar, não confiar.*

## A 14ª célula, ainda nascendo: `gamificacao`

**Estado:** lei aprovada pelo mantenedor em 30/08/2026 (Sessão A de
arquitetura + aprovação da lei; registros `20260830-061` e `20260830-064` no
livro); a pasta `services/gamificacao` **ainda não existe** no momento desta
escrita. Esta seção existe para que a próxima IA não desenhe ponto, selo,
ranking ou recompensa dentro de outra célula sem saber que já há dona para
isso. **Fonte de verdade:**
`docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` (a engenharia, com a escada de
entrega no §6) e `docs/consultorias/gamificacao/VEREDITO.md` (a
rastreabilidade de cada decisão, vinda de 6 consultorias + 5 auditorias).
O resumo abaixo é curado: divergiu, **o original vence**. E quem responde
"isto já foi feito?" continua sendo só o livro (`painel/registros/`) e a
fila (`fila/`) — este mapa não é placar.

**O que ela é.** Uma célula consumidora de fatos por evento e provedora de
leitura por HTTP. Ela transforma o que a plataforma **já afirma** (quiz
completado, sugestão criada/votada, e — com eventos novos — atividade no
fórum) em XP, níveis, Sequência semanal, Forja, missões, medalhas, Marcos de
carreira, Cristais e cosméticos. A hierarquia que decide todo conflito de
desenho é *realidade > criação > maestria > comunidade > XP* — e o objetivo
declarado da gamificação é **tornar-se progressivamente menos necessária**.

**Por que célula própria** (as alternativas foram consideradas e recusadas):
calcular XP dentro de `forum`/`sugestoes` violaria a Lei 3 e o §4.7 da lei do
fórum, e espalharia a economia por N células; um plugin/SaaS de gamificação
poria dado de **menores** em terceiro (Lei 2). Ela nasce com banco + role
próprios, `site_id` em toda entidade (Lei 9/INV-P11), **sem sessão própria**
(INV-P12), e falando com o resto só por contrato congelado + eventos
versionados. A previsão de uma célula assim já estava escrita em três
documentos anteriores — inclusive no `AGENTS.sugestoes.md`, com a frase
"nunca calcula XP".

**O que ela consome** (ninguém emite nada novo *para* ela em v1; ela só ouve
o que já existe):

- `quiz.completado.v1` — XP só na primeira aprovação de cada quiz.
- `sugestao.criada.v1`, `sugestao.voto-adicionado.v1` /
  `voto-removido.v1` (estorno espelhado do crédito),
  `sugestao.status-alterado.v2`.
- **Eventos de pagamento NÃO são consumidos** — a diretiva "pagamento por
  último" vale aqui também; o selo de Fundador entra por backfill.
- **A congelar em Rito de Contrato** (`RITOS.md` §3, uma sessão só):
  `forum.topico-criado.v1`, `forum.mensagem-criada.v1`,
  `forum.mensagem-removida.v1` (estorno) e `forum.resposta-aceita.v1` — este
  último é o evento mais valioso do desenho, porque é validação por gente de
  verdade. Mais um aditivo de assuntos em `notificacao.devida.v1`.
- **Tomada futura**: `aula.concluida.v1`, quando a trilha de aulas existir.
- **Não nasce evento de presença**, e **login vale 0 XP, sempre**: "dia
  ativo" deriva do próprio ledger, não de um evento de comparecimento.

**O que ela oferece** (leitura por HTTP; contrato
`contracts/gamificacao.openapi.yaml`, ainda por escrever): `getPublicProfiles`
— lote de até 50 ids, devolvendo `id → {nivel, titulo_slug, moldura_slug}`,
para o fórum decorar N autores com **uma** chamada; id desconhecido é
omitido, e nunca sai e-mail nem XP bruto. E `getMyStatus`, o painel do
próprio aluno. **Todo consumidor liga com cache de 5 min e falha ABERTA**: se
a gamificação cair, a página perde o selo, nunca quebra.

**Superfície pública:** `/conquistas` (host-bound em `meshcraft.top`), com
`/medalhas`, `/jornada`, `/loja` e `/estudio`. O prefixo tem 10 letras de
propósito — um prefixo de 2 letras como `xp` seria lido como código de
idioma pelo guarda de locale (armadilha 089). A vitrine pública do aluno é
**opt-in** e mora em `meshcraft.top/estudio/apelido`: só apelido, obras
aprovadas e marcos escolhidos, `noindex`.

**O que ela deliberadamente NÃO faz** — esta lista é desenho, não backlog:

| Não faz | Por quê |
|---|---|
| Não é fonte de verdade sobre **pessoas, matrículas ou conteúdo** | Espelha por evento; a verdade continua em `identidade`, `alunos` e `catalogo` (mesmo padrão do espelho `Pessoa` do fórum) |
| **Não calcula ponto dentro de outra célula** | Lei 3; e "pontos calculados dentro de outra célula" é **critério de morte** declarado desta célula |
| Não é reputação **do fórum** | O fórum só (a) afirma fatos por evento e (b) exibe um selo vindo por HTTP com falha aberta — o critério de morte do fórum segue intacto |
| Não é nota pedagógica | Avaliação de aprendizagem não é o mesmo objeto que XP |
| Não é economia comprável | **Nada por dinheiro real**: Cristais não se compram nem se transferem |
| Não dá vantagem por cosmético | **Cosmético é só estética** — nunca vantagem em XP, ranking ou visibilidade |
| Não tranca aula atrás de jogo | **Conteúdo educacional jamais** atrás de XP, nível ou Cristal |
| Não publica ranking global | Ranking global público/indexável é critério de morte |
| Não vira motor de regras genérico/DSL | Também critério de morte; e ajustar a economia **não pode** exigir PR de código |

Os três invariantes em **negrito** acima não são promessa de documento:
nascem como **testes no CI da própria célula** já no PR dos modelos, provados
por sabotagem (padrão 2 da retrospectiva — garantia sem mecanismo apodrece).

**Vocabulário já fechado pelo mantenedor — não reabrir:** as ligas são
**Bronze, Prata, Ouro e Platina** (*Diamante está proibido*: colidiria com os
Cristais, que são a moeda); o medidor de esforço por desafio chama-se
**Forja**, e vira selo na própria obra ("forjada em 14 tentativas"); a
vitrine pública mora em **`meshcraft.top/estudio/apelido`**. Onde o plano de
30/08/2026 ainda escrever "Têmpera", **leia Forja** — o plano foi escrito
antes da Sessão A e o registro `20260830-061` é o mais novo.

**Quando ela existir de verdade**, a linha dela entra na tabela das células
acima, junto com `celulas.yml`, `ci/manifesto-de-contratos.json` e
`constituicoes/AGENTS.gamificacao.md` — e aí o teste-guarda
`ci/tests/test_painel_ia_atualizado.py` passa a **exigir** que este mapa a
cite, em vez de apenas aceitar que ele a antecipe.

## A 16ª célula, nascida em 04/09/2026: `metricas`

**Onde está a lei.** `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2 (o livro
de fatos), §6.4 (marcos, coortes, dimensões) e §6.6 (a confiança). A
constituição da célula é `constituicoes/AGENTS.metricas.md`. Na gênese ela tem
UMA rota (`/healthz`), nenhuma tabela e nenhum cliente: tudo o que a
constituição descreve como "expõe" é o destino da escada, não o estado do
disco.

**O que ela é.** O livro de fatos da plataforma. Toda tela de gestão da casa
conta AO VIVO, perguntando às células a cada abertura: isso responde "quantas
alunas há agora" e nunca "quantas havia na semana passada". A `metricas`
recebe os eventos que as outras publicam (`contracts/eventos/*.json`), guarda
esses fatos imutáveis e responde por API de leitura, para que o painel possa
dizer o que MUDOU.

**O que ela NÃO é, e isto é o que mais importa para quem chega:**

- **Não é dona de nada.** Ela não decide sobre pessoa, matrícula, ponto ou
  mensagem. O dono de cada fato continua sendo quem o emitiu. Ela é
  consumidora pura.
- **Não tem tela, e nunca terá.** Quem mostra número é a `admin`, que já tem
  porta e uma leitora só (o mantenedor). Propor uma tela aqui é duplicar a
  porta de administração.
- **Não pergunta nada a ninguém.** `celulas.yml` diz `consome: []` e vai
  continuar dizendo com a célula completa: `consome` mede leitura de API
  alheia, e esta célula lê EVENTOS. O que o evento não trouxer, ela não sabe,
  e dizer "não sei" é resposta legítima. Completar buraco perguntando ao vivo
  transformaria o livro de fatos num espelho do presente.
- **Não guarda texto nem nome.** Só ids opacos e contagens. Para contar não é
  preciso saber quem é.

**Os invariantes que vão junto com ela** (detalhe em `AGENTS.metricas.md`): o
evento é imutável (correção é evento novo); duplicata se recusa pelo id
externo; evento inválido vai para a fila de eventos mortos e vira incidente,
nunca é aceito pela metade; o fuso é `America/Sao_Paulo` porque a unidade da
medição é o DIA; e "não sei" nunca vira zero.

**A escada:** 7.1 gênese (feito) · 7.2 o evento imutável e a fila de mortos ·
7.3 a recepção com Bearer e o teste de 401 · 7.4 a API de leitura, o contrato
congelado e a `admin` como cliente · 7.5 o compose, em PR próprio. Até o 7.5,
o `deploy-celula` desta célula fica vermelho em todo merge que a toca, e isso
é esperado (`armadilhas/088`).

## A 15ª célula, nascida em 03/09/2026: `encomendas`

**Estado:** lei escrita a partir do plano mestre v0.1 que o mantenedor
trouxe e **aprovada por ele em 03/09/2026** (pergunta estruturada; registro
`20260904-006`); esqueleto em `services/encomendas` no mesmo dia (só
`/healthz`, sem tabela, sem tela, sem contrato congelado). Esta
seção existe para que a próxima IA não desenhe marketplace, oferta de
trabalho a aluno, fila remunerada ou portfólio de encomenda dentro de outra
célula sem saber que já há dona para isso. **Fonte de verdade:**
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (a lei: as emendas da casa
ao plano, os invariantes, os parâmetros, a escada),
`docs/decisoes/PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` (o produto, texto do
mantenedor) e `docs/decisoes/CONTRATO-encomendas-v1-rascunho.md` (o contrato
em papel). O resumo abaixo é curado: divergiu, **o original vence**. Quem
responde "isto já foi feito?" continua sendo só o livro e a fila.

**O que ela é.** O marketplace de encomendas 3D da escola visto de dentro:
perfis profissionais dos formados, a **Fila do Primeiro Dólar** (uma fila,
uma regra: menos entregas aprovadas primeiro, empate por quem entrou antes),
ofertas com relógio de 3 horas úteis, encomendas com máquina de estado,
entregas, revisão humana obrigatória na primeira entrega, correção única,
mediação e a tela de plantão do professor. **A plataforma escolhe o aluno,
não o cliente**: não há lista de freelancers, lance nem ranking, e a lista do
que fica fora está copiada literalmente na lei §2.

**A emenda de 04/09/2026, que a próxima IA precisa conhecer antes de ler o
parágrafo acima.** O mantenedor pediu uma área de negociação, a sessão parou
como o critério de morte 1 manda, perguntou, e ele liberou duas coisas que a
lei proibia: **proposta** e **mural aberto**. Fonte de verdade:
`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md`, e a lei carrega o registro da
reabertura no §2.1. O que mudou, e só isto:

- **O Mural** é a segunda pista. Aluno com zero entregas aprovadas não o vê;
  projeto de nível Iniciante nasce na fila e só chega ao Mural pela chamada
  aberta; projeto Intermediário ou Avançado nasce nele. **Não é leilão:** uma
  reserva viva por projeto, com relógio, e a ordem é só a antiguidade.
- **A Proposta** é formulário com rodadas contadas, nunca conversa: o
  invariante S1 (sem texto livre) não foi revogado e é o que lhe dá forma.
  Quem propõe primeiro é o aluno. O acordo congela valor, prazo e entregáveis.
- **O pagamento mudou de lugar**, não de dono: acontece depois do acordo,
  porque não se cobra valor ainda não combinado. Não adianta uma linha de
  cobrança, porque a origem continua sendo só `escola`.
- **Nove invariantes novos** (M1 a M4, N1 a N5); os dez de justiça da fila
  (J1 a J10) continuam inteiros e sem exceção.

**Continua fora, e continua critério de morte:** lance ou leilão, o cliente
escolher entre alunos, ranking, notas públicas, chat livre, segunda regra de
ordem, matchmaking por IA.

**As emendas da casa ao plano** (o plano foi escrito fora deste repositório):
a escola é 18+, então o ator "Responsável" saiu; o contrato HTTP só congela
depois da porta de máquina (`armadilhas/228`, `243`); os invariantes nascem
declarados na lei e viram guarda no PR do motor; **dinheiro por último** (a
Fase 3 espera o sinal do mantenedor, e até lá a única origem de encomenda é
`escola`, confirmada pelo plantão com autor); o portfólio mora no Estúdio
(`/estudio/<apelido>`, opt-in, célula `pages`), e esta célula só responde
quais peças estão aprovadas e autorizadas; o título de Banca, enquanto a
Banca não existe, é dado pelo professor na tela de plantão.

**O que ela consome:** `identidade` (quem é o dono do cookie; ela não assina
sessão, INV-P12) e `alunos` (a categoria da pessoa). Na gênese,
`consome: []` (`armadilhas/224`).

**O que ela oferece (contrato, Bearer por par):** `getParameters` e
`setParameter` (a tabela de parâmetros da fila, com histórico, editada pelo
Admin), `getQueueStanding` (a fila de uma pessoa: disponibilidade, título,
entregas, espera estimada), `getApprovedPieces` (peças aprovadas e
autorizadas, para o Estúdio), `confirmPayment` (da `pagamentos`, Fase 3) e
`reportAudit` (do worker de auditoria com Blender, Fase 5).

**O que ela emite:** 20 eventos (`encomenda.*`, `oferta.*`, `entrega.*`,
`aluno.pausado`/`.disponivel`, `portfolio.publicado`, `pedido-direto.criado`,
todos `.v1`, só ids opacos) e `notificacao.devida.v1` com assuntos
`encomendas.*`. A gamificação escuta `encomenda.aprovada.v1` para os Marcos
#3 (Primeiro Dólar) e #4 (Primeiro Cliente Real).

| O que ela NÃO faz | Quem faz |
|---|---|
| Cobrar, reter, repassar, reembolsar | `pagamentos` (Fase 3, depois do sinal do mantenedor) |
| Saber o que é Marco | `gamificacao`, por evento |
| Mostrar o portfólio | `pages` (o Estúdio), perguntando `getApprovedPieces` |
| Dizer quem é aluno | `alunos` (`getStudentStanding`) |
| Dar aula ou o título de Banca | a célula de cursos (a nascer); até lá o professor dá o título |
| Auditar o arquivo 3D | o worker de auditoria (imagem própria com Blender) |

**Invariantes declarados na lei §5, com o caminho do guarda:** dez de
justiça (`[INV-ENC-J1..J10]`: uma oferta por encomenda e por aluno, o menor
`(entregas, data_entrada)` primeiro, só abandono muda o lugar, nível mínimo,
nunca a mesma encomenda duas vezes, trabalhando não recebe, relógio congela
fora de 8h–22h, vira aberta em 24h, motor idempotente), cinco de dinheiro
(`[INV-ENC-D13..D17]`) e cinco de segurança (`[INV-ENC-S1..S5]`: sem texto
livre entre cliente e aluno, primeira entrega sempre revisada, sem contato do
aluno, peça só com autorização, cliente novo passa pelo plantão).

## A célula `cursos`, nascida em 04/09/2026

**Estado:** plano escrito a partir dos nove documentos do projeto Meshcraft
que o mantenedor trouxe em 04/09/2026 (eles moram FORA do repositório, de
propósito: obra não lançada, `armadilhas/331`), e **aprovado por ele em
pergunta estruturada na mesma sessão** (registro `20260905-001`, PR #1044);
esqueleto em `services/cursos` no mesmo dia (TAR-146: só `/healthz`, sem
tabela, sem tela, sem contrato congelado). **Fonte de verdade:**
`docs/decisoes/PLANO-CELULA-CURSOS.md` (a visão, as emendas da casa aos nove
documentos, o modelo, os eventos, as superfícies, os agentes de IA, os
invariantes, a escada) e `docs/decisoes/CONSTITUICAO-cursos-rascunho.md` (a
constituição em papel, promovida na gênese). O resumo abaixo é curado:
divergiu, **o original vence**. Quem responde "isto já foi feito?" continua
sendo só o livro e a fila. Esta seção existe para que a próxima IA não
desenhe aula, progresso de aluno, checkpoint ou laudo dentro de outra célula
sem saber que já há dona para isso.

**O que ela é.** A sala de aula da Meshcraft: dona do conteúdo do curso (33
encomendas e uma Bônus, cada uma com 16 peças, o roteiro da aula, a ficha do
Guia do Mentor, o vídeo por link, as pausas reais, os 13 instrumentos), do
progresso de cada aluno (que porta está aberta), do checkpoint (o envio, por
link, na fila de revisão com prazo de 24 horas) e do laudo (o instrumento,
três forças, uma mudança nomeada pela encomenda onde se aprende, a decisão, a
data se devolvido, e a pergunta "ele sabe o que fazer amanhã de manhã?"). E
dos **agentes de IA que trabalham nela**, começando pelo Assistente de laudo,
no molde do agente do fórum: a IA escreve, a pessoa assina.

**Por que UMA célula, e não conteúdo no repositório mais uma célula
`avaliacao`, como os documentos de fora propunham:** o repositório é público
e o curso é obra não lançada; `alunos` só sabe matrícula, nenhuma célula
serve aula, e o envio é a porta da lição, então separar checkpoint e laudo
faria a transação mais comum da escola atravessar duas células sem ganhar
isolamento. Pares e Bancas entram como degraus desta mesma célula.

**As decisões do roadmap que viram invariante aqui:** o checkpoint abre a
porta, o calendário nunca; entregar dá XP e aprovar dá porta; **não existe o
estado "reprovado"**; toda devolução tem uma mudança única e uma data; o
laudo não envia sem a pergunta de amanhã de manhã; rubrica antes da opinião
(regra de API, 422); o prazo de 24 horas não se alonga, só se registra o
estouro; nenhuma tela compara alunos; a pausa real registra.

**O que ela consome:** `identidade` (quem é o dono do cookie) e `alunos` (a
matrícula ativa decide o acesso, fail-CLOSED). Na gênese, `consome: []`
(`armadilhas/224`).

**O que ela oferece (contrato, Bearer por par):** o editor para o Admin
(`listLessons`, `getLesson`, `putLesson`, `putInstrument`, `publishLesson`),
os verificadores (`checkLesson`: coerência mecânica e fidelidade por IA), o
placar da fila (`getReviewQueue`, contagens, nunca quem) e
`getStudentProgress` (para o Estúdio e a home).

**O que ela emite:** `envio.recebido.v1`, `laudo.emitido.v1`,
`aula.concluida.v1` (a tomada que a gamificação já previa, com `e_boss`),
`checkpoint.devolvido.v1`, `revisao.prazo-estourado.v1`, `banca.decidida.v1`
(Fase 5) e `notificacao.devida.v1` com assuntos `cursos.*`. Só ids opacos.

| O que ela NÃO faz | Quem faz |
|---|---|
| XP, medalha, Marco, título de nível | `gamificacao`, por evento |
| Portfólio, Meu Estúdio, as 35 Páginas | `pages` (o Estúdio) |
| Matrícula, quem entra | `alunos` |
| O curso como produto à venda | `catalogo` |
| O quiz de captação (o Crivo) | `quiz` (o quiz da encomenda é dado da aula, com autoavaliação) |
| O silêncio de 14 e 30 dias | jornada da `mensageria`, cancelada por `envio.recebido.v1` |
| O Padrão, os apêndices vivos, o dicionário | a área de `documentos` |
| Guardar arquivo | ninguém: o checkpoint é por link, como o portfólio |

**Invariantes declarados na lei §9:** sete do laudo (`[INV-CUR-L1..L7]`: data
se devolvido; "reprovado" não existe; 24 horas imutável; a IA nunca decide;
rubrica antes; três forças e uma mudança; a pergunta), três da porta
(`[INV-CUR-P1..P3]`: sem comparação; porta só por laudo, nunca por data, XP ou
pagamento; checkpoint fechado até as pausas), dois do conteúdo
(`[INV-CUR-C1..C2]`: remissão quebrada não publica; conteúdo só pela porta de
máquina, nunca por migração com texto), dois de segurança
(`[INV-CUR-S1..S2]`) e `[INV-P12]`.

**Superfície pública:** `/cursos` (host-bound em `meshcraft.top`; 6 letras,
passa no guarda de locale), `/cursos/<numero>`, `/cursos/<numero>/laudo`,
`/cursos/plantao`; e o editor em `/admin/escola/aulas/`, na `admin`, pela
porta de máquina.

**Ela existe desde 04/09/2026** (`celulas.yml`, `ci/manifesto-de-contratos.json`
e `constituicoes/AGENTS.cursos.md` no lugar), e o teste-guarda
`ci/tests/test_painel_ia_atualizado.py` **exige** que este mapa a cite.

## A 18ª célula, ainda NÃO nascida: `pages`

**Estado:** a casa foi escolhida pelo mantenedor em 01/09/2026, renomeada por
ele de `portfolio` para `pages` em 02/09/2026 (registros `20260901-023`,
`20260902-061` e `20260903-003` no livro), e a construção foi liberada por ele
em 05/09/2026 com a assinatura do corredor
`docs/changespecs/CS-PAGES-0001.md`. **A pasta `services/pages` ainda não
existe**: ela nasce no degrau 01 da escada do §5 do plano, e esta seção foi
escrita no degrau 00, de propósito, antes do código. **Fonte de verdade:**
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` (a fronteira no §4, a escada no §5,
o preço da foto por link no §6.2, o que ninguém pode inventar no §7 e os
critérios da escola no §8) e o corredor `CS-PAGES-0001`. O resumo abaixo é
curado: divergiu, **o original vence**. E quem responde "isto já foi feito?"
continua sendo só o livro (`painel/registros/`) e a fila (`fila/`). Esta seção
existe para que a próxima IA não desenhe portfólio de aluno, vitrine pública de
obra ou página nova do aluno dentro de outra célula sem saber que já há dona
para isso.

**O que ela é.** A casa das PÁGINAS do aluno, não só do portfólio. A razão do
mantenedor, em 02/09/2026: *"quero `pages` porque podemos criar todo tipo de
ferramentas, portfólio, estúdio, e etc"*. Um nome específico (`portfolio`,
`ferramentas`) excluiria o que não é ferramenta nem portfólio, e o guarda-chuva
é o ponto. O que isso muda de verdade é o custo por pedido do aluno: o caro
nunca foi a tela, foi a fundação (banco novo, provisionamento, rota e o passo
manual que só o mantenedor executa). Com a casa guarda-chuva esse pedágio é
pago UMA vez, e da segunda página em diante o custo é um PR de tela e zero
passo dele. É por isso que ela é, por decisão registrada, a ÚLTIMA casa nova do
site.

**Dois endereços, uma casa.** Os dois prefixos apontam para a mesma célula no
Traefik:

- `meshcraft.top/pages/...`, a área do aluno logado, onde o portfólio é a
  primeira página e as próximas entram ao lado;
- `meshcraft.top/estudio/<apelido>`, a vitrine pública, opt-in, com `noindex`
  e sem e-mail, telefone ou nome completo. O endereço é curto de propósito:
  é o link que o aluno manda ao cliente no chat, e `/pages/estudio/joao` seria
  pior ali.

**Nome da célula igual ao nome da rota, de propósito.** O par `/conquistas` para
`gamificacao` já custa uma tradução mental a cada leitura, e não se cria um
segundo.

**Ela não assina sessão (`INV-P12`).** Repassa o cookie à `identidade`, e a
matrícula ativa decide o acesso pelo caminho normal da porta, fail-CLOSED.

**A peça tem UMA casa.** O portfólio não guarda cópia de medalha, a
`gamificacao` não guarda cópia de peça, e a tela que precisa das duas pergunta
por HTTP com falha ABERTA (o mesmo desenho já usado entre `forum` e
`gamificacao`), nunca por chave estrangeira cruzando banco de célula.

**A foto é LINK colado, decisão do mantenedor em 01/09/2026, e ela não se
reabre.** O aluno cola o endereço do render que já guarda no Drive, no
ArtStation ou onde quer que seja. O preço está escrito no §6.2 do plano, e está
repetido aqui para ninguém o redescobrir por acidente:

- **link de aluno quebra**, e quando quebra a escola não consegue consertar. A
  mitigação é a Prancheta conferir o link no momento em que ele é colado, avisar
  pelo sininho quando ele parar de responder depois, e **nunca apagar a peça
  sozinha**;
- **a página pública passa a exibir imagem de domínio de terceiro**, o que
  nenhuma outra tela desta plataforma faz hoje. A política de conteúdo da página
  precisa permitir imagem externa de forma controlada, com teste;
- **a escola não controla o que está do outro lado do link**, então o selo
  "conferido pela escola" vale para o que o monitor viu no dia da conferência, e
  o texto do selo precisa dizer isso.

Guardar imagem no servidor é o degrau 09, riscado da escada: ele volta no dia em
que o mantenedor pedir, e **não se constrói antes disso**.

**O que ela emite:** `pages.portfolio.*`, congelados no degrau 03 em
`contracts/`. É por eles que a `gamificacao` sabe do selo e acende o marco
"portfólio" na trilha, sem pagar XP. Nenhum outro evento novo, e nenhum outro
contrato novo: o que ela consome é o contrato de identidade (quem é a pessoa) e
o de matrícula ativa.

**A escada, e o que ela autoriza fora desta célula.** Os degraus 01, 02, 06 a 08
e 10 a 14 são desta célula (a gênese, os modelos, a porta, a Prancheta com as
cinco etapas, as peças por link, o semáforo, o pedido de conferência, o selo, a
vitrine e o dossiê em PDF). Os degraus vizinhos são de outras casas, um PR por
degrau: `contracts` no 03, `infra` no 04 e no 05, `gamificacao` no 15 (só
escutar o evento e acender o marco), `admin` no 16 (os guias no editor de
documentos), `mensageria` no 17 (a sequência que convida quem terminou as aulas,
por fato **declarado**, nunca por inferência de progresso) e `funil` no 18 (o
caminho no menu e na home logada). O degrau 07 lê do banco a lista de
conferência que a professora da escola escreveu no §8 do plano: pelo menos 3
tipos de modelo entre os que o curso ensina, pelo menos 3 peças de cada tipo
escolhido, a maioria das peças em high poly, e nada que se pareça com o modelo
feito na aula.

**O que ninguém pode inventar aqui (§7 do plano):**

- nota, estrela, ranking ou voto popular em portfólio ou em peça de aluno;
- detecção de "isto foi feito por IA";
- trancar aula ou conteúdo do curso atrás de check-list, ponto ou nível;
- e-mail, telefone ou nome completo na página pública, e o `noindex` não é
  negociável;
- guardar a peça em duas células;
- travessão em texto que o aluno lê (`ci/travessao.py`);
- marco real pagando XP (ele vale zero, de propósito).

**Ela ainda não está em `celulas.yml`, não tem constituição, não tem manifesto e
não tem contrato.** Enquanto a pasta não existir, o teste-guarda
`ci/tests/test_painel_ia_atualizado.py` não a cobra: ele exige que toda célula
de `services/` apareça neste mapa, e não proíbe o contrário. Quando ela nascer
no degrau 01, é este parágrafo que muda.

## O mecanismo de contratos: OpenAPI + eventos, e o freeze que os protege

`contracts/README.md` chama a pasta de "**Muralha nº 4**" — a implementação
da Lei 2.4 (Contrato) da `CONSTITUICAO.md`. Regras centrais: nenhuma sessão
normal edita `contracts/` (mudança = Rito de Contrato, `RITOS.md` §3: PR só
com `contracts/`, label `contrato`, aprovação do mantenedor, provedor
implementa primeiro com retrocompatibilidade, consumidores em PRs
seguintes); consumidor desenvolve contra mock Prism, nunca contra o código
do provedor; eventos são versionados no nome do arquivo (`*.v1.json` →
`*.v2.json` numa mudança breaking, com o `v1` continuando a ser emitido até
o último consumidor migrar — hoje `sugestao.status-alterado.v1.json` e
`.v2.json` **coexistem de verdade**, o v2 acrescentando `ator_id` ao
envelope); envelope canônico `{event, version, event_id, occurred_at, data}`,
consumo idempotente por `event_id`; autenticação por Bearer estático **por
par nomeado** (checkout→pagamentos ≠ funil→leads, tokens nunca
compartilhados entre pares).

O congelamento é vigiado por `ci/contract_freeze.py` — reescrito em Python
depois de um **incidente real**: a versão antiga em Bash chamava `python3`
(ausente numa máquina), os dois lados do diff viravam string vazia,
`diff(vazio, vazio)` dava "igual" e o script imprimia "OK" sem ter comparado
nada. A versão atual tem duas defesas específicas:
1. Normalização com guarda-contra-vazio — documento `None`/inválido vira
   ERROR (exit 2), nunca uma string comparável.
2. Segunda checagem, **independente**, da autenticação efetiva: o diff
   textual do OpenAPI é cego para auth porque o django-ninja **omite** a
   chave `security` em rotas públicas em vez de emitir `security: []` — e
   por spec OpenAPI, ausência de `security` *herda* a segurança do
   documento pai. Já causou um caso real medido (endpoint de `catalogo`
   virou público sem o freeze acusar nada). A correção não lê o documento:
   uma sonda importa o app Django de verdade e lê a lista real de
   autenticadores que o ninja vai executar.

## Fluxo de eventos entre células

**Comércio** (síncrono + assíncrono misturados): `checkout` chama
`pagamentos` diretamente via HTTP para criar a cobrança; em paralelo emite
`pedido.criado.v1` (consumido por `leads`). `pagamentos` recebe o webhook do
Mercado Pago, confere a assinatura (INV-P10), **reconsulta o status na API
do MP** em vez de confiar no corpo do webhook, e emite
`pagamento.aprovado.v1` / `pagamento.recusado.v1` / `pix.expirado.v1` —
consumidos por `checkout` (INV-P7), `alunos` (matrícula sob lock, INV-P5, só
no aprovado), `mensageria` e `leads`. `quiz` emite `quiz.completado.v1`,
consumido por `leads` (mas o consumo em `mensageria` ainda **não está
implementado**, apesar de listado na constituição).

**Voice-of-customer**: `sugestoes` emite `sugestao.criada` /
`voto-adicionado` / `voto-removido` / `status-alterado.v1|v2`. Ninguém fora
da célula consome `status-alterado` para avisar o aluno diretamente — a
própria `sugestoes`, na mesma transação, gera `notificacao.devida.v1`
("uma carta, uma pessoa", fan-out feito **na origem**) para `notificacoes`,
que só ouve esse único stream e fica deliberadamente "burra" (grava uma
linha, incrementa contador — não sabe montar leque de destinatários). Ver
[06 — produto e decisões](06-produto-decisoes-e-roadmap.md) para o porquê.

## Isolamento entre células (`ci/cerca-de-celula.sh`)

Implementa a Lei 2.3 (uma sessão = uma célula = um worktree) e a Lei 3
(proibido importar código/ler banco de outra célula). Roda em todo PR:
calcula o diff, extrai células tocadas em `services/*`, **reprova se o diff
tocar mais de uma** — a mensagem manda abrir um PR por célula. Reprova
também se `contracts/` mudar junto com qualquer `services/`, e se
`contracts/` mudar sem a label `contrato`.

O isolamento de dados é reforçado a nível de infraestrutura, não só de CI:
cada célula tem seu próprio database + role Postgres — a conexão de uma
célula **não consegue** ler outra (`permission denied` do próprio banco, não
convenção). A única forma legítima de uma célula levar dado de outra é
**copiar** (snapshot), nunca importar código nem ler banco alheio — por isso
`checkout` congela o preço no pedido em vez de re-perguntar ao catálogo
depois.

## Achados concretos surgidos desta pesquisa (candidatos a PR pequeno)

1. **`ci/manifesto-de-contratos.json` tem motivo desatualizado** para `funil`
   e `quiz` — o texto diz "célula ainda em esqueleto, só expõe `/healthz`",
   mas `funil` já tem ~10 rotas HTML com i18n de 3 idiomas e `quiz` serve um
   formulário completo. A conclusão (sem API JSON, sem contrato) continua
   válida — só o texto do motivo mente sobre a maturidade real da célula.
2. **`sugestao.mesclada.v1` é prometido na constituição de `sugestoes`** mas
   o arquivo não existe em `contracts/eventos/` — ou ainda não foi
   implementado, ou a constituição está adiantada em relação ao contrato.
3. **`checkout` expõe um Bearer token estático no HTML da página**
   (visível em "ver código-fonte") — a própria `LICOES.md` da célula já
   registra isso como pendência de arquitetura em aberto, não decisão
   fechada, sugerindo um token de curto prazo por sessão como alternativa.
4. **`quiz` resolve "Site" localmente** (tabela própria, seedada à mão) em
   vez de chamar a API do `catalogo`, como a receita genérica do Caminho
   Dourado prescreve — desvio deliberado e documentado, mas a própria
   `LICOES.md` pede revisão humana da leitura, porque o `site_id` local
   precisa ficar sincronizado manualmente com o do catálogo, sem checagem
   automática.

Estes 4 pontos também aparecem em
[07 — oportunidades e fronteiras](07-oportunidades-e-fronteiras.md).
