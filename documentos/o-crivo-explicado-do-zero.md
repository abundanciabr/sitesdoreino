---
titulo: O Crivo explicado do zero
publico: false
ordem: 12
---

# O Crivo explicado do zero

Esta página ensina o quiz da Meshcraft para quem nunca construiu um sistema
desse tipo. Sem jargão pela frente. Quando um termo técnico aparecer, ele chega
depois da história que o justifica.

Você não precisa saber programar para acompanhar. Se já programou, vai reconhecer
as peças. Se nunca programou, vai sair daqui capaz de explicar o desenho para
outra pessoa, e de recusar o atalho que parece mais fácil e costuma sair mais
caro.

## Como estudar esta página

Adultos aprendem melhor quando o texto conversa com a vida que eles já viveram.
Por isso cada parte segue o mesmo ritmo:

1. Uma cena do dia a dia (consultório, restaurante, correio, lanchonete).
2. Um desenho da cena.
3. O que o Crivo faz de verdade naquela cena.
4. Uma pausa com pergunta, para você conferir se a analogia grudou.

Não troque de metáfora no meio. A analogia mestra vale do começo ao fim.
Quando uma analogia nova entrar, ela é filha desta, nunca substituta.

**O que você deve conseguir ao terminar**

- Explicar o que o quiz faz, e o que ele recusa fazer, em uma frase.
- Desenhar as cinco peças de qualquer questionário deste tipo.
- Dizer por que a pontuação não pode morar na tela do visitante.
- Contar o que acontece quando Marina aperta "Ver resultado".
- Reconhecer três erros clássicos (endereço dobrado, teste-enfeite, lista
  copiada) e a regra que cada um ensina.

Se no fim você só lembrar da recepcionista, já levou o núcleo.

---

## A analogia mestra: o Crivo é uma recepcionista de clínica

Imagine um consultório. Alguém entra pela porta. A recepcionista não é médica.
Ela não diagnostica doença, não receita remédio, não cobra consulta. Ela faz
três coisas, e só três:

1. Aplica uma fichinha com perguntas ("o que você sente?", "há quanto tempo?").
2. Olha as respostas e decide para qual sala a pessoa vai.
3. Anota o nome e o telefone num caderno e passa a ficha para dentro.

![A recepcionista pergunta, encaminha e avisa. Ela não diagnostica.](figura:recepcionista)

É exatamente isso que o Crivo é. Ele faz perguntas, soma pontos escondidos,
decide um "resultado", mostra um botão para o próximo passo, e avisa o resto
do sistema que uma pessoa nova apareceu. Ele não vende, não cobra, não cadastra
aluno.

Guarde esta frase. Ela é a chave de tudo que vem abaixo:

> **O quiz não sabe o que é um cartão de crédito.**

Essa frase está na constituição da célula, o documento curto que diz o que esta
loja pode e o que não pode. Não é poesia. É uma regra de engenharia, e mais
abaixo fica claro quanto dinheiro e quanta dor de cabeça ela economiza.

**Comparação rápida, do jeito que a gente escolhe profissional no dia a dia**

| Papel | Faz | Não faz |
|---|---|---|
| Recepcionista (o Crivo) | pergunta, classifica, encaminha, avisa | vender, cobrar, matricular |
| Médica (o curso) | ensina, acompanha | receber o cartão na porta |
| Caixa (o checkout) | cobra | decidir se a pessoa "está começando" |

Se você misturar os três papéis numa pessoa só, no primeiro dia parece economia.
No trigésimo, ninguém sabe quem errou.

> **Pausa.** Sem olhar o quadro: quais são as três tarefas da recepcionista?
> Se saiu "perguntar, encaminhar, avisar", a analogia grudou. O resto desta
> página é detalhe dessa frase.

---

## Parte 1. Por que existe uma "célula", e não um site só

### A história do restaurante que virou praça de alimentação

Quando alguém começa um site, escreve tudo num arquivo só. Funciona. Aí chega
a segunda funcionalidade, a terceira, a décima. É como um restaurante onde a
mesma pessoa é garçom, cozinheiro, caixa e faxineiro. Enquanto há três mesas,
ótimo. Na trigésima, um pedido errado na cozinha para o caixa inteiro.

A saída que este projeto tomou é a praça de alimentação. Cada loja tem:

- sua própria cozinha (seu código),
- seu próprio estoque (seu banco de dados),
- sua própria placa na frente (seu endereço na web).

Cada loja dessas aqui se chama **célula**.

![À esquerda, um restaurante só. À direita, a praça: se o pastel pega fogo, o sorvete continua.](figura:restaurante-um-so)

Olhe a lista, só para situar o mapa. Você não precisa decorar os nomes:

```
services/
  quiz/        <- a nossa, a recepcionista
  checkout/    <- cobra o cartão
  leads/       <- guarda as pessoas
  catalogo/    <- sabe quais sites e ofertas existem
  cursos/  alunos/  pagamentos/  forum/  ...
```

