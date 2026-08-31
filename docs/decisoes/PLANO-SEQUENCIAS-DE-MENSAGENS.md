---
publico-para-ia: true
---

# PLANO — as sequências de mensagens para o aluno

> **AS QUATRO DECISÕES DO §8 FORAM RESPONDIDAS PELO MANTENEDOR EM 30/08/2026**,
> na mesma sessão que gerou este plano. Este documento foi corrigido para
> obedecê-las — **o §4.1 diz hoje o CONTRÁRIO do que dizia quando foi escrito**,
> porque a recomendação era célula nova e ele escolheu outra coisa. Quem for
> construir segue o §8, não a recomendação original.
>
> Uma das respostas dele é um fato de negócio que atravessa o projeto inteiro:
> **a escola só tem alunos maiores de 18 anos, e não terá menores.** Isso diverge
> do `DECISAO-gamificacao.md` §9, promulgado no MESMO dia — a divergência está
> registrada no livro e é decisão dele, não deste plano (§8.5).

> **Data:** 30/08/2026 · **Estado:** decidido no §8, a construir pela escada do §7
> **Pedido do mantenedor, nas palavras dele:**
>
> > *"Quero criar algumas sequências de mensagens automáticas para serem enviadas
> > para os alunos, por exemplo, após o cadastro mandar uma mensagem de
> > boas-vindas, após outros eventos disparar mensagens de incentivo aos alunos,
> > e assim por diante. Qual é a melhor maneira de fazer isso?"*

