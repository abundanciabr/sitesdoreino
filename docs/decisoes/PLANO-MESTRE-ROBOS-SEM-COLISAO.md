# PLANO MESTRE — robôs trabalhando em paralelo sem colidir

> Nascido em 28/08/2026 da rodada de consultoria externa em
> `docs/ROBÔS TRABALHANDO EM PARALELO SEM COLIDIR/` (5 pareceres: GPT/Gemini,
> Opus, Opus-2, Fable-1, Fable-2), a pedido do mantenedor.
>
> **O que este documento é:** a síntese dos pareceres, a equipe que executa, a
> ordem de construção, e o registro auditável de cada recomendação com o
> veredito e o motivo.
>
> **O que este documento NÃO é:** um painel. Ele não guarda estado e não se
> atualiza sozinho. Quem responde "isto foi feito?" é o livro
> (`painel/registros/`) e o painel calculado dele — nunca uma lista aqui
> dentro. É a LEI ANTI-DUPLICAÇÃO do `CLAUDE.md`, e foi o `PLANO-10X` que
> ensinou por que ela existe: um plano com estado próprio envelhece e mente.

---

## PARTE 0 — A correção de rota, antes de tudo

**Duas coisas que os cinco consultores não sabiam, e que mudam o plano.** As
duas foram medidas nesta máquina em 28/08/2026, depois de os pareceres
chegarem.

### Fato 1 — O repositório é PÚBLICO, e a `main` já está protegida de verdade

O prompt da consulta afirmou que o repositório era privado e que a proteção
nativa de ramificação estava "fora de alcance por exigir plano pago". **Isso
estava errado.** A frase saiu do `RITOS.md` §2 peça 0, que ficou desatualizado
— o próprio `CLAUDE.md` já dizia o contrário desde 26/08.

Medido:

```
gh api repos/abundanciabr/sitesdoreino  →  "visibility": "public"
gh api repos/.../rulesets               →  "main protegida", enforcement: active
```

O conjunto de regras ativo na `main` impõe hoje: **PR obrigatório** (ninguém
empurra direto), **sem apagar a `main`**, **sem reescrever história**, e **dois
checks obrigatórios** (`muralhas` e `ci-celula-gate`). `bypass_actors` está
vazio — ninguém escapa, nem o dono.

Consequências, uma a uma:

- **A restrição mais dura da consulta não existe.** Três consultores
  desenharam mecanismos elaborados para substituir a proteção nativa que eu
  disse que ele não podia ter. Parte desse trabalho é desnecessária.
- **Minutos de CI deixam de ser um recurso escasso.** Opus, Opus-2 e Fable-2
  apontaram a franquia de 2.000 minutos como o teto real do paralelismo. Em
  repositório **público**, os executores padrão do Actions não consomem
  franquia. O teto que os três temiam não existe hoje.
- **Existe um buraco aberto, e ele é exatamente a Classe 6.** O parâmetro
  `strict_required_status_checks_policy` está **`false`**. Em português: um PR
  pode ser mergeado com o sinal verde de um teste que rodou contra uma `main`
  que já não existe. É a colisão semântica, com a porta escancarada — e o
  fechamento é **um parâmetro**, de graça, hoje.
- **E existe um risco que ninguém pediu para eu olhar:** repositório público
  significa que qualquer pessoa na internet lê o código, o livro de ocorrências
  e as decisões de negócio. O rastreamento de segredos vazados do GitHub —
  gratuito em repositório público — está **desligado**. Nenhum segredo real
  aparece na lista de arquivos versionados (só `.exemplo`), mas isso é uma
  amostragem, não uma auditoria.

### Fato 2 — O merge acontece no servidor, então metade das propostas do painel nasceria inerte

Opus-2 afirmou que driver de merge e `.gitattributes` só valem em merge
**local**, e que se o agente mergeia pela API do GitHub essas peças ficam
inertes. **Confiram: ele está certo, e a medição é direta.** `ci/mergear.py`
executa `gh pr merge <N> --<metodo>` — merge do lado do servidor.