A pergunta natural de quem está começando: "não é mais trabalho?". É. E a
razão de valer a pena é uma só: **quando a loja de pastel pega fogo, a de
sorvete continua vendendo**. Se o quiz quebrar, ninguém para de comprar. Se o
quiz precisar de uma mudança grande, mexe-se em uma pasta, e o resto do site
nem fica sabendo.

**Exemplo do dia a dia.** No shopping, o banheiro do cinema fecha para reforma.
Você ainda almoça, ainda compra sapato, ainda pega o estacionamento. O shopping
não é um restaurante gigante. É um prédio de lojas com regras de corredor.

### O quadro de avisos (as fronteiras)

Cada célula tem um documento curto dizendo o que ela pode e o que não pode. O
do quiz diz:

| Campo | Valor | Tradução para o dia a dia |
|---|---|---|
| Pode escrever | a pasta `services/quiz/` | "Você cozinha na sua cozinha" |
| Só leitura | o arquivo do contrato do evento | "Pode ler o cardápio comum, não pode riscar nele" |
| Expõe | páginas em `/quiz/*` | "Sua placa na frente é essa" |
| **Consome** | **nada** | **"Você não liga para ninguém"** |
| Emite | `quiz.completado.v1` | "Você grita uma frase padrão quando termina" |

![O quadro de avisos da loja. A linha que mais importa é Consome: nada.](figura:quadro-avisos)

Aquele **"Consome: nada"** é a decisão mais importante da célula inteira, e
várias esquisitices que vêm adiante existem só por causa dele. Em português de
consultório: a recepcionista não telefona para o laboratório, não pergunta ao
caixa se o cartão passou, não consulta a ficha médica. Ela tem a listinha dela
na parede e o caderno dela na gaveta.

**O preço dessa independência.** Ela funciona mesmo se a central do prédio
estiver fora do ar. O custo é duplicar um dado (o número do site), e duplicar
sem conferidor é dívida. A Parte 3 mostra o conferidor.

> **Pausa.** Se o checkout cair hoje à tarde, o quiz ainda consegue receber
> respostas? Sim, porque ele não liga para ninguém. O aviso pode atrasar. A
> ficha da Marina não some. Essa diferença (atrasar o aviso versus perder a
> ficha) é o coração da Parte 3.

---

## Parte 2. As cinco peças de qualquer quiz, com nome e sobrenome

Pense em fichas de papel numa caixa de arquivo. No código elas têm nomes
próprios. Na vida, você já as viu em todo formulário de triagem.

![Do site ao quiz, das perguntas às faixas de resultado.](figura:cinco-pecas)

Cinco peças, uma de cada vez.

**1. Site.** A plataforma serve mais de um endereço (`meshcraft.top` e outro
que está congelado). O mesmo programa atende os dois, como um prédio comercial
com duas empresas. Quando chega uma visita, a primeira pergunta é "você veio
pela porta de qual empresa?".

**2. Quiz.** O questionário em si. Tem um apelido curto (`slug`) que vira parte
do endereço: slug `crivo` significa `meshcraft.top/quiz/crivo/`.

**3. Question.** A pergunta, com um número de ordem para não embaralhar.

**4. Option.** A alternativa. E aqui vem o detalhe que separa amador de
profissional:

> Cada alternativa tem uma pontuação, **e essa pontuação nunca sai do servidor**.

**5. ResultBand (a faixa).** Uma linha que diz "de tantos a tantos pontos, o
resultado é este, e o botão diz isto e leva para ali".

### Por que os pontos não podem ir para a tela do visitante

**A história do cardápio com o preço no bolso do cliente.** Imagine um
restaurante onde o cliente anota no papelzinho quanto custa cada prato e
entrega no caixa. O primeiro cliente esperto escreve "lagosta: R$ 2,00".
Muitos formulários na internet são feitos assim: mandam os pontos para a tela
do visitante e depois aceitam de volta o que o navegador devolveu. Quem
entende um pouco de navegador muda o número e escolhe o próprio resultado.

![Amador deixa o cliente carregar o preço. Profissional consulta a cozinha de novo.](figura:preco-no-bolso)

Aqui não. A tela recebe só o texto ("Iniciante", "Avançado") e um número de
identificação da alternativa. Os pontos ficam no banco. Quando a resposta
chega, o servidor vai lá **buscar de novo** quanto vale aquela alternativa. O
visitante nunca vê e nunca toca no valor.

**Analogia do supermercado.** O código de barras do produto não é o preço. O
caixa lê o código e pergunta ao sistema quanto custa hoje. Se o cliente
chegasse com uma etiqueta caseira colada, o caixa não aceitaria. O Crivo faz
o mesmo com cada alternativa.

