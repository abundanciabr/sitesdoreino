# PROMPT — Painel de Gestão da Caixa de Sugestões

> **Para quem é este documento:** para o Claude Design (ou qualquer designer/IA)
> que vai desenhar o painel. É autossuficiente — quem ler não precisa abrir o
> repositório para entender o problema.
>
> **O que se pede ao final:** **3 ou mais modelos de painel visualmente e
> conceitualmente DIFERENTES**, para o mantenedor escolher um. Não são três
> variações de cor do mesmo layout: são três teses diferentes sobre como se
> gerencia esse trabalho. O §9 detalha.

---

## 1. O contexto em uma frase

Uma escola online tem um lugar onde os alunos pedem melhorias e votam nos
pedidos uns dos outros; os pedidos mais apoiados viram tarefas de engenharia
executadas por agentes de IA; **falta o painel que mostra e conduz essa
travessia — da ideia do aluno até o código no ar.**

---

## 2. Quem vai olhar este painel

**O dono do projeto.** Ele é o público primário e a régua de todo o desenho:

- **Não é programador.** Não lê código, não usa terminal, não sabe (nem quer
  saber) o que é branch, merge, container ou pipeline.
- **Lê somente português.** Nenhuma palavra de interface em inglês. Nenhuma
  sigla crua sem tradução ao lado.
- **Quer resposta, não relatório.** A pergunta que ele faz ao abrir qualquer
  painel é sempre a mesma: *"o que está acontecendo, o que travou, e o que
  depende de mim?"*
- **Cansa rápido de tela cheia de número.** Uma tela que exige interpretação
  antes de informar é uma tela que ele fecha.

**Secundário: a equipe** (hoje quase só ele; amanhã, pessoas que moderam
sugestões). Precisam de mais detalhe operacional, mas não às custas da clareza
da primeira tela.

**Terciário: os agentes de IA** que executam as tarefas. Eles não *usam* o
painel visualmente, mas o painel precisa expor claramente o que cada um está
fazendo, para que o dono veja o trabalho acontecendo.

---

## 3. O que é a Caixa de Sugestões (o lado do aluno)

Uma ferramenta já **construída e no ar** desde agosto de 2026, dentro da
plataforma da escola. Funciona assim:

### 3.1 Como o aluno entra

Botão **"Entrar com Google"**. O Google prova *quem é a pessoa*; o sistema de
matrículas decide *se ela pode entrar*. **Sem matrícula em algum curso, não
entra** — nem para olhar. Não existe cadastro com senha, nem link por e-mail.

### 3.2 O que o aluno faz lá dentro

| Ação | Regra que a governa |
|---|---|
| **Escrever uma sugestão** | Título, o **problema** que ele vive, e opcionalmente a **solução** que ele imagina. Escolhe uma **categoria**. Antes de publicar, o sistema procura sugestões parecidas e mostra: *"já existe algo assim — quer votar nela?"* |
| **Votar** | **Um voto por pessoa por sugestão.** Pode desvotar. O voto é o combustível do ranking. |
| **Comentar** | Texto livre na sugestão de qualquer um. |
| **Ver o quadro** | Lista ordenada por **total de votos**. Filtro por categoria. |
| **Aba "Em alta"** | Ordena por **calor**, não por total: voto da última semana vale 3, do último mês vale 1, mais antigo vale 0. Serve para uma ideia velha redescoberta pela turma aparecer. |
| **"Meu impacto"** | O que a participação DELE produziu: quantas ideias escreveu, quantas apoiou, quantas saíram da análise, quantos votos recebeu. |
| **Faixa de roadmap** | Uma faixa visual com as 4 fases (ver §3.4) mostrando onde cada ideia está. |
| **Sininho de avisos** | Quando uma ideia muda de fase, **todo mundo que interagiu com ela** é avisado — quem escreveu, quem votou e quem comentou. O aviso diz o motivo ("sua ideia" × "ideia em que você votou"). |

**Freio contra enxurrada:** cada aluno publica no máximo **3 sugestões a cada 7
dias**.

### 3.3 O que o aluno NUNCA vê

A avaliação interna da equipe (as notas de impacto e esforço, as anotações
internas). Isso é blindado por três camadas de código e existe teste que quebra
se alguém abrir essa porta por descuido.

