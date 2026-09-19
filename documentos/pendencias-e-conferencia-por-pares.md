---
titulo: A Central de Pendências e a conferência por pares
ordem: 45
---

# A Central de Pendências e a conferência por pares

Plano escrito em 06/09/2026, a pedido do mantenedor, depois de ele abrir
`meshcraft.top/conquistas/interno` e dizer: *"que eu nem sabia que isso
existia"*.

Este documento tem duas metades que resolvem o mesmo problema por lados opostos.
A primeira diminui o que chega até você. A segunda faz caber numa tela só o que
ainda chega.

## 1. O que está errado hoje, medido

Você não descobriu uma tela nova. Você esqueceu uma tela que já é sua.

Em 01/09/2026 você colou uma linha no servidor, o script respondeu *"PRONTO: a
equipe da escola tem 1 pessoa(s) que podem conferir marcos"*, e você abriu a
página e viu "Pedidos esperando você". Está tudo registrado no livro de
ocorrências (registro `20260901-009`). Cinco dias depois, a mesma página era uma
surpresa.

Isso não é falha de memória. É falha de desenho: **uma fila que ninguém lembra
de abrir é uma fila que não existe.**

E não é uma fila. São seis, cada uma num endereço diferente, nenhuma delas
avisando nada:

- **Provas de marco enviadas pelos alunos**, em `/conquistas/interno`. Abre para uma lista de nomes escrita dentro do servidor.
- **Portfólios pedindo conferência**, em `/pages/equipe`. Abre para todo administrador da escola.
- **Checkpoints de aula esperando laudo**, em `/cursos/plantao`. Abre para a equipe do plantão.
- **Gente pedindo para entrar na escola**, em `/admin/escola/alunos/`. Abre para todo administrador.
- **Ideias da Caixa de Sugestões**, em `/admin/caixa/`. Abre para quem está na lista de aprovadores.
- **Decisões que os robôs pediram a você**, no painel do sistema. Só você.

Só a última tem contador, e no dia em que este plano foi escrito ela marcava
**85 pedidos parados esperando você**.

**E o tamanho da escola, que é o que decide se isso urge.** Lido em
`/admin/escola/alunos/` em 07/09/2026:

- **133 alunos ativos**, que é quem tem acesso à área de alunos agora.
- **9 pessoas aguardando aprovação** neste momento, ou seja, a primeira linha da Central já tem trabalho de verdade esperando.
- 4 recusados, e zero pausados, ex-alunos ou reembolsados.
- **132 desses alunos estão matriculados em "Primeiros Dólares com Roblox"**, que é o curso que ensina o portfólio. Medido no mesmo dia, pela saída do script que gravou as matrículas. Esse é o tamanho máximo da fila de conferência: até 132 portfólios, e hoje só você para conferir.

Esse número mora no sistema, em `/admin/escola/alunos/` e em `/admin/placar/`, e
é lá que ele se confere. **Não se confere em arquivo nenhum do computador.**

Este plano nasceu com esse erro dentro, e ele fica escrito para ninguém repetir:
a primeira versão dizia *"a escola tem 30 pessoas"*, contando as 30 LINHAS da
lista antiga de WhatsApp (`turmas.txt`) como se fossem gente. Aquele arquivo tem
344 números dentro daquelas 30 linhas, e mesmo os 344 não seriam a matrícula da
escola: ele é a lista de quem foi convidado, não de quem entrou.

Há ainda um sétimo caso, que é uma promessa não cumprida: a lei da escola diz
que toda publicação pública do fórum passa por moderação humana antes de
aparecer. O estado "Esperando aprovação" existe no banco do fórum, e **nenhuma
linha de código o usa**. Não há fila, não há tela, não há aprovação. Isso não é
urgente hoje (o fórum tem pouco movimento), mas está escrito aqui para não ser
descoberto como surpresa depois.

## 2. A Central de Pendências

### O que você vê

Uma linha no alto de **todas** as telas de `/admin/`, ao lado do menu:

> **4 coisas esperando você.** Ver

Ela aparece em toda tela porque é assim que se conserta esquecimento. Uma página
que você precisa lembrar de abrir tem exatamente o defeito que este plano existe
para curar. Quando não há nada esperando, a linha some: um contador zerado todo
dia ensina a ignorar o contador.

Clicando, você chega em `/admin/pendencias/`, e vê isto:

> **Esperando você**
>
> **9 pessoas querem entrar na escola.** A mais antiga pediu há 3 dias. `Abrir`
>
> **1 portfólio pedindo conferência.** Nenhum colega olhou ainda, e ele espera há 2 dias. `Abrir`
>
> **1 prova de marco.** "Primeiros dólares", com prazo até 09/09. Este marco envolve dinheiro, então só você fecha. `Abrir`
>
> **3 portfólios foram aceitos por colegas esta semana. 1 foi sorteado para você conferir.** `Abrir`
>
> **Nada esperando em:** laudos de aula, Caixa de Sugestões.
>
> **85 decisões suas paradas no painel do sistema.** `Abrir`