E tem uma segunda tranca, que é fina: o servidor não procura a alternativa em
qualquer lugar. Ele procura **dentro daquela pergunta**. Se alguém tentar
responder a pergunta 1 com uma alternativa da pergunta 3, a resposta é 404.
É o equivalente a conferir se a chave é daquela porta, não só se é uma chave.

**Exemplo concreto, com os números reais do Crivo**

| Pergunta | Alternativa | Pontos (escondidos) |
|---|---|---|
| Qual é o seu maior desafio hoje? | Não sei por onde começar | 0 |
| Qual é o seu maior desafio hoje? | Já comecei mas travei no meio | 5 |
| Qual é o seu maior desafio hoje? | Quero acelerar o que já funciona | 10 |
| Quanto tempo você tem por semana? | Menos de 2 horas / 2 a 5 / mais de 5 | 0 / 5 / 10 |
| Como descreveria sua experiência? | Iniciante / Intermediário / Avançado | 0 / 5 / 10 |

Três perguntas, máximo 30 pontos. As faixas cortam assim:

| Pontos | Resultado que a Marina lê | Botão que ela vê |
|---|---|---|
| 0 a 9 | Você está começando | Começar pelo básico |
| 10 a 19 | Você já tem base | Destravar o próximo passo |
| 20 a 30 | Você está pronto para escalar | Quero escalar agora |

Marina nunca lê "13 pontos". Diagnóstico é conversa. Nota é boletim. O número
existe, mas para o dono do negócio.

### A lição do beco sem saída

Esta parte é uma pequena história real do projeto, e ensina mais sobre produto
do que sobre código.

A tela de resultado nasceu sem botão. A pessoa respondia tudo, entregava e-mail
e telefone, lia "Você está começando", e acabou. Fim. Nenhum caminho. Isso tem
nome em marketing: **beco sem saída**. Você gastou o interesse da pessoa no
momento de maior atenção dela e não ofereceu nada.

![Sem botão, a visita termina na parede. Com botão da faixa, ela se reconhece no convite.](figura:beco-e-botao)

A correção foi pôr um botão. A sutileza da decisão: **o botão é da faixa, não
da tela**. Quem está começando e quem está pronto para escalar não recebem o
mesmo convite. Hoje os três levam ao mesmo lugar (a oferta padrão do site), e
isso é honesto: o site tem uma oferta só. O que muda é a **palavra**, que é o
que faz a pessoa se reconhecer. É a diferença entre o vendedor que diz "quer
comprar?" e o que diz "pelo que você me contou, eu começaria por aqui".

**E uma regra de banco de dados que vale ouro.** O sistema recusa gravar uma
faixa que tenha destino sem rótulo, ou rótulo sem destino. Destino sem rótulo
é um link invisível. Rótulo sem destino é um botão que não leva a lugar nenhum.
A regra está no **banco**, não na tela, e a razão está escrita no código numa
frase que vale decorar:

> "tela não é lugar de descobrir que o dado está pela metade"

Isso é uma técnica geral: quando uma regra é inviolável, coloque-a no ponto
mais fundo possível. O banco é o cofre. Uma regra escrita só na tela é um
aviso colado na porta. Uma regra no banco é a fechadura.

> **Pausa.** Imagine que você montou um quiz de "qual curso combina com você"
> e deixou os pontos no JavaScript da página, "só para ir mais rápido". Qual
> é o equivalente da lagosta a R$ 2,00 nesse desenho? Se a resposta foi "a
> pessoa escolhe o resultado que quiser", você já pensa como a casa pensa.

---

## Parte 3. A jornada completa, passo a passo

Agora acompanhe uma pessoa de verdade. Chame ela de Marina.

![Marina clica, responde, envia e vê o resultado. No envio, o prédio inteiro pode ouvir.](figura:jornada-marina)

O mesmo filme, visto pelos quatro papéis ao mesmo tempo:

```
  Marina                 Navegador              Servidor do quiz        Resto da plataforma
    |                       |                         |                          |
 1. clica no link --------->|                         |                          |
    |                       |-- GET /quiz/crivo/ ---->|                          |
    |                       |                    [quem é o site?]                |
    |                       |<---- formulário --------|                          |
 2. responde 3 perguntas    |                         |                          |
    escreve e-mail          |                         |                          |
 3. clica em "Ver resultado"|                         |                          |
    |                       |-- POST com respostas -->|                          |
    |                       |                    [confere o selo CSRF]           |
    |                       |                    [soma pontos NO SERVIDOR]       |
    |                       |                    [acha a faixa]                  |
    |                       |                    [grava tudo + bilhete]          |
    |                       |<-- "vá para o resultado"|-- grita o evento ------->|
 4. vê o resultado e o botão|                         |                          |
                                                                    [leads guarda Marina]
```

Não tente decorar as setas. Elas existem para você voltar aqui quando uma peça
parecer solta. Abaixo, cada número vira história.

### Passo 1. "Quem é o site?"

A primeira coisa que acontece não é mostrar a página. É descobrir de qual site
aquela visita veio, olhando o endereço que ela digitou.

