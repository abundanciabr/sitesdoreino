# DECISÃO — as cinco categorias de usuário, e onde cada uma é calculada

> **Decidida pelo mantenedor em 28/08/2026**, na sessão em que ele olhou a home
> do site com a própria conta e viu o botão da Caixa de Sugestões aparecer para
> ele, que não é aluno de nada. As palavras dele: *"o botão de Caixa de
> Sugestões só deveria aparecer para quem é Aluno. E assim teríamos ou deveria
> ter algumas categorias de usuários, Visitantes, Cadastrados (quem só fez
> login com o Google), Alunos (quem foi aprovado ou marcado como Aluno por um
> Admin), e assim por diante"*.
>
> **Status:** *isto é lei.* É também o **Rito de Contrato** (`RITOS.md` §3)
> cumprido: sessão com ele presente, e a autorização para abrir o contrato
> congelado da `alunos` **perguntada e respondida nominalmente** — ele escolheu,
> entre três opções apresentadas, a porta que responde a *situação* completa (e
> não a versão reduzida "é aluno ou não").
>
> Executa as **fases 2 e 3** da `DECISAO-fila-de-liberacao.md` §8, que estavam
> escritas e paradas desde 27/08/2026.

---

## 1. Por que isto precisa ser lei, e não uma condição no template da home

Hoje **cada parte do site adivinha por conta própria** o que uma pessoa é:

- a **home** (`funil`) sabe apenas *"entrou ou não entrou"* (`request.ator`), e
  por isso mostra o botão da Caixa para todo mundo que fez login;
- a **Caixa** (`sugestoes`) sabe *"tem matrícula que vale?"*, perguntando à
  `alunos`, e é a única que acerta;
- a **área administrativa** (`admin`) sabe *"este e-mail está na minha lista?"*;
- a **`identidade`** devolve um campo `papel` que diz `aluno` para **qualquer
  pessoa que tenha feito login** — herança de quando `aluno` significava só
  "não é staff". Esse campo **não é** categoria, e a lei da identidade já diz
  que ele *nunca autoriza nada*.

Quatro respostas para a mesma pergunta, e três delas erradas em pelo menos um
caso. É a doença que o `CLAUDE.md` chama de duplicação: **estado se calcula, e
se calcula num lugar só.**

## 2. As cinco categorias

O mantenedor escolheu, entre três vocabulários oferecidos, o de **cinco nomes** —
com "Na fila" como categoria própria, porque é nela que ele age, e categoria em
que se age precisa de nome curto.

| # | Categoria | Como o sistema sabe | Quem é a autoridade |
|---|---|---|---|
| 1 | **Visitante** | não há sessão do site | quem pergunta (não há e-mail para consultar) |
| 2 | **Cadastrado** | tem sessão; a `alunos` não tem linha nenhuma para este e-mail | `alunos` |
| 3 | **Na fila** | tem linha com status `aguardando` ou `recusada` | `alunos` |
| 4 | **Aluno** | tem linha com status em `STATUS_QUE_VALEM` (desde 31/08/2026, só `ativa`) | `alunos` |
| 5 | **Administrador** | e-mail em `ADMIN_EMAILS` | **a célula `admin`, e só ela** |

**"Recusado" é um estado de "Na fila", não uma sexta categoria.** Quem foi
recusado precisa ver o motivo para poder pedir de novo — a `DECISAO-fila-de-liberacao`
§7 já define o reenvio como o jeito de corrigir um dado errado. Uma categoria
separada obrigaria toda tela a tratar seis casos para exibir a mesma coisa.

**"Ex-aluno" não existe aqui, e a ausência FOI decisão.** Foi oferecida ao
mantenedor e recusada: em 24/08/2026 ele decidiu que `reembolsada` continua
contando como aluno, *quem já foi aluno mantém a voz na Caixa*. Separar teria
mudado essa regra por tabela.

> **EMENDA de 31/08/2026.** As duas coisas mudaram desde então, cada uma em lei
> própria. "Ex-aluno" **existe** como categoria desde 28/08
> (`DECISAO-ex-aluno-e-a-porta-que-explica.md`), e `reembolsada` **deixou de
> dar acesso** em 31/08 (`DECISAO-reembolso-tira-o-acesso.md`), que também fez
> nascer a categoria `reembolsado`. A escada desta seção tem hoje sete degraus,
> não cinco.