Sem sigla, sem número solto, sem gráfico. Cada linha diz **o que é, há quanto
tempo espera, e leva para o lugar onde se resolve**. A tela não resolve nada por
dentro: ela é a portaria, e cada fila continua morando na sua própria casa, que
é onde a regra dela é conferida.

### Como isso funciona por dentro, em uma linha

Cada parte do site aprende a responder uma pergunta só: *"quantas coisas estão
esperando aí, e a mais antiga é de quando?"*. O Admin pergunta a todas ao mesmo
tempo e soma.

O Admin **não guarda cópia** de nenhuma dessas contas. Esta casa tem uma lei
para isso: o mesmo fato em dois lugares é um fato que um dia vai discordar de si
mesmo, e ninguém percebe. A conta é sempre a de quem tem o dado.

Se uma parte do site não responder (por queda, por credencial que falta), a
linha dela diz **"não deu para perguntar agora"** em vez de mentir "zero" ou de
derrubar a página inteira. Uma tela de operação que não abre é inútil justamente
no dia em que você precisa dela.

## 3. A conferência por pares

Aqui está a parte que você pediu, e ela precisa começar por três coisas que a
casa já decidiu, porque duas delas contrariam o que você descreveu.

### O que já está pronto e ninguém usou

A validação por colega **não é ideia nova aqui**. Ela está escrita na lei da
gamificação desde a fundação da célula, foi auditada por quatro consultorias
independentes, e boa parte dela **já está construída**:

- O registro de uma conquista já sabe guardar que quem validou foi "um colega", e não a escola.
- O código já recusa alguém validar o próprio trabalho.
- O código já escala para a escola quando um pedido leva duas devoluções vindas de colegas, o que existe para o caso de um grupo combinar de recusar o trabalho de alguém.
- O sistema já tem um peso interno de confiança por pessoa, invisível em toda tela, feito para escolher a quem pedir uma conferência.

**O que falta é a tela do colega.** Hoje só existe a tela da equipe. Ou seja: o
seu pedido é o próximo degrau de uma escada que já está construída até aqui, e
não uma reforma.

### As três correções ao que você descreveu

**Primeira: o colega não pode ver o print.** A lei da escola diz, com estas
palavras, que a evidência de um marco fica em camada privada e que colegas nunca
a veem. Um print de pagamento carrega o nome de um cliente, um valor e às vezes
uma conversa. Isso não é detalhe de privacidade, é o motivo pelo qual os dois
marcos que envolvem dinheiro ("Primeiro cliente" e "Primeiros dólares") **têm
uma trava no próprio banco de dados** que recusa a linha se o validador não for
da equipe. Não é preferência de programador, é restrição do PostgreSQL, e ela
fica.

O que sobra para o colega conferir são **artefatos públicos**: coisas que
qualquer um pode abrir e julgar sem invadir a vida de ninguém. Que é exatamente
o portfólio.

**Segunda: o poder de conferir não vira faixa visível.** Você descreveu Faixa
Branca, Azul e Preta. A lei desta casa decidiu o contrário, e o motivo cabe em
uma frase: **quem confere não é um troféu.** O poder de conferir é uma função
técnica, discreta e revogável, sem contador público e sem selo no perfil. O
motivo não é tamanho de turma, é o que a faixa faz com a cabeça de quem a usa:
ela transforma "eu ajudo" em "eu sou mais que você", e a partir daí as pessoas
conferem para subir, não para conferir bem. O poder existe, é real e é
revogável. Ele só não é exibido.

**Terceira: quórum sim, votação não, e a diferença não é de tamanho.** A lei
proíbe por escrito voto popular decidindo mérito ("Escolha da Galera"), e essa
proibição continua. Mas o que você pediu **não é isso**: dois colegas marcando
uma lista de itens objetivos ("tem 3 tipos de modelo?", "tem 3 peças de cada?")
não é gosto, é conferência. Ninguém está votando se a obra é bonita.

Aqui eu preciso corrigir uma coisa que escrevi antes. Na primeira versão deste
plano eu disse que quórum devia esperar a escola crescer, e apoiei isso num
arquivo velho no meu disco (`turmas.txt`, a lista antiga de WhatsApp) em vez de
olhar o sistema. **O mantenedor corrigiu em 07/09/2026 abrindo a própria tela:
133 alunos ativos.** O argumento de população caiu, e ele não fazia falta: o que
sustenta a conferência por pares aqui é o critério ser objetivo, não a escola ser
grande ou pequena. Com 133 pessoas dentro, aliás, ela deixa de ser conveniência e
vira necessidade: uma fila de conferência que só você atende não atravessa esse
número.