![O porteiro pergunta a empresa. Host desconhecido não sobe. Não existe andar padrão de consolo.](figura:porteiro)

**Analogia.** É o porteiro do prédio comercial perguntando "você vem para qual
empresa?" antes de deixar subir. Se o nome não está na lista, a visita não
sobe. Aqui é igual: host que não está cadastrado recebe 404. Nunca existe um
"site padrão" de consolo, porque um site padrão silencioso é como o porteiro
mandar a visita para qualquer andar. Parece gentileza. É confusão garantida.

**A esquisitice deliberada.** As outras células perguntam ao `catalogo` (a
central de informações do prédio) quem é o site. O quiz **não pergunta a
ninguém**: ele tem uma listinha própria, colada na parede da sua sala. Isso é
um desvio consciente da receita da casa, registrado com os motivos em
`services/quiz/LICOES.md`.

Vantagem: o quiz funciona mesmo que a central esteja fora do ar. Independência
total.

Preço: **duas listas podem divergir**.

![Duas listas com o mesmo host. Se o número divergir, tudo responde 200 e os leads não aparecem.](figura:duas-listas)

O número de identificação do site precisa ser exatamente o mesmo nas duas. Se
divergir, tudo continua respondendo 200, nenhum erro aparece, e os leads
simplesmente não aparecem do outro lado. É o tipo de falha mais cara que
existe: a silenciosa.

É por isso que o abastecimento em produção tem um passo inteiro só para
conferir isso **nos dois sentidos** ("este host já está com outro número?" e
"este número já está com outro host?"). A lição transferível: **quando você
aceita duplicar um dado, você assume a obrigação de criar o conferidor**.
Duplicação sem conferidor não é atalho, é dívida.

### Passos 2 e 3. A trava do formulário (CSRF)

Aqui tem a melhor história do arquivo, e ela ensina algo que vale para qualquer
sistema.

O formulário sempre teve uma linha de código que gera um "selo de segurança"
invisível, chamado token CSRF. Parecia protegido. **Só que o guarda que
confere o selo nunca tinha sido contratado.** A linha existia, o selo era
emitido, e ninguém olhava.

**O que é CSRF, em português.** Imagine que o seu banco aceite ordens escritas
em qualquer papel, desde que venham do seu envelope. Um golpista monta um site
com uma imagem bonitinha, e por trás um formulário escondido que envia uma
ordem ao banco usando o seu envelope, porque o seu navegador anexa o envelope
automaticamente. O selo CSRF resolve isso: o banco entrega um número único
junto com o formulário verdadeiro e só aceita ordens que tragam aquele número
de volta. O site do golpista não tem como saber o número.

![O envelope do navegador vai sozinho. O selo da recepção é o número que o golpista não tem.](figura:selo-csrf)

Sem o guarda, qualquer página da internet podia disparar respostas para o
quiz, gravando e-mails e telefones inventados e disparando o evento de "lead
novo" para pessoas que nunca existiram. Era a única página pública do projeto
nessa situação. Hoje o guarda está contratado.

Dois detalhes que valem como técnica geral:

**O cookie tem nome próprio: `quiz_csrf`.** No mesmo domínio moram várias
células. Se duas usarem o nome de fábrica, elas escrevem por cima uma da outra
e qual delas vence passa a depender de regrinhas obscuras do navegador.
**Analogia:** condomínio onde todo mundo escreve "correspondência" na caixa de
correio. Bota o número do apartamento.

**E um teste que se enganava sozinho.** Esta é para quem quer aprender a
testar. O teste de segurança original usava a ferramenta padrão de teste, que
**vem com a conferência de selo desligada**. Ou seja: o teste passava verde
com a proteção ligada e passava verde com a proteção desligada também. Ele
media nada e dava a sensação de tudo certo.

![Se o teste passa nas duas situações, ele é enfeite. Sabote de propósito.](figura:teste-enfeite)

> **Lição:** um teste que passa nas duas situações não é um teste, é um
> enfeite. A forma de descobrir isso chama-se sabotagem: quebre o código de
> propósito e veja se o teste fica vermelho. Se ficar verde, o teste é
> decoração.

Esse mesmo problema apareceu numa segunda forma, ainda mais sutil. Um teste
configurava uma opção e depois conferia que a opção estava configurada. Ou
seja, media se o programa obedece a ordem que o próprio teste tinha acabado
de dar. É como perguntar "você está aí?" para o próprio eco.

### Passo 3, o coração: uma transação só

Este é o conceito mais importante de todo o texto, então vamos com calma.

Quando Marina envia, três coisas precisam acontecer:

1. Guardar a resposta dela.
2. Guardar o bilhete que avisa o resto do sistema ("apareceu um lead novo").
3. Entregar esse bilhete.

A armadilha clássica de quem está começando é fazer 1 e 3 direto: salva no
banco e já manda o aviso. Parece óbvio, e está errado, porque as duas coisas
podem falhar em momentos diferentes.