### 3.4 As 6 fases de uma sugestão

Quatro delas são o trilho normal, na ordem:

```
Em análise  →  Planejado  →  Em desenvolvimento  →  Implementado
```

E duas são saídas do trilho, que aparecem numa lista **"Fora do trilho"** logo
abaixo da faixa (não somem da tela, de propósito — sumir faria a conta não
fechar, e esconderia a justificativa que a equipe é obrigada a escrever):

- **Não planejado** — recusada. **Exige justificativa escrita**, sempre.
- **Mesclado** — era duplicata; aponta para a sugestão canônica que a absorveu.

Toda mudança de fase grava uma linha de **histórico que nunca pode ser editada
nem apagada** (correção é uma linha nova). Quem mudou, quando, de qual fase para
qual, e a nota que escreveu.

---

## 4. O lado de dentro: o que já existe hoje

A equipe tem, hoje, três telas funcionando:

1. **A fila** — o quadro inteiro, filtrável por fase, com contagem de votos e um
   marcador de "já foi avaliada ou não".
2. **A tela de moderar uma ideia** — mudar a fase (com nota), ver o histórico
   completo, e escrever a **avaliação interna**, que tem exatamente estes campos:
   - **impacto educacional** (nota)
   - **impacto comercial** (nota)
   - **esforço técnico** (nota)
   - **anotações** livres
   - **decisão de produto** — a tradução de *"problema do aluno"* para
     *"vamos resolver assim"*. É o passo do meio entre a linguagem do aluno e a
     linguagem da engenharia.
3. **A tela de registrar o ChangeSpec aprovado** (ver §5).

**Essas telas são de UMA ideia por vez.** Elas não dão nenhuma visão de
conjunto, nenhuma noção de fluxo, nenhuma noção de trabalho em andamento. É
exatamente esse o buraco (§6).

---

## 5. Como uma sugestão vira código: o corredor

Este é o coração do que o painel novo precisa tornar visível. O caminho completo:

```
Sugestão (linguagem do aluno)
   ↓
Decisão de produto (linguagem do produto)      ← campo "decisão de produto"
   ↓
ChangeSpec (linguagem da engenharia)           ← um documento formal
   ↓
Agente de IA implementa
   ↓
Revisão automática + testes → Pedido de mudança → Publicação no servidor
   ↓
A ideia vira "Implementado" → todos os interessados são avisados
```

### 5.1 O que é um ChangeSpec

Um documento de engenharia com escopo fechado, feito para que um agente de IA
execute **sem inventar nada**. Campos obrigatórios, entre outros:

- **ORIGEM** — qual(is) sugestão(ões) real(is) o originaram (sempre pelo menos uma)
- **PROBLEMA** — reescrito em linguagem de produto, nunca a frase literal do aluno
- **EVIDÊNCIAS** — total de votos, quantas pessoas distintas, comentários relevantes
- **OBJETIVO** — o que muda para o aluno quando isso for entregue
- **FORA DO ESCOPO** — obrigatório, não pode ficar vazio. *"Se não dá para dizer
  o que fica de fora, não houve escopo de verdade."*
- **PARTE RESPONSÁVEL do sistema** e as **partes PROIBIDAS**, listadas uma a uma
- **CRITÉRIOS DE ACEITAÇÃO** — cada um verificável objetivamente. *"Melhorar a
  experiência"* não é critério; *"o aluno publica e recebe o endereço público em
  até 3 cliques"* é.
- **TESTES OBRIGATÓRIOS**, **RISCO E COMO DESFAZER**, **CHECKLIST FINAL**
- **APROVADO POR** — nome e data. **Vazio até uma pessoa autorizada assinar.**

### 5.2 As travas — e por que existem

Estas regras **não são detalhe de implementação**: elas moldam o painel, e o
desenho não pode contradizê-las.

- **Nenhuma ideia sai de "Planejado" para "Em desenvolvimento" sem um ChangeSpec
  aprovado registrado.** A trava é mecânica, em três camadas independentes de
  código. Não há como contornar por engano.
- **Só o dono do projeto aprova.** Ser da equipe **não basta** — moderar e
  autorizar desenvolvimento são papéis diferentes. Um membro da equipe que tente
  registrar uma aprovação **recebe recusa**.