Portanto: **as Direções A (driver customizado) e D (gancho pós-merge) estão
mortas**, não por serem ruins, mas por nunca chegarem a rodar. Fable-1 gastou o
parecer inteiro projetando a Direção A redesenhada; o trabalho não é
aproveitável como mecanismo — só como princípio (ver F1 no registro).

### O que essas duas descobertas ensinam sobre o problema em si

Isto não é ironia: **o erro que estragou parte da consulta foi a Classe 8** — a
lei desatualizada, lida com sinceridade, virando premissa falsa entregue a
cinco consultores. A classe que o projeto ainda não curou acabou de cobrar de
novo, dentro do próprio trabalho de curá-la. Nenhum teste pegaria: ler nunca dá
erro, e `RITOS.md` não tem guarda que confira se o que ele afirma sobre o
GitHub ainda é verdade.

Isso promove uma ideia do Fable-2, que na leitura inicial parecia secundária, à
peça mais importante do plano: **toda lei declara quem a faz valer, e o que não
tem quem faça valer aparece em vermelho** (B10 no registro).

---

## PARTE 1 — O veredito da consulta

### Os cinco concordam na tese central, e é uma discordância com você

Nenhum dos cinco aceitou a premissa da pergunta 1. Todos disseram, com palavras
diferentes, a mesma coisa: **liberdade total sem colisão é impossível — mas a
moeda com que você paga hoje é a errada.**

A formulação mais afiada é de Opus-2:

> "1 PR = 1 célula" cobra o pedágio na moeda errada. Ela restringe **largura**
> (quanto do sistema um robô pode tocar) para comprar uma coisa que exige
> **exclusividade** (quantos escritores mexem no mesmo recurso ao mesmo tempo).
> São eixos diferentes. Os recursos de fato exclusivos são poucos e
> enumeráveis: a `main`, a fila de publicação, a migração de cada banco, um
> punhado de arquivos gerados. A unidade certa de restrição é **recurso**, não
> célula.

E o argumento que encerra a discussão, do mesmo parecer: **a regra que mais
custa liberdade hoje não teria evitado o pior incidente já medido.** A Classe 6
(o serviço novo e a configuração no mesmo commit) passou por dentro de "1 PR =
1 célula" sem encostar nela.

Opus acrescentou a razão econômica, que é específica deste projeto e que eu não
tinha visto:

> Uma equipe humana divide território porque perder 3 horas de trabalho de uma
> pessoa é caro. Você não tem esse problema. Perder o trabalho de uma sessão
> custa 40 minutos de máquina. **Você está pagando um preço projetado para
> proteger trabalho caro, sobre trabalho barato.**

### A tese, em uma frase

> **Liberdade total no trabalho. Serialização absoluta na integração, feita por
> máquina. Restrição cirúrgica só sobre o punhado de recursos que existem numa
> cópia só.**

Isto é o oposto do desenho de hoje, que compra paz trancando o trabalho e
depois ainda serializa o merge à mão.

### Onde eles discordaram — e quem estava certo

Três divergências reais. Nas três, a checagem factual decidiu:

**1. `concurrency` do GitHub Actions serve como fila de merge?**
Opus disse que sim ("o GitHub enfileira e roda uma por vez"). **Opus-2 provou
que não**: quando um trabalho está pendente num grupo e chega um terceiro, **o
pendente anterior é cancelado**, não enfileirado. É "o mais novo vence", não
uma fila. Usar isso como fila de merge descartaria PRs em silêncio — o pior
tipo de falha que este projeto conhece.
**Veredito: Opus-2.** E Fable-2 é quem salva o desenho: a pista, ao terminar,
**chama a próxima** explicitamente, com um agendamento periódico como rede.
Sem essa peça, o desenho do Opus perderia trabalho.

**2. Driver de merge resolve os arquivos gerados?**
Fable-1 construiu o parecer inteiro em cima disso. Opus-2 disse que é inerte
com merge de servidor; Fable-2 concordou; Opus recomendou não usar por outro
motivo (peça que pode não estar instalada e não avisa).
**Veredito: os três contra um, e a medição confirma** — `mergear.py` usa `gh pr
merge`. Driver está fora.