> **O que este documento NÃO é:** autorização para construir. O §8 lista quatro
> decisões que são só do mantenedor, e uma delas — ligar o e-mail — reabre uma
> porta que o próprio projeto fechou (`docs/notificacoes/PLANO-MESTRE.md` §Fase 7:
> *"a porta segue fechada, e nenhuma sessão futura deve reabri-la por conta
> própria"*). Só ele reabre. Enquanto não reabrir, o §7 tem uma escada inteira
> que anda sem tocar nessa porta.

> **Este documento não guarda estado.** O que já foi construído se lê no livro
> (`painel/registros/`), nunca aqui — mesma regra do `DECISAO-gamificacao.md` §11.

---

## §1 — O que JÁ existe (e é mais do que parece)

A pergunta *"qual é a melhor maneira de fazer isso?"* tem uma resposta curta:
**aproveitando o que a plataforma já tem, que é quase tudo.** O inventário, com
os arquivos, para quem for construir não precisar procurar:

| Peça | Onde | Estado |
|---|---|---|
| **Caixa de avisos dentro do site** (o sininho) | `services/notificacoes/` | **No ar.** Consome `notificacao.devida.v1`, contador de não-lidos em O(1), arquivamento, porta de consulta com índices medidos por `EXPLAIN ANALYZE`. |
| **Célula de envio externo** (e-mail/WhatsApp) | `services/mensageria/` | **Existe, mas não envia.** `apps/eventos/tasks.py` é literalmente `"""Stub: loga o envio."""` — nenhum provedor real, nenhum e-mail já saiu daqui. |
| **Esqueleto de eventos** (outbox → relay → consumidor) | `alunos`, `checkout`, `pagamentos`, `quiz`, `sugestoes` | **No ar em 5 células.** Receitas R4 (consumo) e R8 (task com retry). Idempotência por `event_id`, reentrega do PEL, fila morta. |
| **A ficha do aluno** (com contato) | `services/alunos/apps/matriculas/models.py` | **No ar.** `email`, `name`, `whatsapp`, `turma`, `status`, `comprou_em`, `enrolled_at`. |
| **O id de plataforma da pessoa** | `services/identidade/` | **No ar.** É o único lugar onde o e-mail do site vive; traduz e-mail ↔ id opaco. |
| **Trilha de eventos por pessoa** | `services/leads/` | **No ar.** Timeline, tags, consentimentos, UTM. |
| **Gamificação** (níveis, medalhas, marcos) | `services/gamificacao/` | **No ar**, e os quatro assuntos de celebração já estão congelados no contrato (`notificacao.devida.v1.json`) — só ainda **não são publicados**. |
| **Fórum** | `services/forum/` | **No ar**, e já publica `forum.topico-criado`, `forum.mensagem-criada`, `forum.resposta-aceita`. |

**Conclusão do inventário:** não falta infraestrutura de mensagem. Falta **um
motor que entenda TEMPO** — e é aí que mora a diferença entre o que existe e o
que foi pedido.

---

## §2 — O buraco, medido: hoje a plataforma só sabe reagir, não sabe esperar

Tudo que a plataforma envia hoje é **reação imediata a um fato**: aconteceu X,
manda a carta, acabou. Uma *sequência* é outra coisa:

> *"No dia do cadastro, boas-vindas. Dois dias depois, **se a pessoa ainda não
> entrou em nenhuma aula**, um empurrãozinho. Uma semana depois, **se ela ainda
> não postou no fórum**, um convite."*

Isso exige três coisas que **não existem em lugar nenhum do projeto**:

1. **Esperar.** Nada agenda "faça isto daqui a 2 dias". As `crontab` do Huey que
   existem hoje são varredores de outbox (`relay_outbox`), não agendadores de
   passo.
2. **Desistir na hora certa.** O passo 2 só faz sentido *se a condição ainda for
   verdadeira*. Uma sequência que não sabe cancelar o próprio passo manda
   "sentimos sua falta" para quem voltou ontem — e essa é a falha que faz o aluno
   desligar tudo.
3. **Perceber a ausência.** "Sumiu há 5 dias" **não é um evento** — é a falta
   dele. Nenhuma célula mede isso; só uma varredura periódica consegue.

E há quatro buracos menores, todos concretos:

- **O cadastro é mudo.** `services/identidade/` não tem `apps/eventos`, não tem
  outbox e não publica **nada**. O gatilho mais óbvio do pedido — *"após o
  cadastro"* — hoje não chega a lugar nenhum.
- **A gamificação é muda.** Os quatro assuntos existem no contrato desde a Sessão
  B (30/08/2026), mas a célula ainda não os emite.
- **O envio externo é um `logger.info`.** Ver §1. Ligar e-mail de verdade é
  construir o envio, não plugar um fio.
- **Não há preferência nem opt-out.** Nem "silenciar", nem "não quero e-mail".

---

## §3 — As oito leis que este desenho não pode violar

Não são opinião: cada uma já é lei escrita neste repositório, com mecanismo de CI
atrás. Quem for construir precisa das oito na cabeça **antes** de desenhar tabela.

1. **Aviso é DADO, nunca frase pronta.** A escola serve três idiomas. Gravar
   *"Você chegou ao nível 7"* congela o idioma de quem gravou. Grava-se `assunto`
   + `parametros`; **a frase nasce na leitura.**
   → `contracts/eventos/notificacao.devida.v1.json`, `DECISAO-notificacoes.md` §5.1.
2. **Evento nunca carrega e-mail, nome ou telefone.** Só id opaco de plataforma.
   Quem precisa falar com a pessoa **pergunta** à `identidade`/`alunos`.
   → `DECISAO-EVO-01` §3, e `additionalProperties: false` em todo contrato.
3. **O leque é feito na ORIGEM.** Uma carta = uma pessoa. A caixa central só
   escreve o que chega; ela é burra de propósito, e é isso que a mantém barata.
   → Rito de Contrato de 26/08/2026.
4. **Só boa notícia vira carta. No máximo 1 por dia, nunca depois das 20h, nunca
   em horário escolar.** Perder XP, regredir na sequência ou ter marca estornada
   **não gera aviso nenhum**.
   → lei da célula `gamificacao`, escrita dentro do contrato da carta.
5. **Menores obrigam.** Modo Júnior abaixo de 13 anos é trava de sistema, não
   escolha. Nada de mascote que cobra, notificação de culpa, corações/vidas ou
   aposta de sequência — **explicitamente vetados**.
   → `DECISAO-gamificacao.md` §8 e §9.
   **⚠ EM DIVERGÊNCIA (30/08/2026):** o mantenedor declarou que *"só temos alunos
   acima de 18 anos, não temos e nem teremos alunos menores de idade"* — a metade
   desta lei que fala de IDADE ficou sem sujeito. Este plano **não constrói trava
   de menor** (§8.4) e **não revoga o §9**, que continua escrito e é lei até ele
   decidir (§8.5). O veto a mascote-que-cobra e notificação-de-culpa **continua
   valendo integralmente** — aquilo nunca foi sobre idade.
6. **O dia é o dia de São Paulo.** `America/Sao_Paulo`, sempre. Com o fuso do
   Django cru, o esforço das 22h cai no dia errado e nada acusa.
   → invariante da `gamificacao`, e `test_fuso_horario.py` em toda célula.
7. **Nenhum fato mora em dois lugares.** Superfície nova de acompanhamento se
   **calcula**; lista paralela é proibida.
   → `CLAUDE.md`, lei anti-duplicação.
8. **Regra de negócio ajustável é DADO, não código.** No `DECISAO-gamificacao.md`
   §10, *"ajustar a economia passar a exigir PR de código"* é **critério de
   morte** da célula. O mesmo vale aqui, e com mais força: o mantenedor vai
   querer trocar o texto de uma mensagem numa terça à noite.

---

## §4 — O desenho: o motor mora DENTRO da `mensageria` (decisão de 30/08/2026)

```
  UM FATO ACONTECE                      A MENSAGERIA                  ONDE CHEGA
 ───────────────────      ─────────────────────────────────      ──────────────────
  identidade  ──┐          ┌───────────────────────────┐       ┌──▶ notificacoes
  alunos      ──┤          │  apps/jornadas  (NOVO)    │       │    (o sininho — no ar)
  gamificacao ──┼──▶ eventos│  tempo · condição · régua │──────▶┤
  forum       ──┤          ├───────────────────────────┤       │
  quiz        ──┘          │  apps/eventos  (JÁ EXISTE)│       └──▶ e-mail / WhatsApp
                           │  envio · retry · registro │            (hoje é stub)
                           └───────────────────────────┘
```

### 4.1 A escolha do mantenedor, e o que ela obriga

**Este plano recomendava uma célula nova (`jornadas`). O mantenedor escolheu o
contrário: o motor entra dentro da `mensageria`.** Decisão dele em 30/08/2026,
com os custos de cada lado na mesa. É a decisão que vale; o que segue é como
executá-la sem quebrar nada.

**O problema real que a escolha traz, e a solução:** a trava de idempotência da
`mensageria` é `unique(order_id, tipo, canal)` em `EnvioRegistrado` — é ela que
hoje impede um cliente de receber dois e-mails do mesmo pagamento. Uma sequência
de aluno **não tem `order_id`**, e o mesmo `tipo` se repete de propósito em
passos diferentes.

**Não se altera essa constraint.** O motor escreve `order_id` sintético:

```
order_id = "jornada:<inscricao_id>:<passo_id>"
```

`order_id` de pagamento é um id real vindo do checkout e **nunca colide com uma
chave prefixada** — a trava passa a proteger as duas coisas sem uma linha de
migração e sem risco para o fluxo de dinheiro. O motor tem, além dela, as duas
travas próprias do §5.

**As três coisas que a escolha obriga, e que não se pode esquecer:**

1. **Emendar `constituicoes/AGENTS.mensageria.md`.** A missão hoje diz
   *"comunicação transacional… disparados por eventos"* — um fato, um envio,
   agora. Sequência que espera dois dias **não é transacional**. Sem a emenda, a
   cerca do CI e o próximo agente leem a missão e recusam o trabalho como fora de
   escopo. Isto é PR próprio, e é o degrau 0 da escada.
2. **App separado, banco compartilhado.** `apps/jornadas/` é um app novo dentro da
   célula. Ele **lê e escreve as próprias tabelas** e toca `apps/eventos/` num
   ponto só: criando a linha de `EnvioRegistrado`. Nada além disso.
3. **O orçamento de 15 arquivos por PR fica apertado** — a célula já tem ~30
   arquivos. Cada degrau do §7 precisa ser fatiado com isso em mente.

**Quem faz o quê, depois da decisão:**

| Onde | Responsabilidade | Uma frase |
|---|---|---|
| origem (`identidade`, `alunos`, `gamificacao`, `forum`…) | **afirmar o fato** | "isto aconteceu" |
| `mensageria/apps/jornadas` | **decidir** | "quem recebe o quê, quando, e se ainda faz sentido" |
| `mensageria/apps/eventos` | **entregar fora do site** | "saiu por e-mail/WhatsApp" |
| `notificacoes` | **guardar e mostrar dentro do site** | "está no seu sininho" |

### 4.2 A sequência é DADO, não código

Uma jornada é **linha de tabela**, editável em `/admin/`, versionada, **nunca
retroativa** (mudar a jornada não reescreve quem já está no meio dela). Pela lei
8 do §3, e por um motivo prático: se trocar o texto de uma mensagem exigir um PR,
ninguém troca, e as mensagens envelhecem no ar.

**O que continua sendo código:** as *condições* que um passo pode consultar
("já entrou em alguma aula?", "já postou no fórum?"). Cada condição nova é um PR
pequeno que registra uma função num dicionário — **nunca uma linguagem de
fórmula dentro do banco.** Uma DSL aqui é o mesmo critério de morte da
`gamificacao`, e é como este motor viraria um monstro em seis meses.

### 4.3 A pergunta difícil: e-mail é frase pronta, e a lei 1 proíbe frase pronta

Não é contradição — é uma distinção que o plano precisa deixar explícita, porque
quem construir vai tropeçar nela:

> **A lei 1 proíbe GRAVAR a frase. O e-mail não grava: ele é a leitura.**

O aviso do sininho é gravado hoje e lido daqui a três meses, possivelmente em
outro idioma — por isso guarda dado. O e-mail é **renderizado no instante do
envio** e sai da plataforma; aquele instante *é* o momento da leitura. Então:

- `apps/jornadas` decide o passo e grava `assunto` + `parametros` + `canal` —
  **sem uma palavra de texto pronta**.
- Na hora do envio, `apps/eventos` **pergunta à `identidade`** quem é (e-mail +
  idioma), renderiza o template naquele idioma **naquela hora**, e envia.
- O que fica gravado no `EnvioRegistrado` é o texto que **realmente saiu** — isso
  é registro de auditoria, não conteúdo a ser reexibido, e é justamente o que se
  quer guardar quando alguém perguntar "o que vocês me mandaram?".

Consequência mecânica: `mensageria` passa a ter `consome: [identidade]` no
`celulas.yml`. É exatamente o ponto que o `PLANO-MESTRE.md` do sininho já tinha
antecipado — *"a `mensageria` precisa de um destinatário, e o e-mail vive numa
linha só"*.

**Um ganho real da decisão de 30/08:** com o motor dentro da própria célula, o
caminho do e-mail **não precisa de evento nenhum** — o app novo chama a máquina
de envio que já existe, na mesma transação. O contrato `mensagem.devida.v1`, que
a versão anterior deste plano previa, **deixa de ser necessário**: é um Rito de
Contrato a menos e um transporte a menos para dar errado. O sininho continua
recebendo por evento (`notificacao.devida.v1`, que já existe), porque
`notificacoes` é outra célula e ninguém escreve no banco alheio (Lei 3).

---

## §5 — O modelo de dados de `mensageria/apps/jornadas`

Quatro tabelas **novas, no banco que a célula já tem** (`mensageria_db`) — nenhuma
alteração nas duas que já existem. Nem uma a mais — e as travas em `CheckConstraint`/
`UniqueConstraint`, no banco, nunca só em `save()` (`armadilhas/023`: um
`queryset.update()` fura guarda escrita em Python).

**`Jornada`** — a sequência em si.
`site_id` · `slug` · `gatilho` (o evento que inscreve) · `ativa` · `versao` ·
`criada_em`. Uma jornada por assunto de vida do aluno.

**`Passo`** — cada mensagem da sequência.
`jornada` · `ordem` · `atraso` (quanto tempo depois do passo anterior) ·
`assunto` (o vocabulário fechado das cartas) · `parametros_modelo` ·
`canais` (`sino` · `email` · `whatsapp`) · `condicao_slug` (a função que decide
se ainda faz sentido) · `so_entre` (janela de horário permitida).
Constraint: `unique(jornada, ordem)`.

**`Inscricao`** — uma pessoa dentro de uma jornada.
`jornada` · `destinatario_id` · `site_id` · `passo_atual` · `proximo_em` ·
`estado` (`andando` · `concluida` · `saiu` · `cancelada`) · `motivo_de_saida` ·
`origem_event_id`.
Constraint: **`unique(jornada, destinatario_id, site_id)`** — a mesma pessoa
nunca entra duas vezes na mesma jornada. É esta linha que impede o pesadelo
clássico: o evento reentregue inscrevendo de novo e mandando tudo em dobro.

**`Entrega`** — o que foi (ou não foi) entregue, e por quê.
`inscricao` · `passo` · `decidida_em` · `resultado` (`enviada` · `pulada` ·
`barrada_pela_regua` · `barrada_por_preferencia`) · `motivo` · `event_id`.
Constraint: **`unique(inscricao, passo)`** — segunda camada de idempotência, por
chave de negócio, exatamente como a `mensageria` já faz com
`order_id+tipo+canal`. A varredura pode rodar duas vezes no mesmo segundo: a
segunda não entrega nada.

**A tabela `Entrega` guarda também o que NÃO foi enviado, e isso é essencial.**
Sem ela, a pergunta *"por que o aluno X não recebeu?"* não tem resposta, e o
mantenedor fica olhando para o silêncio. Com ela, a tela do admin responde
*"barrada pela régua: já tinha recebido uma hoje"*.

---

## §6 — A régua anti-chateação, e ela é fail-closed

**Uma peça só, atravessada por toda entrega.** Se cada jornada implementasse a
própria régua, três jornadas somariam três mensagens no mesmo dia — cada uma
respeitando "1 por dia" isoladamente, e o aluno recebendo três.

A régua barra, nesta ordem:

1. **Preferência da pessoa.** Silenciou aquele assunto, ou aquele canal ⇒ barra.
   *Transacional nunca se silencia* — "sua matrícula foi liberada" e "sua senha"
   não são incentivo.
2. **Teto diário.** Máximo 1 por dia por pessoa (lei 4 do §3). Um passo barrado
   **não se perde: reagenda** para a próxima janela válida.
3. **Janela de silêncio.** Nunca depois das 20h. Fuso `America/Sao_Paulo`,
   sempre (lei 6). *"Nunca em horário escolar" **cai** — o público é adulto
   (§8.4), e um adulto às 14h de terça é exatamente quem se quer alcançar.*
4. **Só boa notícia.** Nenhuma jornada de culpa, cobrança ou "você está
   perdendo". O vocabulário de assuntos é fechado justamente para que uma
   jornada nova não consiga inventar um assunto ruim. **Isto não era sobre
   idade e continua valendo integralmente.**

**Não há trava de menor, e é decisão declarada, não esquecimento** (§8.4): a
escola só tem alunos maiores de 18 anos. Se algum dia isso mudar, esta régua é o
lugar onde a trava entra — e entra antes de qualquer mensagem sair.

**Fail-closed:** régua indisponível ou preferência ilegível ⇒ **não envia** e
registra o motivo. É a mesma escolha que a Caixa de Sugestões já fez com a lista
de aprovadores, e é desenho, não bug.

---

## §7 — A escada de PRs

Cada degrau é **um PR pequeno** (orçamento de 15 arquivos, `armadilhas/035`), com
evidência vermelho→verde, e **cada degrau deve virar uma TAR em `fila/`** — é
assim que várias IAs constroem em paralelo sem colidir (RITOS §5: tarefa se pega
no balcão, nunca de memória).

**Os degraus 0 a 7 não dependem de decisão nenhuma sobre e-mail**, e ao fim deles
as sequências **já estão no ar pelo sininho** — que é a ordem que o mantenedor
escolheu em 30/08/2026 (§8.1). Isto não é a "versão reduzida" proibida pelo
`DECISAO-filosofia-de-escopo.md`: é a escada segura para chegar ao completo — o
destino continua sendo e-mail + WhatsApp + preferências + painel.

**A escada encurtou com a decisão do §8.2:** não há gênese de célula, não há
provisionamento de banco novo na VPS, e o contrato `mensagem.devida.v1` sumiu
(§4.3). Em troca, entrou a emenda da constituição, que é degrau próprio.

| # | Degrau | Onde | Entrega visível |
|---|---|---|---|
| **0a** | **Emenda a `AGENTS.mensageria.md`:** a missão passa a incluir sequência com espera, e não só transacional | `constituicoes/` | sem isto, a cerca do CI recusa tudo que vem depois |
| **0b** | **Rito de Contrato** com o mantenedor: `identidade.pessoa-cadastrada.v1` e os assuntos novos em `notificacao.devida.v1` | `contracts/` | não é código (RITOS §3) |
| 1 | `identidade` ganha voz: outbox + relay + publica o cadastro | `identidade` | o cadastro finalmente vira fato na plataforma |
| 2 | Nasce `apps/jornadas`: as 4 tabelas e as travas — **sem mandar nada ainda** | `mensageria` | migração aplicada, `healthz` intacto |
| 3 | A régua (§6) + preferências, com os testes de fuso e de teto | `mensageria` | a régua barra, e o motivo fica registrado |
| 4 | O motor: consumidor dos gatilhos, inscrição, varredura periódica, condições | `mensageria` | uma pessoa entra numa jornada e o passo é agendado |
| 5 | Publica `notificacao.devida.v1` — **a primeira sequência de verdade no ar** | `mensageria` | **boas-vindas chegando no sininho do aluno** |
| 6 | `gamificacao` ganha voz (os 4 assuntos já congelados) | `gamificacao` | comemoração automática ao subir de nível |
| 7 | Tela em `/admin/escola/jornadas/`: quais existem, quem está em cada uma, o que foi enviado e o que foi barrado — **e é aqui que ele edita o texto** (§8.3) | `admin` | o mantenedor troca uma frase sozinho |
| **8** | **`mensageria` deixa de ser stub:** provedor de e-mail real, `consome: [identidade]`, renderização por idioma | `mensageria` | **o primeiro e-mail de verdade sai** |
| 9 | Devolvidos e reclamações (*bounce/complaint*): endereço que devolve é marcado e não se tenta de novo | `mensageria` | a reputação do domínio sobrevive |
| 10 | WhatsApp oficial, se o mantenedor quiser | `mensageria` | segundo canal |

**O degrau 8 tem trabalho que só o mantenedor faz** (Lei 5 — agente não tem SSH,
env nunca viaja por pipeline): conta no provedor, domínio remetente, e os
registros de DNS (SPF, DKIM, DMARC) no Cloudflare. Quando chegar a hora, isso
vira **uma linha só de colar**, fail-closed, como já foi feito nos H20/H21/H22 —
e uma pendência em `painel/registros/` com `precisa_do_dono: true`.

---

## §8 — As quatro decisões — RESPONDIDAS pelo mantenedor em 30/08/2026

As quatro foram feitas a ele em pergunta estruturada, com o custo de cada lado na
mesa, na mesma sessão que produziu este plano. **Estas respostas são a lei deste
plano — onde o texto original recomendava outra coisa, o texto foi corrigido.**

### 8.1 Canal → **sininho primeiro, e-mail em seguida**

Escolhida a opção recomendada. As sequências entram no ar pelos avisos dentro do
site (degraus 0–7) e o e-mail vem logo atrás (degraus 8–9), quando ele escolher o
provedor. **A porta fechada da Fase 7 do sininho está reaberta por ele** — o
`docs/notificacoes/PLANO-MESTRE.md` §Fase 7 deve ser atualizado para dizer isso,
citando este §8.1, no PR do degrau 8.

### 8.2 Onde mora o motor → **dentro da `mensageria`, NÃO uma célula nova**

**Contra a recomendação deste plano**, e é a escolha dele que vale. Sem célula
nova, sem congelamento arquitetural aberto, sem banco novo para provisionar na
VPS. O §4.1 foi reescrito para executar esta decisão: a constraint do pagamento
**não se toca**, o motor entra como `apps/jornadas/` com tabelas próprias, e o
`order_id` sintético (`jornada:<inscricao>:<passo>`) reusa a trava existente sem
migração.

O custo aceito, dito por inteiro: a célula passa a ter duas responsabilidades
(decidir e entregar), e o §10 ganhou um critério de morte para vigiar isso.

### 8.3 Quem edita o texto → **ele mesmo, na área administrativa**

Escolhida a opção recomendada. Sequência é linha de tabela (§4.2), e o degrau 7
entrega a tela onde ele troca a frase de boas-vindas numa terça à noite, sem
robô e sem publicação.

### 8.4 Menores de idade → **a pergunta não se aplica: a escola é 18+**

Ele não escolheu nenhuma das opções oferecidas. Respondeu, com pedido explícito
de registro:

> *"Só temos alunos acima de 18 anos, não temos e nem teremos alunos menores de
> idade, registre isso."*

Consequência neste plano: **nenhuma trava de menor é construída** — sem Modo
Júnior, sem contato de responsável, sem "horário escolar" na régua (§6). O veto a
mascote-que-cobra e notificação-de-culpa **continua**, porque nunca foi sobre
idade.

### 8.5 A divergência que essa resposta abriu — e que é dele, não deste plano

`docs/decisoes/DECISAO-gamificacao.md` §9 (*"Menores, e o que isso obriga"*) foi
promulgado em **30/08/2026, o mesmo dia**, e constrói Modo Júnior como **trava de
sistema**, marcos de dinheiro restritos a 13+, e validação sempre por adulto.
Com a escola sendo 18+, esse §9 inteiro fica sem sujeito.

**Este plano não revoga o §9 e nenhuma sessão deve revogá-lo por conta própria.**
Enquanto ele não decidir, §9 é lei escrita. A pergunta foi devolvida a ele e o
estado dela se lê no livro (`painel/registros/`), não aqui.

**RESPONDIDA em 30/08/2026, ainda na mesma sessão:** ele mandou **revisar o §9
guardando o que serve para adulto** — sai o que só existia por causa de idade
(Modo Júnior, faixa 13+, contato de responsável), fica o que vale em qualquer
comunidade (moderação antes de publicar, sem mensagem privada entre alunos,
links de lista permitida, estúdio público opt-in, evidência de marco em camada
privada). A emenda foi feita; a divergência está fechada.

### 8.6 Quais sequências primeiro → **as quatro**

Perguntado a ele em 30/08/2026, com escolha múltipla. Ele marcou **todas**:

1. **Boas-vindas no cadastro** — o pedido original. Depende do degrau 1
   (`identidade` ganhar voz).
2. **Matrícula liberada** — quem espera na fila descobre sem reabrir o site. O
   fato já é publicado pela `alunos` hoje; falta a sequência que continua depois
   do primeiro aviso.
3. **Sumiu há alguns dias** — a mais difícil, e a que exige a varredura
   periódica e a reavaliação de condição (§2, faltas 1 e 3). É ela que justifica
   o motor existir; uma sequência que não sabe desistir manda "sentimos sua
   falta" para quem voltou ontem.
4. **Comemoração — subiu de nível, ganhou medalha** — depende do degrau 6
   (`gamificacao` ganhar voz). Os quatro assuntos já estão congelados no
   contrato desde a Sessão B.

Nenhuma delas muda a escada do §7 — elas são **dado** (§8.3), e entram como
linhas de tabela conforme os degraus que cada uma exige ficam prontos. A ordem
natural de entrada é 1 → 2 → 4 → 3, porque a terceira é a única que precisa do
motor inteiro.

---

## §9 — Riscos, com o antídoto de cada um

| Risco | Antídoto |
|---|---|
| **A sequência manda o passo 2 para quem já resolveu** — "sentimos sua falta" para quem voltou ontem. É o defeito que faz o aluno desligar tudo. | `condicao_slug` reavaliada **no instante do envio**, nunca no da inscrição. Teste-guarda: a condição deixa de valer entre a inscrição e a varredura ⇒ `Entrega` com `resultado="pulada"`. |
| **Três jornadas somam três mensagens no mesmo dia**, cada uma respeitando "1 por dia" sozinha. | A régua é UMA, por pessoa, atravessando toda entrega (§6). |
| **Evento reentregue inscreve de novo e manda tudo em dobro.** | `unique(jornada, destinatario_id, site_id)` + `unique(inscricao, passo)` + dedup por `event_id` — as três camadas que a `mensageria` já provou funcionarem. |
| **A varredura fica presa e a fila represa** — a plataforma acorda e dispara 400 mensagens de uma vez. | Teto por passada (o `LOTE = 200` que os relays já usam) + a régua barra o excedente e reagenda. |
| **E-mail vai para spam e o domínio queima.** | Degrau 9 antes de qualquer volume: devolvidos e reclamações tratados, endereço ruim marcado. E-mail que devolve e continua sendo tentado é o que mata a reputação. |
| **A tabela de tempo mente por fuso** — o passo das 22h cai no dia errado. | `America/Sao_Paulo` explícito e `test_fuso_horario.py`, que toda célula já tem (`armadilhas/099`). |
| **O motor vira monstro** com uma linguagem de fórmulas dentro do banco. | Condição é função Python registrada num dicionário, PR pequeno por condição nova. DSL é critério de morte (§10). |

---

## §10 — Critério de morte

**Pare e reabra a decisão com o mantenedor** se qualquer uma acontecer:

1. a célula ganhar uma DSL ou linguagem de fórmulas para condições;
2. um evento passar a carregar e-mail, nome ou telefone;
3. nascer uma jornada de culpa, cobrança ou perda;
4. a régua do §6 ganhar exceção "só para esta jornada";
5. o texto de uma mensagem passar a exigir PR de código;
6. qualquer invariante do CI precisar de exceção;
7. **`apps/jornadas` precisar ler ou escrever em qualquer tabela de
   `apps/eventos` além de criar a linha de `EnvioRegistrado`.** Este é o
   critério que a decisão 8.2 obriga: foi o acoplamento que a separação em
   célula teria impedido por construção, e aqui ele só é impedido por
   disciplina. Passou desse ponto, a separação volta à mesa — com a medição na
   mão, não com a mesma recomendação de antes.

---

## §11 — Estado

Este documento **não guarda estado**. O que já foi construído, o que travou e o
que espera decisão se lê no livro (`painel/registros/`) e na fila (`fila/`).
Documento que guarda estado envelhece em silêncio e passa a mentir com
autoridade — a Classe 8 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.
