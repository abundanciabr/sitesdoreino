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