**3. Reformatar o arquivo gerado é sintoma ou fundação?**
Fable-1 disse que reformatar é tratar sintoma. Opus, Opus-2 e Fable-2 dizem que
uma linha por registro é a fundação, porque o merge textual do Git resolve
inserções disjuntas corretamente **por construção**.
**Veredito: os três.** Com uma condição que o Fable-1 acertou sozinho e que os
outros não enfatizaram: o gerado precisa ter **um único escritor**, senão a
reformatação só adia.

### O que os cinco viram que eu não perguntei

Convergência espontânea em quatro pontos fora do escopo da consulta:

1. **O robô afrouxando o próprio teste é o risco número um.** Sem revisor
   humano, o teste é a única coisa entre o robô e a produção — e quem escreve o
   teste é o robô. Três dos cinco citaram sem combinar.
2. **O repositório dentro do OneDrive corrompe o Git.** Opus e Fable-2, de
   forma independente. Com cinco árvores de trabalho simultâneas, não é risco
   teórico.
3. **Não existe reversão automática quando a `main` fica vermelha.** Ninguém
   está olhando, por definição.
4. **Agente autônomo que mergeia e publica é superfície de ataque**, e merece
   consulta própria. Com o repositório público, isso subiu de prioridade.

---

## PARTE 2 — A super equipe de especialistas

Sete especialistas. Cada um é uma **sessão de agente com um mandato fechado**,
não um cargo permanente: nasce com o brief, entrega, registra no livro e morre.
A divisão respeita as leis que continuam valendo (worktree por agente,
orçamento de 15 arquivos, 1 PR = 1 célula **enquanto a cerca existir**).

A regência é da **sessão-maestro** (`RUNBOOK-LOTES.md`): é ela que fala com o
mantenedor, e é a única que abre pergunta estruturada. Especialista reporta
para a maestro, em texto.

### 1. O Porteiro — governança da `main`

**Mandato:** o conjunto de regras do GitHub e tudo que se resolve com
configuração, não com código. Ligar a política estrita de checks, ligar o
rastreamento de segredos, revisar bypass, corrigir a lei desatualizada que
originou o erro da Parte 0.
**Fronteira:** não escreve workflow, não escreve Python. Se a resposta é
código, o trabalho é de outro.
**Toca:** `.github/`, `RITOS.md` — **caminhos CODEOWNERS, exige mandato
nominal do mantenedor.**
**Entrega:** a Classe 6 fechada por parâmetro no mesmo dia.

### 2. O Arauto — o mapa fresco

**Mandato:** matar a Classe 8. Um script de abertura de sessão, versionado, que
cria o worktree a partir de `origin/main` (nunca do espelho), **recusa começar
se não falar com o GitHub**, e imprime o boletim: PRs abertos com os arquivos
de cada um, reservas vivas, o que pousou nas últimas 24 horas, e leis novas
desde a base.
**Fronteira:** não decide nada sobre merge nem sobre reservas — só informa, e
falha alto quando não consegue informar.
**Toca:** `ci/`, `.claude/`.
**Entrega:** nenhuma sessão volta a nascer com mapa velho, e o espelho para de
envelhecer como efeito colateral.

### 3. O Almoxarife — reservas e numeração

**Mandato:** a cura de classe da Classe 3 e o barateamento da Classe 5. Um
script único de reserva por **referência atômica no servidor** (quem chega
primeiro cria; o segundo recebe recusa do próprio GitHub), com prazo escrito
dentro e renovação a cada push. Um script único `numero <superfície>` que
substitui os validadores escritos um a um. Um zelador agendado que rotula
órfãos — **sem apagar nada**.
**Fronteira:** não tranca área do sistema; tranca **intenção nomeada** e
**recurso de cópia única**. Trancar área é o desenho que estamos derrubando.
**Toca:** `ci/`, `.github/workflows/`.
**Entrega:** toda superfície nova ganha trava de graça, em vez de reinventar a
sua.

### 4. O Ourives — o painel de escritor único