- Se o aviso for enviado e o banco falhar depois: existe um lead avisado que
  não existe.
- Se o banco gravar e o aviso falhar: Marina respondeu, entregou o e-mail, e
  **ninguém nunca vai saber**. Lead perdido, sem erro, sem log, sem nada.

A solução usada aqui se chama **outbox**, que quer dizer literalmente "caixa
de saída".

**Analogia da agência dos correios.** Você não sai correndo com a carta na
mão. Você escreve a carta e coloca na caixa de saída, **no mesmo movimento em
que arquiva a cópia**. Depois, um carteiro passa e leva o que estiver na
caixa. Se o carteiro não vier hoje, a carta continua lá. Ela não some.

![Arquiva a ficha e o bilhete juntos. O carteiro leva depois. Se ele atrasar, a carta continua.](figura:caixa-de-saida)

No código, em uma frase:

```
com uma transação (tudo ou nada):
    grava a resposta de Marina
    grava o bilhete na caixa de saída
    (as duas linhas juntas: ou as duas existem, ou nenhuma existe)

depois que a transação fecha:
    tenta entregar o bilhete agora mesmo  <- carteiro expresso
```

E tem um segundo carteiro, que passa **de minuto em minuto**, recolhendo
qualquer coisa que tenha ficado para trás. Se o serviço de entrega estiver
fora do ar às 14h03, o bilhete sai às 14h05. O contêiner que faz isso se chama
`quiz-relay` e roda o dia inteiro.

**A ordem das duas linhas, que parece boba e não é.** O carteiro faz:

```
1. entrega o bilhete
2. marca "entregue"
```

Nunca o contrário. Se marcar antes e a entrega falhar, o bilhete some para
sempre, marcado como entregue, sem nada acusando. Do jeito certo, o pior caso
é entregar duas vezes, e quem recebe sabe reconhecer repetido porque todo
bilhete tem um número único.

> **A regra geral, que serve para a sua vida inteira de programação:** entre
> "posso perder" e "posso repetir", escolha sempre repetir. Perda silenciosa
> é irrecuperável. Repetição é um problema que se resolve com um número de
> série.

**Comparação com o cotidiano.** Você prefere o banco dizer "talvez o PIX tenha
saído duas vezes" (e você confere o extrato) ou "talvez o PIX não tenha saído
e ninguém vai te avisar"? Ninguém escolhe a segunda. Sistemas também não
deveriam.

### Passo 4. A tela de resultado

Marina é redirecionada para um endereço assim:

```
https://meshcraft.top/quiz/crivo/resultado?lead=8f3c2a91-...
```

Aquele pedaço depois do `?` não é rastreamento. **É a identidade do resultado.**
É o número da senha da lanchonete: sem ele, o balcão não sabe qual pedido
entregar. Quem abre a página sem o número recebe 404.

![O ?lead= é a senha da lanchonete. Sem o número, o balcão não entrega o pedido.](figura:senha-lanchonete)

Por que fazer assim, em vez de simplesmente mostrar o resultado na mesma
resposta do envio? Porque de outro jeito, se Marina apertar F5, o navegador
reenvia o formulário e grava tudo de novo. Todo mundo já viu aquele aviso
"deseja reenviar os dados?". Esse padrão de resolver isso chama-se
**POST-redirect-GET**: recebe, guarda, e manda o navegador buscar a página
numa segunda visita limpa, que pode ser recarregada à vontade.

E note o que a tela **não** mostra: a pontuação. Marina lê "Você já tem base",
não "13 pontos".

> **Pausa.** Feche os olhos e conte a Marina: o que o servidor faz, em ordem,
> quando ela aperta o botão? Se saiu "confere o selo, soma no servidor, acha
> a faixa, grava ficha e bilhete juntos, tenta entregar, manda ela para a
> tela do resultado", você pegou o coração. O resto é vocabulário.

---

## Parte 4. Três histórias de bug que ensinam mais que qualquer manual

Estas três estão documentadas em `services/quiz/LICOES.md`, escritas pelos
próprios agentes que erraram. Ler erro alheio é o atalho mais barato de
aprendizado que existe.

### História 1. O endereço dobrado, ou "quem tira o prefixo?"

Na frente da praça de alimentação existe um porteiro que direciona: "tudo que
começar com `/quiz` vai para a loja do quiz". Esse porteiro chama-se Traefik.

A pergunta que ninguém fez: **o porteiro apaga o `/quiz` do pedido antes de
entregar, ou entrega inteiro?**

Ele entrega inteiro. Quem apaga é o programa lá dentro, um instante antes de
olhar o endereço. Como ninguém sabia disso, escreveram as rotas internas
**também** com `quiz/` na frente. Resultado: o único endereço que funcionava
era o dobrado.

![O endereço divulgado dava 404. O endereço dobrado, que ninguém anunciava, funcionava.](figura:endereco-dobrado)