### 2.1 Administrador é ORTOGONAL, e isso não é detalhe

As categorias 1–4 formam uma escada: cada pessoa está em exatamente um degrau.
**Administrador não está na escada** — é um crachá que se acumula com qualquer
degrau, e é calculado por uma lista que mora na célula `admin`, nunca na
`alunos` e nunca na `identidade`.

Por que importa: no dia em que a `alunos` respondesse "administrador", a
autorização da área administrativa passaria a depender de uma célula de
produto. É o invariante *reconhecer não é autorizar*
(`DECISAO-onde-mora-a-sessao.md` §4) — a resposta desta lei **descreve**, nunca
**permite**. Quem decide se alguém entra em `/admin` continua sendo
`ADMIN_EMAILS`, conferida na hora, na porta.

## 3. Onde a categoria é calculada: uma porta só, na `alunos`

A `alunos` ganha **uma** operação de leitura:

```
GET /alunos/{email}/situacao   →   getStudentStanding
```

Ela responde a categoria da pessoa **e nada além disso**. As decisões de
desenho, cada uma com o modo de falha que ela fecha:

- **Responde 200 com `cadastrado` para quem ela não conhece — nunca 404.**
  "Não tenho linha para esta pessoa" **é a resposta**, não um erro. A porta
  vizinha (`GET /alunos/{email}/matriculas`) devolve 404 nesse caso, e está
  certa no contexto dela; aqui um 404 obrigaria cada consumidor a traduzir
  "erro" em "cadastrado" por conta própria — e o primeiro que tratasse 404
  como falha de rede mostraria a tela errada, fail-OPEN, para todo visitante
  novo do site.
- **Não devolve PII: sem WhatsApp, sem nome, sem eco do e-mail.** É a §5 da
  `DECISAO-fila-de-liberacao` aplicada: o telefone sai por **uma** porta só, a
  do painel administrativo. Guarda de conjunto EXATO de chaves na resposta —
  campo novo que vaze dado pessoal fica vermelho.
- **`esperando_ha_dias` vem calculado pela `alunos`**, não pela data crua: é o
  provedor quem tem o relógio e a linha. Consumidor que subtraísse datas
  erraria de formas diferentes em cada célula.
- **A categoria é derivada da MESMA `STATUS_QUE_VALEM`** que decide acesso. Uma
  segunda lista de "quais status contam" seria duas verdades sobre quem é
  aluno, e elas divergiriam no primeiro status novo.

## 4. Quem pode perguntar, e o degrau de e-mail que isto abre

| Consumidor | Para quê | Já tinha acesso a e-mail? |
|---|---|---|
| `funil` (a home) | mostrar o botão certo, ou o andamento do pedido | **não — este é o degrau novo** |
| `sugestoes` (a Caixa) | já pergunta o equivalente hoje; migra depois, sem pressa | sim |
| `admin` | a fila usa `GET /pre-matriculas`; esta porta é para conferir uma pessoa | sim |

**O degrau novo, registrado por escrito como a `DECISAO-celula-de-identidade`
§6.3 exige:** para saber QUEM está na home, o `funil` passa a precisar do
e-mail da sessão — ou seja, entra em `TOKENS_COMPLETOS_FUNIL` na `identidade`,
ao lado de `sugestoes` e `admin`. O motivo é este: **a categoria de uma pessoa
é calculada por e-mail, porque é por e-mail que a `alunos` guarda matrícula** —
e não existe outro identificador comum entre as duas células.

**Por que a ampliação é menor do que parece, e isso é medição e não conforto:**
o `funil` **já manipula e-mail hoje** — o formulário de `/cadastro` envia
e-mail e telefone para a célula `leads` (`LeadsClient.upsert_lead`). Não é uma
classe nova de dado entrando numa célula que não a tinha; é a mesma classe,
por um caminho a mais, agora só de leitura.