**Mandato:** a Classe 4 no painel. Tirar do `painel.html` tudo que muda porque
nasceu um registro; um registro por linha no livro do mês; a geração passa a
ter **um escritor só** — a integração — e o robô é mecanicamente impedido de
commitar arquivo gerado.
**Fronteira:** não muda o que o painel mostra. É obra de encanamento; se a
tela mudar, ele saiu do mandato.
**Toca:** `painel/`, `ci/`, `.github/workflows/`.
**Entrega:** a colisão diária de hoje deixa de existir por construção.

### 5. O Controlador de Pouso — a pista

**Mandato:** a peça central. Um fluxo que recebe o pedido de pouso, funde com a
`main` **de agora**, testa a junção, publica as células afetadas em ordem de
dependência com verificação de saúde, e reverte sozinho se qualquer passo
falhar. Encadeia o próximo pouso ao terminar (porque o grupo de exclusividade
**não é fila**), com agendamento periódico como rede.
**Fronteira:** não muda regra de escopo nem de contrato — só integra e publica.
**Toca:** `.github/workflows/`, `ci/`, `infra/` — **CODEOWNERS, exige
mandato.**
**Entrega:** a Classe 6 fechada de verdade, a Classe 7 com dono, e o merge
serial deixa de depender de sessão viva.

### 6. O Cartógrafo — o mapa das células e a queda da cerca

**Mandato:** o que substitui "1 PR = 1 célula". Um `celulas.yml` versionado
(caminho → célula, e quem consome o contrato de quem); o CI passa a **derivar
do diff** quais suítes rodar, em vez de recusar por largura; comparação de
contrato que aceita adição e recusa remoção sem autorização; `Depende-de: #N`
cobrado por máquina. **Só depois disso a cerca cai.**
**Fronteira:** não derruba a cerca antes de as três peças estarem verdes e
medidas. A cerca é muleta — mas muleta se tira depois que a perna anda.
**Toca:** `ci/`, `.github/`, `contracts/` — **CODEOWNERS, exige mandato.**
**Entrega:** a liberdade que o mantenedor pediu, com prova em vez de bloqueio.

### 7. O Fiscal — o guarda dos guardas

**Mandato:** o risco que os cinco apontaram e ninguém perguntou. Catraca de
cobertura por célula (só sobe); recusa de PR que apague, pule ou afrouxe teste
sem autorização; reversão automática quando a `main` fica vermelha; o arquivo
de métricas (espera na fila, taxa de reprovação na junção, retrabalho) que
transforma "está apodrecendo?" em número; e o contador de **leis sem
mecanismo** — quantas regras deste projeto ninguém faz valer.
**Fronteira:** não relaxa nada para destravar ninguém. Se o Fiscal virar
negociável, ele deixa de existir.
**Toca:** `ci/`, `.github/workflows/`, `painel/`.
**Entrega:** o projeto passa a medir a própria doença-mãe em vez de torcer.

---

## PARTE 3 — O plano mestre, em ondas

Cada onda é uma leva de PRs. A ordem é por **dependência e por sangramento**,
não por calendário. Onda 0 é hoje; as outras são tarefas de robô.

### Onda 0 — o que já dá para fazer sem escrever código (Porteiro)

| # | O quê | Mata | Custo |
|---|---|---|---|
| 0.1 | Ligar `strict_required_status_checks_policy` no conjunto de regras | **Classe 6, hoje** | um parâmetro |
| 0.2 | Ligar rastreamento de segredos + proteção de push (grátis em repo público) | risco novo | um parâmetro |
| 0.3 | Corrigir `RITOS.md` §2 peça 0 — a frase que diz que a proteção é inalcançável | a causa do erro da Parte 0 | 1 linha |
| 0.4 | Decidir o que fazer com o repositório público e com o OneDrive | 2 riscos reais | decisão do dono |

**Aviso honesto sobre 0.1:** com a política estrita ligada, todo merge
invalida o verde dos outros PRs abertos, que precisam se atualizar e rodar de
novo. Com 5 frentes isso gera retrabalho visível — foi a "fila de rebase
infinita" que o Gemini previu. **É a troca certa mesmo assim**, porque hoje a
alternativa é quebrar em silêncio, e porque a Onda 4 remove o retrabalho. É
reversível com o mesmo parâmetro.