```
meshcraft.top/quiz/quiz/crivo/     <- funcionava (e ninguém divulgava)
meshcraft.top/quiz/crivo/          <- 404 (e era o que se divulgava)
```

**E por que nenhum teste pegou?** Porque todos os testes mediam por dentro,
onde os dois erros se cancelavam. É o clássico: testar o motor na bancada,
nunca o carro na rua. Ficou um mês assim.

> **Lição:** teste pelo menos um caminho **exatamente como o usuário entra**,
> de fora. Um teste de superfície pública vale por dez de laboratório.

**Analogia.** Você prova o sabor do bolo na tigela e declara a festa pronta.
Os convidados chegam e a forma está vazia, porque ninguém ligou o forno. A
tigela estava deliciosa. A festa não existia.

### História 2. O curinga que quase virou tela de erro

Consertar o endereço criou um efeito colateral bonito de entender. A rota do
formulário virou "qualquer palavra única":

```
/<qualquer-coisa>/   ->  procura um quiz com esse apelido
```

Só que `/healthz/` (a sonda que verifica se o serviço está vivo) e `/static/`
(imagens e CSS) também são "qualquer palavra única". E esses dois caminhos
são justamente os que o porteiro interno **pula**, não perguntando de qual
site vieram.

![A rota curinga atende o quiz de verdade e, sem guarda, tentaria atender a sonda e os estáticos.](figura:curinga)

Consequência: a página tentava ler uma informação que ninguém tinha
preenchido, e onde antes havia um 404 educado passaria a haver um erro de
servidor 500.

**Analogia:** você instala uma secretária eletrônica que atende "qualquer
número que ligar". Aí percebe que o interfone da portaria também é um número,
e a secretária tenta perguntar o CPF do entregador de pizza.

A correção cabe em duas linhas: se a informação do site não veio, responda
404, porque não existe quiz chamado "healthz".

### História 3. O quiz publicado que ninguém alcançaria

Este é o favorito de quem revisa, porque mostra o que é uma boa revisão.

Depois do conserto acima, alguém percebeu: e se um dia alguém criar um quiz
com o apelido `healthz`? Ele moraria em `/healthz/`, cairia na exceção, e
responderia 404 **para sempre**. Um quiz publicado, existente no banco,
cobrado no relatório, e absolutamente inalcançável. Sem nenhum aviso no
momento da criação.

A correção: o comando de criação passou a recusar esses apelidos. E aqui vem
o detalhe fino, que é o que separa bom de excelente.

A lista de apelidos proibidos **não foi digitada à mão**. Ela é lida direto
de onde a exceção está definida. Por quê? Porque a comparação usa "começa
com", e portanto a exceção é mais larga do que os dois nomes sugerem:
`healthz2` e `healthzinho` também começam com `healthz` e também seriam
engolidos.

![healthz, healthz2 e healthzinho caem na mesma boca. A lista copiada à mão erraria a borda.](figura:slug-proibido)

E o texto do projeto registra que a primeira versão do teste **listava
`healthzinho` como apelido honesto**. Foi o próprio código, ao recusá-lo, que
corrigiu o teste. Ou seja: uma verificação escrita à mão teria errado
exatamente a mesma borda que o humano errou.

> **Lição:** nunca copie uma lista para um segundo lugar. Leia do primeiro.
> Duas listas escritas à mão divergem no dia em que alguém mexer numa e
> esquecer da outra, e esse dia sempre chega.

**Estória paralela do cotidiano.** A lista da festa no papel da cozinha e a
lista no grupo do WhatsApp. Na hora do bolo, falta um nome. Ninguém mentiu.
As duas listas envelheceram em ritmos diferentes.

> **Pausa.** Das três histórias, qual você repetiria amanhã se estivesse
> com pressa? A mais tentadora costuma ser a primeira (testar só por dentro)
> e a terceira (copiar a listinha "para ir mais rápido"). As duas são o mesmo
> vício: medir o eco em vez da rua.

---

## Parte 5. Como um quiz nasce em produção (e por que isso é um botão, não um terminal)

Uma confusão comum de quem está começando: **subir o programa e povoar o
programa são coisas diferentes.**

**Analogia:** inaugurar a loja e abastecer a prateleira. O deploy inaugura a
loja: as luzes acendem, a porta abre, a plaquinha de "aberto" funciona. Mas a
prateleira está vazia. Ninguém coloca mercadoria por você.

![Loja inaugurada com prateleira vazia não é produto. Loja abastecida é.](figura:loja-vazia)

Foi exatamente o que aconteceu. A célula quiz estava no ar. A sonda
`/quiz/healthz` respondia que o serviço estava vivo, tudo verde, painel
feliz. E o endereço do quiz respondia 404, porque **não existia um único quiz
cadastrado**. O programa estava perfeito e o produto não existia.

Hoje o abastecimento é um botão no GitHub. Alguém escolhe o host e dispara. O
script na máquina de produção faz, em seis passos:

