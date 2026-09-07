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
> **2 pessoas querem entrar na escola.** A mais antiga pediu há 3 dias. `Abrir`
>
> **1 portfólio pedindo conferência.** Dois colegas já conferiram e disseram que está de acordo. `Abrir`
>
> **1 prova de marco.** "Primeiros dólares", com prazo até 09/09. Este marco envolve dinheiro, então só você fecha. `Abrir`
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

**Segunda: faixas visíveis fazem mal a uma escola de 30 pessoas.** Você
descreveu Faixa Branca, Azul e Preta. A lei desta casa decidiu o contrário, e o
motivo cabe em uma frase: **quem confere não é um troféu.** O poder de conferir é
uma função técnica, discreta e revogável, sem contador público e sem selo no
perfil. Faixa visível transforma "eu ajudo" em "eu sou mais que você", e numa
turma de trinta pessoas que se conhecem pelo WhatsApp isso vira política em uma
semana. A escola tem 30 nomes na lista, não três mil.

**Terceira: quórum e votação ficam para quando houver gente.** A lei já reserva
"quórum de pares" para a fase de cerca de 150 alunos ativos por semana, e proíbe
por escrito voto popular decidindo mérito. Com 30 pessoas, votação não mede
qualidade: mede quem tem mais amigos. O que entra agora é o degrau anterior, e
ele é suficiente.

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

- **Os dois concordam que está de acordo:** o portfólio sobe na sua fila já marcado como "2 colegas conferiram e disseram que está de acordo", e você fecha em um clique. Ou fecha sozinho, sem você, se for essa a sua decisão (seção 6).
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
- **O sistema marca quando A confere B e B confere A.** É o combinado entre dois amigos, o ataque mais provável numa turma de 30.
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
4. A conferência por pares no portfólio: quem pode conferir, a tela sem nome, o teto semanal, o registro de quem conferiu.
5. A vigilância do combinado: a marca de quando duas pessoas conferem uma à outra, visível só para você.
6. A tela onde você desfaz uma conferência e tira o poder de alguém.

Do degrau 3 sai um passo seu no servidor, de uma linha, para o Admin poder
perguntar ao fórum. As outras três partes já têm a credencial.

**O fórum não entra nesta obra.** A moderação prometida e não construída é uma
tarefa própria, e misturá-la aqui dobraria o tamanho de tudo.

## 6. O que depende de você

Duas decisões, e as duas são suas porque definem o contrato social da escola,
não a engenharia.

**Primeira: quem ganha o poder de conferir?** A recomendação é *quem já teve o
próprio portfólio conferido e aceito pela escola*. É automático (você não
escolhe ninguém, não há favorecido), é justo (só confere quem já passou pela
régua) e prova competência (a pessoa entendeu o critério porque ele foi aplicado
nela).

**Segunda: o que o atestado de dois colegas vale?** A recomendação é *os dois
colegas preparam e você assina em um clique*. Você continua sendo quem afirma o
que a escola afirma, e o trabalho pesado (abrir os links, contar as peças, olhar
os tipos) já vem feito. Com 30 alunos, o custo disso para você é de minutos por
semana, e a escola não abre mão da própria palavra enquanto ainda é pequena.

## 7. O que este plano recusa, por escrito

Para não voltar depois disfarçado de novidade:

- **Faixas visíveis, selos de conferente, ranking de quem mais confere.** Quem confere não é troféu.
- **Votação e quórum aberto.** Só a partir de cerca de 150 alunos ativos por semana.
- **Convite e apadrinhamento.** Aqui ninguém entra por indicação: entra por compra. É um mecanismo bonito para um problema que esta escola não tem.
- **Colega vendo evidência de dinheiro.** Trancado no banco, e fica.
- **Um contador do que fez cada aluno na tela do próprio aluno.** A lei proíbe pontos de personalidade, e "quantas vezes você ajudou" é o vizinho perigoso deles.