- **A trava é "fail-closed":** se a lista de quem pode aprovar estiver vazia,
  **ninguém aprova e nada anda.** Isso é o comportamento *desejado*, não um
  defeito — *"não sei quem pode aprovar"* jamais vira *"então pode qualquer um"*.
  **O painel deve mostrar esse estado como uma trava consciente, nunca como um
  erro vermelho de sistema quebrado.**
- **Quem escreve o ChangeSpec nunca é quem o implementa.** Um agente pode
  rascunhar; a assinatura é humana e nominal.
- **Depois de aprovado, um ChangeSpec não se edita.** Mudou o escopo? Nasce uma
  versão nova que aponta para a anterior, e a anterior fica onde está.
- **O sistema guarda o REGISTRO da aprovação, não confere o documento.** A
  garantia é *"uma pessoa autorizada afirmou isto, e ficou registrado quem e
  quando"* — nunca *"o documento existe e está bem preenchido"*.

---

## 6. O buraco — o que o painel novo precisa resolver

Hoje existem duas metades que **não se falam**:

| Metade | O que ela sabe | O que ela ignora |
|---|---|---|
| **A Caixa de Sugestões** | tudo sobre as ideias: votos, comentários, fases, quem pediu | nada sobre o trabalho: nenhuma noção de tarefa, agente, execução ou entrega |
| **O painel do projeto** | tudo sobre a construção: entregas, decisões, incidentes, o que trava | nada sobre de onde veio a demanda: não conhece aluno nem sugestão |

**Entre as duas há um vão**, e é ali que uma ideia aprovada some de vista.
Perguntas que hoje **nenhuma tela responde**:

1. Quais ideias já viraram tarefa de verdade, e quais ainda são só ideia?
2. Das que viraram tarefa — quais estão paradas, e paradas **esperando o quê**?
3. Qual tarefa está com qual agente **agora**?
4. O que está pronto para começar **hoje**, e o que pode rodar **em paralelo**
   sem duas tarefas brigarem pelo mesmo arquivo?
5. Quanto tempo uma ideia leva, na média, de "escrita pelo aluno" a "no ar"?
6. **O que depende exclusivamente do dono** para destravar — e quantas ideias
   estão paradas atrás disso?
7. Alguma ideia muito votada está encalhada há tempo demais sem ninguém decidir?

**O painel a ser desenhado é a ponte.** Ele mostra a ideia do aluno virando
tarefa, a tarefa virando trabalho de um agente, e o trabalho virando entrega que
volta ao aluno como aviso de "implementado".

---

## 7. O que o painel precisa mostrar e permitir

Dividido em **essencial** (todo modelo tem que resolver) e **desejável** (cada
modelo escolhe quais adota — é aí que os modelos se diferenciam).

### 7.1 Essencial

- **A travessia inteira, visível de uma olhada:** ideia → triagem → decisão de
  produto → ChangeSpec assinado → em execução por um agente → em revisão →
  publicado → avisado ao aluno. Não precisa ser um Kanban; precisa ser
  *legível de longe*.
- **Uma caixa "Precisa de você"** — tudo que está parado esperando uma ação
  exclusiva do dono, com o número de ideias e de alunos afetados atrás de cada
  item. Se está vazia, ela precisa dizer isso com alegria, não ficar em branco.
- **O peso humano em cada tarefa:** quantos votos, quantas pessoas distintas.
  Uma tarefa não é só um cartão — é gente esperando. **Isso é o que este painel
  tem e um gerenciador de tarefas comum não tem: cada linha carrega uma
  plateia.**
- **Estado de cada tarefa em andamento:** quem executa (agente/pessoa), desde
  quando, e qual o próximo obstáculo.
- **Idade e encalhe:** quanto tempo cada coisa está parada na fase atual, com
  destaque para o que passou do tolerável. Envelhecimento visível sem ninguém
  precisar escrever "atualizado em".
- **Prova, não promessa:** quando algo é declarado pronto, o painel mostra a
  evidência conferida (link do pedido de mudança, resultado da publicação). Sem
  prova conferida, o correto é dizer **"não comprovado"** — nunca pintar de
  verde.