| Passo | O que faz | Por que importa |
|---|---|---|
| 1 | Confere se os serviços estão de pé | Não adianta abastecer loja fechada |
| 2 | Pergunta ao catálogo o número e a oferta do site | Fonte única da verdade |
| 3 | Confere o cadastro local **nos dois sentidos** | Impede a divergência silenciosa |
| 4 | Pergunta ao comando qual é a assinatura dele | O comando é de outro dono e pode mudar |
| 5 | Semeia | Pode rodar mil vezes, não duplica |
| 6 | **Confere no banco, por outro caminho** | O eco do script não é prova |

![Seis passos do abastecimento. O último não acredita no eco da receita.](figura:seis-passos)

Três coisas aí merecem destaque para quem está aprendendo.

**"Idempotente"** é a palavra difícil para "rodar de novo não estraga". Como
o botão do elevador: apertar cinco vezes chama um elevador, não cinco. Isso
transforma um procedimento assustador ("e se eu apertar duas vezes?") em algo
que qualquer pessoa pode disparar sem medo.

**O passo 6 existe por causa de um erro real.** O log de um script ecoa os
comandos que ele contém, e alguém já leu esse eco como se fosse resultado. É
como ler a receita em voz alta e concluir que o bolo está pronto. Então a
conferência final é feita por outro caminho, contando as linhas no banco,
filtradas pelo site pedido, provando de quebra que o site vizinho não foi
tocado.

**O passo 4 é raro e elegante.** O script pergunta ao comando "quais
argumentos você exige hoje?" em vez de assumir. Se o comando ganhar uma
exigência nova que o script não sabe preencher, ele **para antes de gravar
qualquer coisa** e diz quem precisa consertar o quê. Falhar cedo e barulhento
vale mais que publicar torto e calado.

> **Pausa.** "O painel está verde" prova que o produto existe? Não. Prova que
> a loja está de pé. Produto é prateleira. Essa distinção sozinha evita uma
> tarde inteira de caçada.

---

## Parte 6. O que acontece depois que o quiz termina

O quiz grita uma frase padronizada. Literalmente uma mensagem com formato
fixo. Quem fala não sabe quem está escutando, e não se importa.

![O quiz grita no rádio do prédio. Quem quiser escuta. Quem nascer amanhã também pode escutar, sem mexer no quiz.](figura:radio)

Isso se chama arquitetura orientada a eventos, e o ganho é enorme: para o
quiz, tanto faz se há um ouvinte, três ou nenhum. Adicionar um ouvinte novo
amanhã **não exige mexer no quiz**.

**Analogia estendida da clínica.** A recepcionista não entra nas salas
avisando cada médico. Ela anuncia no corredor, na frase combinada: "Marina,
triagem intermediária, chegou agora". Quem precisa ouve. Quem não precisa
segue a vida.

Esse formato fixo é um **contrato**. É um documento que não pertence ao quiz
(ele só pode ler, não escrever), justamente porque mudar o formato quebraria
todo mundo que escuta. Mudar contrato tem cerimônia própria.

A frase, em português de gente, traz: de qual site, qual quiz, qual faixa, a
pontuação, o e-mail da Marina, e de onde ela veio (por exemplo, Instagram).
Em formato de rádio, fica assim:

```
{
  "event": "quiz.completado",
  "version": 1,
  "event_id": "um número único desta mensagem",
  "occurred_at": "quando aconteceu",
  "data": {
    "site_id": "de qual site",
    "quiz_slug": "crivo",
    "result_key": "intermediario",
    "score": 13,
    "lead": { "email": "marina@...", "name": "Marina", "phone": "..." },
    "utm": { "source": "instagram" }
  }
}
```

Quem escuta hoje:

| Ouvinte | O que faz |
|---|---|
| `leads` | Cria ou atualiza a pessoa, marca a origem como `quiz:crivo`, e adiciona na linha do tempo dela |
| `gamificacao` | Escuta e **não faz nada**, de propósito |

Esse "não faz nada" é honesto e merece explicação. A gamificação dá pontos de
experiência por ações. Ela até tem uma regra chamada `quiz-aprovado` já
cadastrada. Mas o contrato do quiz identifica a pessoa **por e-mail**, e a
gamificação só sabe trabalhar com número de aluno. Ela não sabe fazer a
tradução.

O que o código faz então? Escreve no log, em texto claro, que recebeu o
evento, que não vai creditar, e por quê. Isso é maduro. O caminho errado
seria fingir que trata e não tratar: alguém ligaria a regra um ano depois,
os pontos não viriam, e a caçada duraria uma tarde.

> **Lição:** limite conhecido e escrito é documentação. Limite silencioso é
> bug esperando a hora.

**Estória do cotidiano.** O técnico do ar-condicionado cola um papel na
máquina: "esta unidade não gela o quarto do fundo, falta duto". Todo mundo
reclama do quarto, lê o papel, e para de caçar fantasma. Sem o papel, cada
visita nova começa a investigação do zero.