### Onda 1 — o mapa fresco (Arauto)

A Classe 8 é a mais grave sem cura, é a que acabou de cobrar dentro deste
próprio trabalho, e é a mais barata de fechar. Vem primeiro por isso.

Um script de abertura que faz `git fetch`, cria o worktree de `origin/main`,
atualiza o espelho como efeito colateral, e imprime o boletim. **Sem contato
com o GitHub, ele recusa começar** — é assim que se faz ler dar erro.

### Onda 2 — o cofre (Almoxarife)

Reserva por referência atômica; numeração alocada pelo servidor; PR em rascunho
no minuto 1 como anúncio; zelador que rotula órfãos. Fecha a Classe 3 por
classe e encurta a Classe 5 de 40 minutos para 30 segundos.

### Onda 3 — o painel de escritor único (Ourives)

Esvaziar o `painel.html`; um registro por linha; geração com escritor único;
gancho e CI recusando gerado dentro de PR. Fecha a Classe 4 e paga a dor
diária.

### Onda 4 — a pista de pouso (Controlador)

A peça central. Junção testada, publicação ordenada, reversão automática,
encadeamento. Fecha a Classe 6 de verdade e dá dono à Classe 7. É aqui que o
retrabalho da Onda 0.1 desaparece.

### Onda 5 — a queda da cerca (Cartógrafo)

`celulas.yml`, escopo derivado do diff, contrato aditivo, dependência
declarada. **E só então remover "1 PR = 1 célula"** — a liberdade que originou
tudo isto. O orçamento de 15 arquivos fica: é barato e continua útil.

### Onda 6 — o guarda dos guardas (Fiscal)

Catraca de testes, reversão da `main` vermelha, métricas, contador de leis sem
mecanismo. Sem esta onda, o resto apodrece sem ninguém perceber.

### O que morre em cada onda

| Classe | Estado hoje | Morre em |
|---|---|---|
| 1 — mesma pasta | curada | — |
| 2 — pilha de stash global | só convenção escrita | Onda 1 (interceptador) |
| 3 — corrida por número | duas curas separadas | Onda 2 (cura de classe) |
| 4 — arquivo compartilhado | desenho | Onda 3 |
| 5 — trabalho duplicado | **nada** | Onda 2 (encurtada, não curada) |
| 6 — colisão semântica | **nada** | Onda 0.1 (parcial) → Onda 4 |
| 7 — recursos únicos | **nada** | Onda 4 |
| 8 — mapa velho | **nada** | Onda 1 |

---

## PARTE 4 — Registro auditável das recomendações

**Este é o pedaço que a auditoria externa vai usar.** Cada recomendação
distinta dos cinco pareceres, com veredito e motivo. Vocabulário:

- **ACEITA** — entra como recomendado.
- **ACEITA COM MUDANÇA** — a ideia entra, o desenho muda (motivo escrito).
- **RECUSADA** — não entra (motivo escrito).
- **PREJUDICADA** — um fato medido depois derrubou a premissa.
- **JÁ EXISTIA** — o projeto já tinha.
- **DO DONO** — decisão que só o mantenedor toma.

### Gemini

| # | Recomendação | Veredito | Onda | Motivo |
|---|---|---|---|---|
| G1 | Robô nunca commita gerado; a integração gera | ACEITA COM MUDANÇA | 3 | A ideia é certa. O desenho usa `.git/info/exclude`, que **não é versionado** — some num clone novo, em silêncio. Vira gancho versionado + recusa no CI |
| G2 | Concorrência otimista; catraca no merge | ACEITA | 4 | É a tese central |
| G3 | Testes em matriz substituem a cerca | ACEITA | 5 | Igual ao Opus-2 e Fable-2 |
| G4 | Árbitro = rótulo no PR + pré-voo no PC | RECUSADA | — | Rótulo **não é atômico** (ler-e-escrever tem janela de corrida). Referência atômica ganha |
| G5 | Action que reprova PR com base velha | PREJUDICADA | 0 | Não precisa escrever nada: é um parâmetro nativo, grátis, desligado hoje |
| G6 | `radar.py` + pré-commit exigindo mapa recente | ACEITA COM MUDANÇA | 1 | Nasce na criação da árvore, não no commit — no commit já é tarde |
| G7 | Ceifador fecha PR e **apaga** o ramo em 3h | RECUSADA em parte | 2 | Rotular órfão sim; apagar não. Neste projeto nada se apaga (Fable-2 tem razão) |
| G8 | Teto em função da duração do CI | ACEITA | 6 | Medir, não chutar |
| G9 | Tirar do robô o poder de mergear | DO DONO | 4 | Contraria a Lei 4. E metade já é fato: o push direto **já** está bloqueado |