### Onde o colega confere: o portfólio

A escolha é essa, e o motivo é aritmético. Existem três marcos na escola. Dois
são de dinheiro e estão trancados no banco para colegas. **Sobra um:**
"Portfólio no ar".

E aqui está a parte bonita: **o portfólio já tem tudo o que uma conferência por
pares precisa, e ninguém tinha ligado as pontas.**

- Os critérios são objetivos e foram escritos pela professora, não por um robô: pelo menos 3 tipos de modelo, pelo menos 3 peças de cada tipo, a maioria em high poly, e nada parecido demais com o modelo feito na aula.
- O que se confere é **um link público** que qualquer pessoa abre. Não há print, não há dado privado, não há nada para vazar.
- Os motivos de devolver já são uma lista fechada de frases prontas, cada uma apontando uma regra objetiva. Ninguém escreve opinião sobre o trabalho de ninguém, que é a diferença entre um processo e uma humilhação.
- E quando a escola aceita um portfólio, um aviso já viaja sozinho até a gamificação e acende o marco "Portfólio no ar" no nome do aluno.

Ou seja: **construir a conferência por pares no portfólio acende o marco de
graça.** As duas coisas que você pediu são, por baixo, a mesma obra.

### O que o aluno vê

Na Prancheta dele nasce uma seção nova, e ela só aparece para quem pode
conferir:

> **Conferir o portfólio de um colega**
>
> Alguém da turma pediu conferência. Abra as peças e diga se cumprem as quatro regras da escola. Você tem 3 conferências por semana.
>
> `Abrir o portfólio` (sem nome, sem foto, sem apelido)
>
> `caixa` Tem pelo menos 3 tipos de modelo diferentes
>
> `caixa` Tem pelo menos 3 peças de cada tipo
>
> `caixa` A maioria está em high poly
>
> `caixa` Nenhuma peça é parecida demais com o modelo da aula
>
> `Está de acordo`   `Ainda falta`, escolhendo o que falta na lista

**O nome do dono não aparece.** É a defesa mais barata e mais forte contra
amizade e contra implicância, e ela custa uma linha de código.

### O que acontece depois

Dois colegas conferem, cada um sem saber do outro. A partir daí, uma de quatro
coisas:

- **Os dois concordam que está de acordo:** o portfólio é aceito na hora, sem passar por você, e o marco "Portfólio no ar" acende no nome do aluno. Foi a sua decisão de 06/09/2026, e a seção 6 explica o que ela obriga.
- **Os dois concordam que falta:** o aluno recebe o que falta, com as frases da professora, em particular, e pode mandar de novo.
- **Eles discordam:** vai para você, sem nenhum dos dois saber que discordaram.
- **Duas devoluções de colegas:** o pedido sai do caminho dos colegas para sempre e passa a ser seu. Essa trava já está construída.

## 4. As travas, e o que cada uma impede

Cada uma existe por causa de um ataque concreto, não por precaução genérica. As
que dizem "já construída" são código que já roda hoje.

- **Ninguém confere o próprio trabalho.** O óbvio. Já construída.
- **O nome do dono não aparece na conferência.** Impede aprovar o amigo e reprovar o desafeto.
- **Teto de 3 conferências por semana.** Impede que uma conta invadida, ou uma pessoa com raiva, aprove a turma inteira numa tarde.
- **Quem conferiu fica gravado, para sempre.** Faz a pergunta "quem disse que sim?" ter resposta daqui a um ano.
- **O sistema marca quando A confere B e B confere A.** É o combinado entre dois amigos, o ataque mais provável de todos. Quem for apontado por ela cai na amostra semanal sempre, sem sorteio.
- **A amostra semanal:** parte do que os colegas aceitaram sozinhos volta para você conferir. Obrigatória por causa da sua decisão da seção 6, e explicada lá.
- **Duas devoluções de colega escalam para a escola.** Impede um grupo combinar de recusar o trabalho de alguém. Já construída.
- **Devolver só com motivo de uma lista fechada.** Impede a devolução virar crítica pessoal. Já construída.
- **Marco de dinheiro nunca passa por colega.** Impede vazar print de pagamento, e elimina o conflito de quem confere ser concorrente. Já construída, dentro do banco de dados.
- **Você desfaz qualquer conferência e tira o poder de qualquer um.** Impede todo o resto.

A régua que a casa usa, e que este plano segue: **prefira teto a punição.** Um
limite que impede o estrago é melhor que um castigo depois dele.

## 5. A ordem de construção

Seis degraus, um PR cada, na ordem em que cada um passa a servir para alguma
coisa sozinho.