---

## Parte 7. O retrato honesto de hoje

Quatro coisas para você ter clareza do que está e do que não está pronto. Esta
página explica o desenho. O estado ao vivo (se a página abre, se o menu aponta
para ela) mora no site e no painel, não aqui. Documento que copia número vira
mentira no dia seguinte.

![Quatro cartões do retrato honesto: um quiz só, respostas sem tela, páginas-ilha, loja fora do mapa.](figura:retrato-hoje)

**1. Existe um único quiz, e ele é o mesmo em todos os sites.** As três
perguntas, os pontos e as três faixas estão **escritos no código**, não
cadastrados numa tela. Não existe editor de quiz. Quiz diferente hoje exige um
programador abrindo um PR.

Isso não é defeito, é estágio. O caminho normal é exatamente esse: primeiro
faça funcionar com o conteúdo cravado, depois, quando a necessidade de variar
aparecer de verdade, construa o editor. Construir o editor antes de saber se
alguém quer um segundo quiz é gastar semanas para resolver um problema
hipotético.

**2. As respostas ficam guardadas e ninguém as lê.** Cada resposta completa
vira um registro imutável, com as alternativas, a pontuação e as UTMs. Existe
tudo isso guardado e **nenhuma tela mostra**. Se você quiser saber "quantas
pessoas caíram na faixa avançado este mês", hoje não há onde ver.

**3. As duas páginas não têm o menu nem o rodapé do site.** Elas são HTML
solto, com o estilo escrito dentro do próprio arquivo. A pessoa que chega no
quiz está numa ilha, sem barra de navegação para voltar ao site. Isso ficou
registrado como dívida conhecida quando a página ainda não era alcançável. A
justificativa da época venceu no dia em que a página passou a ser alcançável.

**4. A loja pode estar aberta e fora do mapa.** Ter o endereço
`meshcraft.top/quiz/crivo/` respondendo não é a mesma coisa que ter um link
no menu. Uma loja iluminada dentro de um shopping onde ela não aparece no
mapa continua sendo uma loja que quase ninguém encontra. Quem decide o menu
é a tela `/admin/menu/`, com sessão logada.

---

## Treino. Você explica agora, sem olhar

Fecha a página um instante (ou só desce os olhos) e tenta, em voz alta:

1. O Crivo é médica, caixa ou recepcionista? Por quê?
2. Onde moram os pontos, e o que acontece se morarem na tela?
3. Por que gravar a ficha e o aviso na mesma transação?
4. O que um teste precisa fazer para não ser enfeite?
5. Qual é a diferença entre subir o programa e abastecer o programa?

Se travou em alguma, volte só na parte dela. Aprendizagem de adulto é volta
cirúrgica, não reler tudo.

---

## O resumo em uma página

Se você guardar só isto, já foi um bom investimento de leitura:

![As dez lições do Crivo, para levar embora.](figura:dez-licoes)

1. **O quiz é uma recepcionista, não uma médica.** Pergunta, classifica,
   encaminha, avisa. Não vende, não cobra, não cadastra.
2. **Pontuação mora no servidor.** Nunca deixe o cliente carregar o próprio
   preço.
3. **Regra inviolável mora no banco**, não na tela. Tela não é lugar de
   descobrir dado pela metade.
4. **Caixa de saída (outbox).** Grave a mensagem na mesma transação do fato,
   e deixe um carteiro entregar depois. Entre perder e repetir, escolha
   repetir.
5. **Um teste que passa nas duas situações é enfeite.** Sabote de propósito
   e veja se fica vermelho.
6. **Teste pelo menos um caminho exatamente como o usuário entra.** O erro
   do endereço dobrado durou um mês porque só se media por dentro.
7. **Nunca copie uma lista para um segundo lugar.** Leia do primeiro.
8. **Subir não é abastecer.** Um serviço verde com prateleira vazia é um
   produto que não existe.
9. **Falhe cedo e alto.** Parar antes de gravar vale mais que publicar
   torto e calado.
10. **Escreva os limites que você conhece.** Silêncio vira caçada de uma
    tarde, um ano depois.

---

## Se você for montar o seu

Três gestos concretos, na ordem em que esta casa aprendeu doído:

1. Escreva primeiro a frase "isto não faz X". A do Crivo é sobre cartão de
   crédito. A sua pode ser outra. Sem essa frase, o sistema engorda no
   primeiro aperto.
2. Coloque a pontuação no cofre (o banco) e a regra do botão no cofre
   também. Tela mente. Banco recusa.
3. No primeiro teste de segurança, sabote o código de propósito. Se o teste
   continuar verde, você ainda não tem teste.

O Crivo que você acabou de estudar é essa disciplina aplicada a um
questionário de três perguntas. O tamanho é pequeno de propósito. A disciplina
é o que escala.