### Opus

| # | Recomendação | Veredito | Onda | Motivo |
|---|---|---|---|---|
| O1 | "Detectar e refazer" em vez de "dividir território"; trabalho de robô é barato | ACEITA | tese | A melhor justificativa econômica das cinco |
| O2 | Fila com `concurrency`, testando a junção | ACEITA COM MUDANÇA | 4 | O mecanismo está errado: `concurrency` **não é fila** (ver P5). Entra com o encadeamento do B3 |
| O3 | `pre-push` recusando a `main`; interceptador de `git` no PATH | ACEITA em parte | 0/1 | `pre-push` virou redundante (o conjunto de regras já recusa) — fica como cerca rápida. O interceptador de `stash` entra: cura a Classe 2 |
| O4 | "O versionado confere se o não-versionado está instalado" | ACEITA | 1 | Princípio forte. Vira lei, não item |
| O5 | Reserva por `refs/reservas` | ACEITA | 2 | Convergiu com P6 e B4 |
| O6 | Publicar o estado inteiro em ordem de dependência | ACEITA | 4 | Mata o caso pior da Classe 6 na raiz |
| O7 | Expandir-e-contrair obrigatório em contrato | ACEITA | 5 | Convergiu com P4 e B7 |
| O8 | Carimbo de frescor recusado pela fila | ACEITA em parte | 0/4 | Metade vira o parâmetro nativo da Onda 0 |
| O9 | Boletim de 24 horas | ACEITA | 1 | Convergiu com P8 e B-início |
| O10 | Classe 5 não tem cura mecânica; encurtar a descoberta | ACEITA | 2 | Honestidade que os outros não tiveram |
| O11 | Reprovar PR que reduza testes ou adicione "pular" | ACEITA | 6 | Convergiu com B15 |
| O12 | Minutos de CI são recurso escasso; rodar em Linux | PREJUDICADA | — | Repositório **público**: executor padrão não consome franquia. O teto temido não existe |
| O13 | Repositório dentro do OneDrive corrompe | ACEITA | 0.4 | Confirmado: o repositório está em `OneDrive\Documentos\` |
| O14 | O fluxo do PR se auto-neutraliza | ACEITA | 4 | O portão de verdade tem de disparar na `main` |
| O15 | Cópia de segurança antes de migração | ACEITA | 4 | — |
| O16 | Credencial do banco só dentro da publicação | ACEITA | 4 | "Não roda porque não tem a senha", não porque leu que não deve |
| O17 | Abandonar número sequencial; id derivado | ACEITA COM MUDANÇA | 2 | O dono **lê** "registro 019" — a sequência é interface humana. Mantém-se o número, alocado atomicamente (B5) |
| O18 | Esvaziar o `painel.html`; uma linha por registro | ACEITA | 3 | Convergiu com P15 e B |
| O19 | Não fazer driver de merge nem gancho pós-merge | ACEITA | — | **Confirmado por medição**: o merge é do servidor, eles nunca rodariam |
| O20 | Não deixar o CI commitar no ramo do PR | ACEITA | 3 | Vale para o ramo. Commitar na `main` é outra coisa, e essa entra |

### Opus-2

| # | Recomendação | Veredito | Onda | Motivo |
|---|---|---|---|---|
| P1 | A moeda certa é **recurso**, não célula | ACEITA | tese | O refinamento mais preciso da rodada |
| P2 | A cerca não teria evitado a Classe 6 | ACEITA | 5 | O argumento que encerra a defesa da cerca |
| P3 | Escopo derivado do diff (`celulas.yml`) | ACEITA | 5 | — |
| P4 | Comparação de compatibilidade de contrato | ACEITA | 5 | — |
| P5 | **`concurrency` não é fila: cancela o pendente anterior** | ACEITA | 4 | **A correção factual mais valiosa da rodada.** Derrubou o desenho do O2 |
| P6 | Reserva por referência via API | ACEITA | 2 | — |
| P7 | Retestar contra a `main` real (padrão Tide/Prow) | ACEITA | 4 | — |
| P8 | Briefing na criação da árvore, falhando alto | ACEITA | 1 | — |
| P9 | Aviso: gancho de início de sessão trava no Windows | **RECUSADA por medição** | — | Este projeto **roda** um gancho de início de sessão hoje (a muralha), e ele funciona — provado na abertura desta sessão. O aviso não se aplica |
| P10 | Limpeza preguiçosa embutida na aquisição | ACEITA | 2 | Melhor que varredura: não depende de vigia |
| P11 | Reverter sozinho quando a `main` fica vermelha | ACEITA | 6 | — |
| P12 | Agente autônomo é superfície de ataque; consulta própria | ACEITA como pendência | — | Sobe de prioridade: o repositório é público |
| P13 | "Vocês estão voando sem instrumento" | ACEITA | 6 | Pré-requisito para responder "apodreceu?" com número |
| P14 | Driver não roda em merge de servidor | ACEITA | — | **Confirmado por medição** |
| P15 | Um registro por linha é a fundação | ACEITA | 3 | — |

### Fable-1 (parecer sobre o painel)

| # | Recomendação | Veredito | Onda | Motivo |
|---|---|---|---|---|
| F1 | **Lei: fonte multiescritor + materialização de escritor único + validação independente** | ACEITA como lei | 3 | A formulação mais reaproveitável da rodada. Vale para índices, catálogos, resumos e tudo que vier |
| F2 | Driver de merge redesenhado como peça central | PREJUDICADA | — | Merge é do servidor. Nunca rodaria |
| F3 | Tirar do `painel.html` o que muda por registro | ACEITA | 3 | Convergiu com O18 |
| F4 | Não transformar divergência entre caches em conflito de domínio | ACEITA | 3 | Princípio correto |
| F5 | Duas provas diferentes: verificador semântico **e** regeneração byte a byte | ACEITA | 3 | As duas medem propriedades diferentes |
| F6 | Não reformatar o arquivo primeiro — é sintoma | RECUSADA | 3 | Três consultores contra. Com o `painel.html` esvaziado, a reformatação é fundação |

### Fable-2

| # | Recomendação | Veredito | Onda | Motivo |
|---|---|---|---|---|
| B1 | Toda a segurança na integração — a pista de pouso | ACEITA | 4 | O desenho mais completo das cinco |
| B2 | PR em rascunho no minuto 1 como anúncio | ACEITA | 2 | Ataca a Classe 5 pelo lado barato |
| B3 | **Encadeamento do pouso + agendamento de rede** | ACEITA | 4 | É a peça que salva o desenho do O2 do problema achado em P5 |
| B4 | Reserva com prazo dentro e renovação no push | ACEITA | 2 | Push como prova de vida, sem disciplina |
| B5 | Script `numero <superfície>` genérico | ACEITA | 2 | A cura de classe da Classe 3 |
| B6 | `celulas.yml` + varredor de referência não declarada | ACEITA | 5 | O varredor é o que impede o mapa de mentir |
| B7 | Contrato aditivo + `Depende-de: #N` | ACEITA | 5 | — |
| B8 | Nunca apagar ramo nem PR; rotular órfão | ACEITA | 2 | Bate com a cultura do projeto; derruba G7 |
| B9 | Conta-máquina + fork como jaula de verdade | ADIADA | — | O conjunto de regras já bloqueia o push direto. E o repositório é público, o que muda as premissas. Reavaliar depois da Onda 4 |
| B10 | **Cada lei declara quem a faz valer; leis sem mecanismo aparecem em vermelho** | ACEITA | 6 | A melhor ideia estrutural da rodada: mede a doença-mãe do projeto. A Parte 0 é a prova de que faltava |
| B11 | Revisor-robô no pouso, com contexto fresco | ACEITA | 6 | O substituto mais próximo do revisor humano ausente |
| B12 | OneDrive e Git não convivem | ACEITA | 0.4 | Segunda voz independente sobre o mesmo risco |
| B13 | Verificador de maiúsculas e fim de linha | ACEITA | 6 | Cobrou nesta própria sessão: um arquivo divergindo só no fim de linha travou a atualização do espelho (`armadilhas/152`) |
| B14 | Medir perguntas por frente — o dono é recurso único | ACEITA | 6 | — |
| B15 | Catraca de cobertura por célula | ACEITA | 6 | Convergiu com O11 |