**O que continua proibido, e ganha guarda:** o e-mail **não** vai para o
template, **não** entra em log e **não** aparece em nenhuma resposta ao
navegador. Ele existe dentro da requisição, o tempo de fazer uma pergunta.

## 5. O que cada categoria vê na home — decidido nominalmente

O mantenedor escolheu, entre três opções, **"só o andamento, sem convite"**:

| Categoria | O que a home mostra |
|---|---|
| **Visitante** | "Entrar" — como hoje |
| **Cadastrado** (nunca pediu) | **nada sobre a escola.** Sem botão da Caixa, sem convite para entrar na fila |
| **Na fila — aguardando** | *"seu pedido está em análise há N dias"* |
| **Na fila — recusado** | o motivo, e que pode pedir de novo |
| **Aluno** | o botão da Caixa de Sugestões, como hoje |

**A opção recusada, nominalmente: convidar quem nunca pediu.** Ela foi
apresentada como recomendada e ele escolheu a outra. O efeito prático é
deliberado — **o caminho de entrada na fila deixa de ser descoberto por acaso**
e passa a existir onde ele divulgar. A fila continua aberta a qualquer conta
Google (a `DECISAO-fila-de-liberacao` §7 já aceitou esse risco, com "alguém
olhar" como única defesa que não erra); o que muda é a home não empurrar
ninguém para lá.

**Consequência que precisa estar escrita:** hoje quem não é aluno chega ao
formulário da fila **clicando no botão da Caixa**. Tirando o botão, esse
caminho some para quem nunca pediu. Isso é o que foi escolhido — não um efeito
colateral esquecido. O endereço da Caixa continua funcionando e continua
mostrando o formulário para quem chegar nele.

## 6. Fail-OPEN ou fail-CLOSED: os dois, e em lugares diferentes

Esta é a parte que mais fácil se erra, e ela já tem precedente medido no
projeto (`DECISAO-onde-mora-a-sessao` §4).

- **Na home (`funil`), a `alunos` fora do ar ⇒ trata como `Cadastrado`.** A
  vitrine não pode cair porque uma célula de produto caiu. O pior caso é uma
  pessoa não ver o botão dela por alguns minutos — irritante, não perigoso.
  **É fail-OPEN quanto à PÁGINA e fail-CLOSED quanto ao ACESSO**, que é a
  combinação certa: a home nunca é a porta.
- **Na Caixa (`sugestoes`), nada muda.** Ela continua fail-closed, perguntando
  "tem matrícula que vale?" ao entrar. **A home nunca autoriza** — esconder um
  botão não protege nada, e mostrar um botão não libera nada. Quem digitar o
  endereço da Caixa direto continua batendo na porta de sempre.
- **Na área administrativa (`admin`), nada muda.** `ADMIN_EMAILS` na porta,
  404 para quem não é da casa.

## 7. O que fica FORA, de propósito

- **Categoria gravada em coluna.** Ela é sempre **calculada** dos status. Um
  campo `categoria` no banco seria a mesma pergunta com duas respostas
  possíveis, e um dia elas divergiriam — a doença que este projeto passou o mês
  curando.
- **Categoria dentro do cookie de sessão.** O cookie é assinado, não cifrado, e
  a `DECISAO-celula-de-identidade` já proíbe pôr papel lá: mudaria de valor sem
  a pessoa entrar de novo, e viraria autorização acidental.
- **Aviso automático de que a pessoa foi liberada.** É a fase 3 da
  `DECISAO-fila-de-liberacao` pela caixa de notificações, e não entra aqui.
- **Qualquer aprovação automática.** Continua valendo o §7 daquela lei: toda
  liberação é humana.

---

*Relacionados: `DECISAO-fila-de-liberacao.md` (as fases 2 e 3 que esta lei
executa) · `DECISAO-onde-mora-a-sessao.md` §4 (reconhecer não é autorizar) ·
`DECISAO-celula-de-identidade.md` §6.3 (o registro por escrito de cada par com
acesso a e-mail — cumprido no §4 acima) · `DECISAO-celula-admin.md` §2
(`ADMIN_EMAILS` como única fonte de "pode entrar") · `RITOS.md` §3 (o rito
cumprido aqui).*
