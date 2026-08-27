# PLANO MESTRE — o sistema de notificações da plataforma

> **Escrito em 25/08/2026**, a pedido do mantenedor, logo depois de o Lote 4 da Caixa
> de Sugestões fechar. O pedido dele, nas palavras dele: *"quero que todos os que
> interagiram com a ideia sejam notificados, em um sininho na tela ao lado do nome,
> algo como as notificações do Facebook, e isso já é o começo do que vamos enviar de
> notificações para o aluno e **serão muitas**"*.
>
> **O que este documento é:** o desenho do caminho, com o terreno medido no código
> real, as tensões nomeadas e as fases dimensionadas como lotes.
>
> **O que este documento NÃO é:** autorização para construir. A Fase 0 é uma sessão
> de decisão com o mantenedor (§7), pelo mesmo motivo que a Caixa teve a EVO-01: as
> escolhas aqui mudam a forma da plataforma, e uma delas cria célula nova.
>
> **ATUALIZAÇÃO 25/08/2026 — a Fase 0 está FECHADA.** O mantenedor respondeu as três
> perguntas da §7 (*"sim, sim e nascer só com a Caixa"*), e as respostas viraram lei em
> **`docs/decisoes/DECISAO-notificacoes.md`**. A partir daqui este plano é o **mapa de
> execução**; a lei é aquele documento. **Se os dois divergirem, a lei vence.**

---

## 1. A parte fácil já está pronta — e é a menor parte