### Placar

| Veredito | Quantidade |
|---|---|
| ACEITA | 38 |
| ACEITA COM MUDANÇA | 6 |
| RECUSADA (ou em parte) | 5 |
| PREJUDICADA por fato medido | 4 |
| DO DONO | 1 |
| ADIADA | 2 |

---

## PARTE 5 — O protocolo da auditoria externa

Quando as ondas andarem, cada consultor volta e confere **o próprio parecer**.
Para a auditoria ser honesta, ela precisa de três coisas que este documento já
entrega:

1. **A tabela da Parte 4** — cada recomendação com veredito e motivo escrito
   ANTES de qualquer implementação. Isso impede o projeto de escrever a
   justificativa depois de decidir.
2. **A prova de fora** — o auditor não pergunta ao projeto se algo foi feito.
   Ele confere no GitHub: o PR existe, está mergeado, o teste-guarda existe e
   fica vermelho quando o mecanismo é sabotado.
3. **A pergunta certa para cada linha:** *foi aceita e implementada? aceita e
   ainda não? recusada — o motivo se sustenta? prejudicada — o fato medido é
   mesmo verdade?*

O prompt da auditoria nasce quando a primeira onda fechar, na mesma pasta da
rodada. **A recusa mais importante de auditar é a P9**, porque ali o projeto
contradiz um consultor com base numa medição própria — exatamente o tipo de
afirmação que precisa de testemunha de fora.