- **A trava do aprovador visível e explicada** — ver §5.2, último ponto.

### 7.2 Desejável (varie entre os modelos)

- **Priorização** cruzando votos × impacto educacional × impacto comercial ×
  esforço técnico (os quatro números já existem). Um mapa de esforço × impacto,
  um score, uma ordenação sugerida — cada modelo pode responder isso diferente.
- **Dependências e conflitos entre tarefas:** o que está pronto para começar, o
  que espera outra coisa terminar, e o que **não deve rodar ao mesmo tempo** que
  outra tarefa por tocarem a mesma área. Daí sai a pergunta mais valiosa: *"qual
  é a melhor combinação de trabalhos para começar agora?"*
- **Lotes/ondas de execução:** agrupar tarefas independentes que podem ser
  despachadas simultaneamente para agentes diferentes.
- **Linha do tempo de uma ideia**, do dia em que o aluno escreveu até o dia em
  que entrou no ar, com cada mão que a tocou.
- **Termômetro da Caixa:** ritmo de ideias novas, participação, categorias mais
  quentes, ideias em análise há tempo demais.
- **Ciclo de vida médio** por fase — onde as ideias mais empacam.
- **O retorno ao aluno:** quantas pessoas foram avisadas de cada entrega. Fechar
  o laço é parte do produto.

### 7.3 Ações que o painel pode oferecer

O modelo escolhido pode (ou não) propor ações diretas na tela. Se propuser, elas
precisam ser **explícitas e sem jargão**:

- mover uma ideia de fase (com a nota obrigatória quando for recusa);
- escrever/editar a decisão de produto;
- pedir o rascunho de um ChangeSpec;
- **assinar** um ChangeSpec (a ação exclusiva do dono — merece tratamento visual
  de peso, é uma assinatura, não um clique qualquer);
- despachar uma tarefa aprovada para um agente.

---

## 8. Restrições de desenho (não negociáveis)

1. **Tudo em português do Brasil.** Zero palavra de interface em inglês. Zero
   sigla crua — se precisar de uma, traduza ao lado, na mesma linha.
2. **Linguagem de resultado, não de processo.** *"A plataforma está no ar"*, não
   *"pipeline concluído com sucesso"*.
3. **O painel não guarda dado próprio — ele CALCULA.** Lei do projeto: nenhum
   fato mora em dois lugares. Toda vista é derivada dos fatos que já existem
   (as sugestões, os votos, o histórico de fases, os registros do projeto).
   Consequência prática para o desenho: **nada de campos que alguém precise
   manter à mão** ("status: atualizado por Fulano em..."). Se o painel mostra
   algo, é porque algo o produziu.
4. **Uma lista calculada não pode esquecer.** A caixa "Precisa de você" é
   derivada de "pedido sem resposta" — ela não depende de ninguém lembrar de
   marcar como resolvido.
5. **Verde é conquistado.** Só se pinta de verde o que tem evidência conferida.
   O resto é "não comprovado" — e isso é honesto, não feio.
6. **Tema escuro**, coerente com a Caixa que já existe. Paleta de referência:

   | Papel | Cor |
   |---|---|
   | fundo | `#15161c` |
   | superfície | `#1e202b` |
   | superfície clara | `#262838` |
   | linha | `rgba(255,255,255,.08)` |
   | destaque (laranja) | `#ff7a33` |
   | informação (azul) | `#4c8dff` |
   | sucesso (verde) | `#34d399` |
   | alerta (vermelho) | `#ff5c5c` |
   | texto | `#edeef2` |
   | texto fraco | `#9a9db0` |
   | texto tênue | `#5c5f70` |

   Fonte de sistema (nada de fonte exótica). Sinta-se livre para propor um
   acento diferente **se a tese do modelo pedir** — mas justifique.
7. **Legível em tela grande e em celular.** O dono abre isso do computador na
   maior parte do tempo, mas confere do telefone.
8. **Acessível sem depender de cor:** quem não distingue vermelho de verde
   precisa entender o estado pelo texto e pela forma.
9. **Nada de gráfico decorativo.** Todo elemento visual responde a uma pergunta
   do §6. Se não responde, sai.

---

## 9. O que entregar