1. A Central de Pendências com o que o Admin já sabe: alunos esperando, ideias da Caixa, pedidos do painel. Já vale no primeiro dia, sem depender de ninguém.
2. A linha no alto de todas as telas do Admin, com o contador.
3. As outras filas entram na conta: portfólio, marcos e laudos passam a responder a pergunta "quantos estão esperando?".
4. A conferência por pares no portfólio: quem pode conferir, a tela sem nome, o teto semanal, o registro de quem conferiu, **e a amostra semanal na Central**. A amostra vai junto, e não depois, porque nesta decisão ela é o único lugar onde um adulto ainda olha (seção 6).
5. A vigilância do combinado: a marca de quando duas pessoas conferem uma à outra, visível só para você, alimentando a amostra.
6. A tela onde você desfaz uma conferência e tira o poder de alguém.

Do degrau 3 sai um passo seu no servidor, de uma linha, para o Admin poder
perguntar ao fórum. As outras três partes já têm a credencial.

**O fórum não entra nesta obra.** A moderação prometida e não construída é uma
tarefa própria, e misturá-la aqui dobraria o tamanho de tudo.

## 6. As duas decisões que você tomou, e o que elas obrigam

Perguntadas e respondidas em 06/09/2026. As duas definem o contrato social da
escola, não a engenharia, e por isso eram suas.

### Quem ganha o poder de conferir

**Sua decisão: quem já teve o próprio portfólio conferido e aceito pela escola.**

É automático (você não escolhe ninguém, não há favorecido), é justo (só confere
quem já passou pela régua) e prova competência (a pessoa entendeu o critério
porque ele foi aplicado nela).

Isso tem uma consequência de partida que é preciso dizer: **no primeiro dia
ninguém pode conferir**, porque ninguém foi conferido ainda. Os primeiros
portfólios são seus, um por um, e a partir daí o círculo cresce sozinho. Não é
defeito, é a única forma honesta de começar: o primeiro conferente tem que ter
sido conferido por alguém.

Com 133 alunos ativos, isso merece um número na sua frente: se trinta pessoas
pedirem conferência na primeira semana, as trinta caem no seu colo. A saída não
é abrir exceção, é ordem de chegada, e a Central de Pendências passa a mostrar
quantos ainda estão na partida a frio. Cada portfólio que você aceita nessa fase
vira um conferente novo, então a fila encolhe sozinha e depressa: depois de dez
aceitos, dez pessoas passam a poder conferir as outras.

### O que o atestado de dois colegas vale

**Sua decisão: dois colegas de acordo fecham sozinhos, sem passar por você.**

Eu havia recomendado o contrário (colegas preparam, você assina em um clique).
Você leu o custo e escolheu assim mesmo, e o plano é este. Fica escrito o que
essa escolha muda, para não ser descoberto depois:

- **A escola passa a afirmar coisas que nenhum adulto da escola olhou.** Quando um portfólio é aceito, o site diz "a escola conferiu" e acende um marco. Nessa decisão, quem conferiu foram dois alunos.
- **Desfazer é mais caro que segurar.** Tirar um marco já concedido de alguém é um gesto que magoa, e ele existe (seção 4), mas ninguém quer usá-lo.
- **A auditoria por amostra deixa de ser opcional e vira peça obrigatória.** No desenho que eu recomendei ela seria um extra; nesta, ela é o único lugar onde um adulto ainda olha. Sem ela, a conferência não tem fundo.

Por isso este plano ganhou uma peça que não teria de outro jeito, e ela entra
**no mesmo degrau** da conferência por pares, nunca depois:

> **A amostra semanal.** Toda semana, o sistema sorteia parte dos portfólios aceitos por colegas e põe na Central de Pendências: *"3 portfólios foram aceitos por colegas esta semana. 1 foi sorteado para você conferir."* São minutos, e é o que mantém a palavra da escola de pé.

E o sorteio não é honesto por acaso: **quem foi apontado pela vigilância do
combinado (seção 4) entra na amostra sempre**, nunca por sorte.

## 7. O que este plano recusa, por escrito

Para não voltar depois disfarçado de novidade:

- **Faixas visíveis, selos de conferente, ranking de quem mais confere.** Quem confere não é troféu.
- **Voto popular decidindo mérito** ("Escolha da Galera"), proibido por escrito na lei. Conferir uma lista de itens objetivos não é isso, e continua valendo.
- **Convite e apadrinhamento.** Aqui ninguém entra por indicação: entra por compra. É um mecanismo bonito para um problema que esta escola não tem.
- **Colega vendo evidência de dinheiro.** Trancado no banco, e fica.
- **Um contador do que fez cada aluno na tela do próprio aluno.** A lei proíbe pontos de personalidade, e "quantas vezes você ajudou" é o vizinho perigoso deles.