---

## PARTE 6 — O que espera decisão do mantenedor

Quatro coisas que este plano não pode decidir sozinho. Elas vão para o livro
como pedido, e para ele como pergunta estruturada.

1. **O repositório é público.** Qualquer pessoa lê o código, o livro de
   ocorrências e as decisões de negócio. Isso pode ser deliberado — e traz
   vantagens reais que o plano já aproveitou (regras de proteção e CI de graça).
   Mas precisa ser uma escolha, não uma descoberta.
2. **O repositório mora dentro do OneDrive**, e dois consultores independentes
   apontaram isso como causa de corrupção silenciosa do Git com várias sessões
   simultâneas.
3. **O merge sai da mão do robô e passa para a pista?** Contraria a Lei 4, que
   foi decisão dele em 22/08. O ganho: o robô deixa de poder quebrar a `main`.
   O que **não** muda: ele continua sem esperar por humano — quem mergeia é
   máquina, não o dono.
4. **Mandato para os caminhos protegidos.** Ondas 0, 4 e 5 tocam `.github/`,
   `ci/`, `infra/`, `contracts/` e arquivos-lei da raiz. A Lei 4 exige mandato
   nominal dele.

---

## Apêndice — o que continua valendo

Nada aqui revoga o que já funciona. Continuam de pé, sem discussão: worktree
por agente, muralha da pasta compartilhada, orçamento de 15 arquivos, dono
obrigatório nos caminhos sensíveis, evidência vermelho→verde, um arquivo por
entrada, o livro de ocorrências e a lei anti-duplicação.

A cerca "1 PR = 1 célula" é a **única** trava que este plano derruba — e só na
Onda 5, depois de as três peças que a substituem estarem verdes e medidas.