**Três ou mais modelos de painel, cada um defendendo uma tese diferente** sobre
como esse trabalho se gerencia. O objetivo é dar ao dono uma escolha real, não
três sabores do mesmo prato.

Para cada modelo, entregue:

- **um nome curto** e **uma frase de tese** ("este painel acredita que...");
- **a tela principal**, desenhada de verdade, com dados de exemplo plausíveis
  (nomes de ideias que um aluno de uma escola de criação de jogos escreveria —
  ver §10);
- **pelo menos uma tela secundária ou estado** que revele como o modelo se
  comporta na profundidade (o detalhe de uma ideia, a assinatura de um
  ChangeSpec, ou a visão de um agente trabalhando);
- **o estado "tudo em dia"** — como a tela fica quando não há nada esperando o
  dono. Um painel que só é bonito cheio de problema é um painel que ensina medo;
- **uma nota honesta** do que esse modelo entrega bem e do que ele sacrifica.

### Direções sugeridas (use, misture ou proponha melhores)

- **A) Fluxo / esteira** — a travessia inteira em colunas ou faixas, cada tarefa
  visivelmente atravessando etapas. Força o dono a ver *onde entope*.
- **B) Caixa de entrada / fila de decisões** — a tela abre com *"o que espera
  você"*, uma decisão por vez, no maior tamanho possível. O resto é secundário.
  Tese: o gargalo é a decisão humana, não a execução.
- **C) Sala de controle / ondas** — mostra o que os agentes estão fazendo agora e
  qual a próxima combinação de trabalhos que pode rodar em paralelo sem
  conflito. Tese: o valor está em orquestrar execução simultânea.
- **D) Voz do aluno em primeiro plano** — a unidade da tela é a *pessoa
  esperando*, não a tarefa. Cada item mostra a plateia antes do estado técnico.
  Tese: o painel existe para não deixar ninguém sem resposta.
- **E) Linha do tempo / mapa da ideia** — o eixo é o tempo: da ideia escrita ao
  código no ar, com o encalhe visível como espaço vazio.

---

## 10. Dados de exemplo (use estes, ou nesta linha)

A escola ensina **criação de jogos e mundos 3D para Roblox**, para adolescentes
e jovens adultos. Sugestões plausíveis:

| Ideia | Votos | Pessoas | Fase |
|---|---|---|---|
| "Quero uma página pública com meus projetos para mostrar a clientes" | 218 | 176 | Planejado (ChangeSpec assinado) |
| "As aulas de scripting deviam ter exercício corrigido automaticamente" | 143 | 121 | Em análise |
| "Modo escuro na área de aulas" | 97 | 89 | Em desenvolvimento |
| "Certificado de conclusão que eu possa colocar no LinkedIn" | 84 | 80 | Em análise |
| "Poder baixar os assets das aulas de uma vez" | 61 | 55 | Não planejado (com justificativa) |
| "Fórum de dúvidas dentro da plataforma" | 52 | 48 | Mesclado na ideia da comunidade |
| "Trilha para quem já sabe programar" | 44 | 41 | Em análise |
| "Aula ao vivo mensal de tira-dúvidas" | 38 | 36 | Implementado |

Categorias plausíveis: **Aulas e conteúdo · Plataforma · Comunidade ·
Certificação · Ferramentas**.

---

## 11. O que NÃO fazer

- ❌ Não desenhe "mais um Trello". Cartão com título e etiqueta é o ponto de
  partida de todo mundo — o valor deste painel está no que um Trello **não**
  sabe: a plateia de alunos atrás de cada linha, a assinatura que destrava, e o
  agente que executa.
- ❌ Não invente uma tela onde alguém digita e mantém estado à mão (§8.3).
- ❌ Não pinte de verde nada sem evidência (§8.5).
- ❌ Não trate a trava do aprovador como erro a ser consertado (§5.2).
- ❌ Não use inglês na interface, nem sigla sem tradução.
- ❌ Não proponha a versão reduzida "para começar". Este projeto é para ser feito
  completo — é decisão explícita e permanente do dono. Fatiar a construção em
  etapas seguras é bom; **cortar escopo por ser mais rápido, não.**
- ❌ Não misture assunto de pagamento, cobrança ou checkout. Está fora do escopo
  por diretiva vigente.