Desde 25/08/2026 a Caixa avisa **quem criou, quem votou e quem comentou** quando uma
ideia muda de status, com etiqueta de origem e tudo (EVO-42, PR #193). O sininho
existe, conta os não-lidos, e a página de avisos está vestida.

**Mas ele só existe dentro da Caixa.** Quem está lendo uma página do site — a vitrine,
o cadastro, o quiz — não vê aviso nenhum. E é exatamente isso que o pedido do
mantenedor descreve: o sininho **ao lado do nome**, em qualquer página.

A distância entre as duas coisas não é uma tela. É a §2.

---

## 2. O NÓ — medido, e é o coração deste plano

**Não existe, hoje, um identificador de pessoa que atravesse a plataforma.**

Medido no código em 25/08/2026:

| Onde | Modelo | Chave real | Id |
|---|---|---|---|
| `services/identidade/apps/identidade/models.py` | `Identidade` | `email` (único) | opaco, cunhado ali |
| `services/sugestoes/apps/sugestoes/models.py` | `Identidade` | `email` (único) | opaco, cunhado ali |

São **duas tabelas independentes**. A mesma pessoa tem **dois ids opacos diferentes**,
e a única coisa que os une é o e-mail — que, por decisão do mantenedor
(`DECISAO-EVO-01-identidade.md` §3), **vive numa linha só e não circula**.

E os eventos no fio herdam o problema. O `sugestao.status-alterado.v1.json` diz, na
própria descrição do campo:

> `autor_da_sugestao_id`: *"Id OPACO da identidade **dentro da célula sugestoes**.
> NUNCA é o e-mail… **Consumidor que precise falar com a pessoa não resolve isto
> sozinho.**"*

**Consequência, e é dura:** uma caixa de notificações central, alimentada pelos
eventos que já existem, **não consegue endereçar ninguém**. Ela receberia o fato
("a sugestão 731 mudou de status") e um id que não significa nada fora da Caixa.

### A boa notícia: o conserto é pequeno, e o dado já passa na mão

A Caixa chama `GET /sessao/completa` a cada entrada, e a resposta **já traz o `id` da
identidade da plataforma** (está no contrato congelado, `SessionFull.id`). O
`services/sugestoes/apps/core/sessao.py` lê `email`, `nome_exibido` e `autenticado`
— e **descarta o `id`**.

Ou seja: o elo que falta atravessa a plataforma todo dia, e é jogado fora na porta.

**Fase 0 do plano é guardá-lo.** Toda célula que cunha identidade local passa a
guardar, ao lado, o id da plataforma. A partir daí os eventos podem carregar um
`ator_id` que qualquer célula entende, e uma caixa central passa a ser possível.

Sem isso, **nada do resto deste plano funciona** — e qualquer atalho vira o e-mail
circulando, que é a decisão que não se reabre.

---

## 3. A TENSÃO que o plano não pode esconder

Hoje o aviso da Caixa nasce **dentro da mesma transação** da mudança de status. Não é
detalhe de implementação: é invariante escrito, com guarda que morde, e a
`DECISAO-EVO-40` §2 o protege nominalmente. O motivo está no código:

> *"Redis fora do ar deixaria o status mudado e o aluno sem aviso, e nada na Caixa
> indicaria a falta."*

**Uma caixa central muda essa garantia.** O fato viaja pelo fio (outbox → relay →
consumidor), então a promessa deixa de ser *"o aviso existe no mesmo instante"* e
passa a ser *"o fato está durável na outbox, e o aviso chega em seguida"*.

Isso **não** é afrouxamento de durabilidade — o padrão outbox já garante que o fato
não se perde, e a plataforma inteira já roda assim (`INV-P6`). O que muda é a
**latência** e a **janela em que o aluno ainda não sabe**.

As três saídas honestas, com o preço de cada uma:

| Saída | O que acontece | Preço |
|---|---|---|
| **A. Caixa central pura** | a `sugestoes` só publica o evento; o aviso mora na célula nova | perde-se o aviso transacional; a Caixa passa a depender do fio para a própria tela |
| **B. Local + central (espelho)** | a Caixa mantém o `Aviso` dela (transacional) **e** o fato vai ao fio para a caixa central | duas verdades sobre o mesmo aviso; "lido" num lugar não é "lido" no outro sem trabalho extra |
| **C. Central com escrita síncrona** | a `sugestoes` chama a célula de notificações por HTTP dentro da transação | acopla duas células no caminho crítico; a célula de notificações fora do ar **impede mudar status**. Contraria a Lei 3 |

**Recomendação: A, com a garantia reescrita.** A promessa vira *"a mudança de status
e o fato notificável nascem na mesma transação; a entrega é em segundos, e é
rastreável"* — e o guarda muda junto, medindo a outbox em vez da tabela de avisos. **B
parece o mais seguro e é o mais caro**: duas verdades sobre "lido" é o tipo de dívida
que só aparece quando o aluno reclama que já tinha lido. **C está fora** — é a Lei 3.

---

## 4. Onde a caixa de notificações mora

| Opção | A favor | Contra |
|---|---|---|
| **Cada célula com a sua, e o site agrega** | zero célula nova; nada muda no que existe | o site faria **uma chamada HTTP por célula** só para desenhar um sino, e o custo cresce a cada célula nova. Some com o "uma consulta" e vira latência no caminho de toda página |
| **Dentro da `identidade`** | ela já tem contrato que o site consome; zero célula nova | contraria a própria lei dela, escrita no contrato: *"A resposta desta API **RECONHECE** uma pessoa; ela nunca AUTORIZA nada"*. Dar a ela estado de domínio a transforma em outra coisa |
| **Célula `notificacoes` própria** ✅ | um lugar, um contrato, uma consulta; cresce sem tocar em quem publica; banco isolado como manda a Lei 3 | **cria célula nova** — decisão do mantenedor, com gênese, contrato congelado e passo de provisionamento na VPS |

**Recomendação: célula `notificacoes` própria.** O argumento decisivo não é elegância,
é o *"serão muitas"* dele: um sino que o site desenha em toda página tem de custar
**uma** pergunta barata, e tem de continuar custando uma quando existirem dez células
publicando. As outras duas opções são mais baratas hoje e mais caras todo dia depois.

**Isto é o congelamento arquitetural sendo aberto de propósito**, e por isso é decisão
dele — não minha. Foi assim que a `sugestoes` e a `identidade` nasceram.

---

## 5. Duas coisas que o desenho tem de acertar desde o primeiro dia

### 5.1 A notificação é DADO, nunca frase pronta

O site serve **três idiomas** (`en` na raiz, `pt-br`, `es` — `infra/sites.json`).
Guardar *"Sua ideia mudou para Em desenvolvimento"* no banco congela o idioma de quem
gravou, e a pessoa que lê em espanhol recebe português para sempre.

**Regra:** a linha guarda `tipo` + `parametros` (json) + `ator_id` + `lido_em`. A frase
nasce **na leitura**, no idioma de quem está lendo. É a mesma disciplina do i18n que a
plataforma já aplica, e é irreversível se errada — texto já gravado não se traduz
depois.

**Exceção que precisa ser decidida:** a `nota` da equipe (a justificativa de um "não
planejado") é texto humano, escrito num idioma só. Ela **não** se traduz sozinha, e
fingir que sim seria pior. Proposta: mostrar como citação, com o idioma marcado.

### 5.2 O contador tem de ser barato, e "muitas" é a palavra dele

O sino aparece em **toda página**. Se o contador for um `COUNT(*)` numa tabela que
cresce para sempre, ele fica lento exatamente quando o produto der certo.

O que o plano exige, e cada um tem teste de volume:
- contador **O(1)** — coluna/contador por pessoa, não varredura;
- fan-out em **lote** (a lição do EVO-42: três consultas fixas, tenha a ideia 2 ou 200
  votantes; `armadilhas/116` explica por que `bulk_create` exige cuidado com guardas);
- **arquivamento** desde o começo: notificação lida e velha sai do caminho quente;
- e o guarda que prova que **o custo não cresce com a plateia** — `assertNumQueries`
  com 2 e com 200, como o EVO-42 fez.

---

## 6. As fases

Cada fase é um lote. A ordem não é preferência: cada uma destrava a seguinte.

### FASE 0 — Sessão de decisão (com o mantenedor) · **não é código** · ✅ FECHADA em 25/08/2026

As três perguntas da §7. Sai daqui uma `DECISAO-*.md` que vira lei, como a EVO-01 foi
para a Caixa. **Nada começa antes.**

**Fechada.** A lei é **`docs/decisoes/DECISAO-notificacoes.md`** — leia-a antes de
tocar qualquer fase seguinte: ela fixa a gênese da célula, a garantia nova (e o guarda
que muda junto), o recorte da V1 e as duas irreversibilidades do desenho.

### FASE 1 — O id que atravessa · células `sugestoes` (+ qualquer outra que cunhe identidade)

Guardar o id da plataforma ao lado da identidade local, **sem apagar** o casamento por
e-mail que já existe (ele preserva a autoria de tudo que foi criado antes do login
mudar de casa). Migração que preenche o que dá, e caminho para o que faltar na próxima
entrada da pessoa.

**Destrava tudo. É a fase mais barata e a mais importante.**

### FASE 2 — Rito de Contrato: o envelope de evento ganha `ator_id` · ✅ FECHADA em 26/08/2026

**Fechada.** Rito cumprido com o mantenedor presente; as três escolhas dele viraram lei em **`docs/decisoes/DECISAO-fase-2-do-sininho.md`** — leia-a antes de tocar a Fase 3, porque ela **muda o tamanho** daquela fase (§3 de lá) e **muda o endereço** do fan-out (§1 de lá). Os contratos entraram no PR #243: `sugestao.status-alterado.v2.json` (o fato, com `ator_id` obrigatório no envelope) e `notificacao.devida.v1.json` (a carta endereçada, uma por pessoa).

Falta só o passo §3.4 do rito: a `sugestoes` migrar para o `v2` em PR próprio, na célula dela. Medido em 26/08: **zero** consumidores externos do `v1`.

Os eventos passam a carregar um id de pessoa que qualquer célula entende. **Rito §3**,
com o mantenedor presente, PR só de `contracts/` com a label `contrato`. Versão nova do
schema (`v2`), com os consumidores migrando em PRs seguintes — nunca no mesmo.

### FASE 3 — Gênese da célula `notificacoes` · **e a mudança de casa dos avisos que já existem** · ✅ CÉLULA NO AR em 26/08/2026

> **Alterada em 26/08/2026** pela §3 da `DECISAO-fase-2-do-sininho.md`: o mantenedor escolheu que os `Aviso` que já existem na `sugestoes` **mudam de casa junto**, no MESMO PR da gênese, e a tela de avisos da Caixa passa a ler da caixa nova. A alternativa (caixa nova começando vazia) foi recusada por criar duas verdades sobre "o que você tem para ler". Esta fase, portanto, não é só "nascer".

**A célula nasceu em 26/08/2026** (PRs #247 script, #248 célula, #252 compose): banco isolado, contador O(1), arquivamento, consumidor do fio, rollback no mesmo PR e `freeze: not-applicable`. Constituição em `constituicoes/AGENTS.notificacoes.md`; invariantes INV-NOT1 e INV-NOT2.

**FALTA A SEGUNDA METADE DESTA FASE:** os `Aviso` que já existem na `sugestoes` ainda NÃO mudaram de casa, e a tela da Caixa ainda lê da tabela local. É PR próprio, na célula `sugestoes` (1 PR = 1 célula), e o caminho é reemitir as cartas dos avisos existentes — o dado atravessa pelo fio, sem ninguém ler o banco alheio (Lei 2).

> E o fan-out **não acontece aqui**: a célula recebe cartas já endereçadas (uma por pessoa) e escreve uma linha por carta. Ela é burra de propósito — é isso que a mantém barata quando dez células estiverem publicando.

Banco isolado, `Notificacao` (tipo + parâmetros + destinatário + lido), consumidor dos
eventos do fio, contador O(1), arquivamento. **Sem tela ainda** e sem contrato público
— a célula nasce `freeze: not-applicable`, como a Caixa nasceu, e congela contrato só
quando alguém for consumi-la (é a correção nº 1 da auditoria da Caixa).

Inclui **passo do mantenedor** na VPS (banco + env), entregue como script versionado de
uma linha — o padrão que funcionou no H20 e no H22.

### FASE 4 — Rito de Contrato: o site pergunta

`notificacoes` expõe a superfície de máquina que o `funil` consome: contagem de
não-lidos e lista paginada. **Rito §3** de novo.

### FASE 5 — O sininho ao lado do nome

`services/funil/templates/funil/_sessao.html` — o pedaço que hoje desenha "Entrar" ou o
nome da pessoa. **Falha ABERTO, sem exceção:** notificações fora do ar ⇒ o site mostra
o nome sem sino e a página abre normal. Já é a lei do `obter_sessao` (*"a vitrine não
pode cair porque a Caixa está reiniciando"*), e vale igual aqui.

### FASE 6 — A Caixa passa a publicar o leque inteiro

Hoje o `sugestao.status-alterado` carrega só o autor — os votantes ficaram de fora **de
propósito** ("lista sem teto num evento"). Para a caixa central avisar quem votou, ou o
evento cresce, ou a `sugestoes` publica um evento por interessado. **Decidir medindo**,
não por gosto: um evento com 200 destinatários e 200 eventos de um destinatário têm
custos diferentes no Redis e no consumidor.

E aqui a Caixa **aposenta** o `Aviso` local em favor da caixa central (saída A da §3),
com migração dos avisos existentes.

### FASE 7 — Preferências, e só então outros canais

Silenciar um assunto, marcar todas como lidas, e a decisão sobre **e-mail**. Esta última
reabre uma porta fechada: a `mensageria` precisa de um destinatário, e o e-mail vive
numa linha só. **Não entra sem decisão nova.** Vale saber que o envio da `mensageria`
ainda é **stub** (`services/mensageria/apps/eventos/tasks.py`: *"Stub: loga o envio"*) —
"ligar o e-mail" é construir o envio, não plugar um fio.

---

## 7. As decisões que são do mantenedor — a Fase 0 · **RESPONDIDAS em 25/08/2026**

> **As três perguntas abaixo foram respondidas pelo mantenedor em 25/08/2026** — nas
> palavras dele, *"as respostas são: sim, sim e nascer só com a Caixa. Vou seguir as
> recomendações integralmente."* As três recomendações foram aceitas integralmente, e
> viraram lei em **`docs/decisoes/DECISAO-notificacoes.md`**. O texto das perguntas
> fica preservado aqui como registro do que estava em jogo; **a lei é o documento, não
> esta seção.**

1. **Criar a célula `notificacoes`?** É abrir o congelamento arquitetural de propósito,
   como foi feito para a Caixa e para a identidade. As alternativas estão na §4, com o
   preço de cada uma. *Recomendação: sim.* → **RESPONDIDO: SIM.**
2. **A garantia pode passar de "no mesmo instante, sempre" para "em segundos, e
   rastreável"?** É a §3, e é a única coisa deste plano que o aluno consegue perceber.
   *Recomendação: sim (saída A), com a promessa reescrita e o guarda mudando junto.*
   → **RESPONDIDO: SIM (saída A).**
3. **Quais assuntos entram na primeira versão?** Hoje só a Caixa produz fatos
   notificáveis. O quiz, a matrícula e o pagamento produzem eventos que **poderiam**
   virar notificação — e "serão muitas" sugere que virão. *Recomendação: nascer só com
   a Caixa, com o desenho pronto para os outros; assunto novo vira um PR pequeno, não
   uma refatoração.* → **RESPONDIDO: nascer só com a Caixa.**

---

## 8. O que fica FORA, e por quê

- **Push do navegador, app, SMS.** Nada disso antes de a caixa in-app existir.
- **Agrupar notificações** ("3 pessoas votaram na sua ideia"). É V1.1: exige janela de
  agregação, e agregar cedo esconde o dado que ainda não sabemos ler.
- **Notificação em tempo real** (websocket/SSE). O sino atualiza a cada página. Tempo
  real é outro problema de infraestrutura, e o pedido não precisa dele.
- **Traduzir a nota da equipe.** Texto humano; ver §5.1.

---

## 9. Riscos, com o antídoto de cada um

| Risco | Antídoto |
|---|---|
| **Fase 1 sai errada e o id da plataforma some** — todo o resto herda o defeito | teste-guarda de que toda identidade cunhada depois da migração tem o id da plataforma, e relatório do que ficou sem |
| **A caixa central vira dependência do caminho crítico** e derruba a Caixa | a `sugestoes` publica no fio e segue; **nunca** chama a célula nova por HTTP dentro da transação (é a Lei 3, e é a saída C recusada na §3) |
| **O sino quebra o site** | falha aberta na Fase 5, com guarda que prova a página abrindo com o serviço de notificações fora do ar |
| **Texto congelado num idioma** | §5.1 — dado, nunca frase. Irreversível se errado |
| **Contador lento quando o produto der certo** | §5.2 — contador O(1) e teste de volume desde o primeiro PR |
| **Duas verdades sobre "lido"** | recusar a saída B da §3; um dono só por notificação |

---

## 10. Ordem de grandeza

Sete fases, das quais **duas são ritos de contrato** (exigem o mantenedor presente) e
**uma é passo dele na VPS** (uma linha, script versionado). As demais são trabalho de
agente e cabem no ritmo dos lotes anteriores.

A Fase 1 é pequena e destrava o resto — **e vale ser feita mesmo que ele decida contra a
célula nova**, porque um id de pessoa que atravessa a plataforma é infraestrutura de
qualquer caminho, inclusive o de deixar cada célula com a sua caixa.

---

*Relacionados: **`docs/decisoes/DECISAO-notificacoes.md`** (a LEI — Fase 0 fechada),
`docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`
(§2 — a decisão que originou este plano), `DECISAO-EVO-01-identidade.md` §3 (o e-mail
numa linha só), `DECISAO-celula-de-identidade.md`, `DECISAO-onde-mora-a-sessao.md` §4
(falha aberta), `CONSTITUICAO.md` Lei 3, `RITOS.md` §3 (Rito de Contrato),
`RUNBOOK-LOTES.md` §7 (o que nunca entra num lote), `armadilhas/115` e `/116`.*
