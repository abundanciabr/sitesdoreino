# PLANO | a área de negociação: o Mural e a Proposta

publico-para-ia: true

**Escrito em 04/09/2026**, a pedido do mantenedor, que descreveu com as
próprias palavras *"uma área de negociação tipo contratação de freelancer
dentro do site, onde pessoas possam criar projetos / solicitar serviços e os
alunos possam pegar os projetos / serviços, e aí teremos a questão dos prazos,
regras, disputas, e etc"*.

Este documento **não é um plano novo para um produto novo**. Ele é a **emenda
de desenho** da Fila do Primeiro Dólar, que o mantenedor aprovou um dia antes
(`DECISAO-fila-do-primeiro-dolar.md`, registro `20260904-006`). A lei aprovada
proibia de propósito duas das três coisas que ele pediu agora, e mandava, no
critério de morte 1, parar e reabrir a decisão com ele. Foi o que se fez: as
três perguntas foram feitas em caixa estruturada em 04/09/2026, e as respostas
estão no §1.

**Onde este documento manda:** no Mural, na Proposta e no que elas mudam. Tudo
o mais continua valendo como está escrito na lei e no plano mestre. Onde este
documento e a lei divergirem, **este vence a partir de 04/09/2026**, e a lei
carrega a emenda no seu §2.

---

## §1 As três respostas do mantenedor (04/09/2026)

| Pergunta | Resposta dele | O que ela revoga |
|---|---|---|
| Como o aluno pega o trabalho? | **Os dois, em ordem.** A fila garante o primeiro trabalho de cada aluno; depois da primeira entrega aprovada, ele passa a ver o Mural e pega o que quiser | Nada da fila. Acrescenta o Mural, que não existia |
| Tem negociação de preço e prazo? | **Negociação em tudo.** Todo projeto abre conversa de preço e prazo entre cliente e aluno | O preço de tabela fechado (§5.1 do plano) e o princípio 5 na parte em que ele promete "peça, pague, receba" |
| Quem pode abrir projeto agora? | **Só a escola por enquanto.** A escola abre, o aluno faz, a escola paga por fora do site | Nada. É o que a lei já dizia até a Fase 3 |

A recomendação escrita para a segunda pergunta era "fixo nos pequenos,
negociado nos grandes". **Ele escolheu a opção mais completa, informado do
preço**, que estava escrito na própria opção: um aluno recém-formado negocia
sozinho com um comprador profissional, e é assim que iniciante aceita trabalho
barato demais. O §7 deste plano é a resposta de engenharia a esse risco, e ela
não é "não construir": é construir com piso, com referência e com o professor
olhando.

---

## §2 O que muda, em uma tela

Antes (lei aprovada em 03/09/2026):

```
cliente escolhe um cartão de preço fixo  →  paga  →  entra na fila
  →  a plataforma oferece a UM aluno  →  ele aceita ou passa  →  produz
```

Depois desta emenda:

```
cliente descreve o projeto (preço de referência à vista, não final)
  →  o projeto entra numa das duas pistas:

     PISTA 1 — A FILA (nível Iniciante)
       a plataforma oferece a UM aluno por vez, quem entregou menos primeiro

     PISTA 2 — O MURAL (nível Intermediário e Avançado)
       todos os alunos que já entregaram veem; quem pega primeiro, leva

  →  o aluno que está com a vez manda uma PROPOSTA (valor, prazo, o que entrega)
  →  o cliente aceita, ou devolve uma contraproposta
  →  rodadas limitadas; ninguém fica negociando para sempre
  →  ACORDO fechado congela valor, prazo e entregáveis
  →  paga (hoje: a escola registra o pagamento feito por fora)
  →  produz  →  entrega  →  revisão  →  aprovação
```

Três coisas nascem: **o Mural**, **a Proposta** e **o Acordo**. Uma coisa se
move de lugar: **o pagamento**, que deixa de ser a porta de entrada e passa a
acontecer depois do acordo, porque não se pode cobrar um valor que ainda não
foi combinado.

---

## §3 O Mural

### 3.1 A regra que o faz existir sem quebrar a promessa da fila

A fila existe por um motivo escrito na primeira linha do plano mestre:
**ninguém contrata quem nunca entregou, e ninguém entrega sem ser
contratado.** Um mural aberto desde o primeiro dia recria exatamente esse
problema, porque um cliente escolhendo entre dez alunos escolhe o que já tem
portfólio, e o aluno sem portfólio nunca começa.

A resposta do mantenedor resolve isso com uma ordem, e a ordem vira três
regras que não precisam de nenhuma invenção nova, porque a elegibilidade da
lei já as continha:

1. **Aluno com zero entregas aprovadas não vê o Mural.** Ele está na fila, e a
   fila serve exatamente a ele, porque a ordem dela é "quem entregou menos vai
   primeiro".
2. **Projeto de nível Iniciante nasce na fila.** Só chega ao Mural pela
   chamada aberta que já existe na lei: 24 horas sem ninguém aceitar.
3. **Projeto de nível Intermediário ou Avançado nasce no Mural**, porque a
   elegibilidade da lei já exige, para eles, 1 e 5 entregas aprovadas. Quem
   pode pegá-los, por definição, já entregou.

O efeito é o que ele pediu, em ordem: **a fila garante o primeiro dólar de
todo formado; o Mural é para onde ele vai depois.** E é exatamente a frase que
o plano mestre já usava sem nunca ter desenhado: *"o marketplace é uma rampa,
não um destino"*.

**A quarta regra, que fecha o buraco dos primeiros meses.** Nos primeiros
meses ninguém terá entrega aprovada, então o Mural nasce sem ninguém para
olhá-lo. Um projeto de nível Intermediário ou Avançado aberto nesse período
ficaria parado para sempre, sem ninguém elegível e sem ninguém sabendo. Então:
**projeto que passa 24 horas no Mural sem nenhum aluno elegível disponível vai
para o plantão**, com a razão escrita ("ninguém elegível ainda"). O professor
decide: reclassificar para Iniciante, segurar, ou avisar o cliente. É o mesmo
relógio e o mesmo destino que a lei já dava à encomenda encalhada na fila
(§6.4), e vale a mesma regra de sempre: **nada nesta plataforma pode ficar
parado sem alguém saber.**

### 3.2 O Mural não é leilão, e isto é desenho, não descuido

O mantenedor pediu que os alunos possam **pegar** os projetos. Pegar não é dar
lance. A diferença decide o produto inteiro, então está escrita aqui:

**Um projeto do Mural fica reservado a um aluno por vez.** O aluno clica em
"Pegar", ganha a vez com um relógio visível, e é ele quem negocia. Se a
negociação falhar ou o relógio vencer, o projeto volta ao Mural para o
próximo. **Nunca existem duas propostas vivas para o mesmo projeto.**

Por que não leilão, mesmo agora que a negociação existe:

- Leilão entre alunos da mesma escola é uma corrida para baixo. Quem ganha é
  quem cobra menos, e a escola estaria construindo a máquina de rebaixar o
  próprio preço do próprio aluno.
- Comparar propostas é comparar pessoas, e comparar pessoas é o ranking e a
  nota pública, que continuam fora por decisão dele e por critério de morte.
- O cliente escolher entre alunos é o item que a lei aprovada proíbe na
  primeira linha dos princípios, e ele **não** revogou esse item: revogou o
  preço fixo e a ausência de mural, não a escolha de freelancer pelo cliente.

Se um dia ele quiser leilão, é uma decisão nova, e o §9 diz onde ela entra.

### 3.3 O que o aluno vê

Uma lista, celular primeiro, com um cartão por projeto: título, nível, prazo
desejado pelo cliente, preço de referência, resumo do briefing e o botão
**Pegar**. Filtro por nível e por tipo de peça. Nenhum nome de cliente,
nenhum contato, nenhuma foto de perfil de ninguém.

Ordem da lista: **os mais antigos primeiro**. É a única ordem que existe, e
ela é deliberadamente burra: qualquer ordem "inteligente" (destaque, peso,
relevância) é a segunda regra de ordem que o critério de morte 2 proíbe.

### 3.4 O que o cliente vê

Nada de diferente. O cliente descreve o projeto e acompanha uma linha de
rastreio. Ele **não** sabe se o projeto foi para a fila ou para o Mural, e não
escolhe a pista. Isso preserva o princípio 5 na parte que continua valendo: a
complexidade é nossa, não dele.

---

## §4 A Proposta

### 4.1 Negociação por formulário, nunca por conversa

Esta é a peça mais delicada do plano, porque o invariante de segurança
**[INV-ENC-S1]** continua valendo e o mantenedor não o revogou: *não existe
texto livre trocado entre cliente e aluno fora dos campos estruturados, e
todos são visíveis ao plantão.*

A saída não é enfraquecer o invariante. É perceber que **negociar não é
conversar**: negociar é trocar propostas. Então a negociação desta plataforma
tem a forma de um formulário que vai e volta, com rodadas contadas.

Uma **Proposta** tem:

| Campo | O que é |
|---|---|
| `valor_cents` | inteiro em centavos, nunca decimal quebrado |
| `prazo_dias` | dias de produção |
| `entregaveis` | lista fechada, marcada a partir do briefing |
| `correcoes_inclusas` | número |
| `justificativa` | texto curto e limitado, campo estruturado, sempre visível ao plantão |
| `valida_ate` | o relógio da proposta |

A **contraproposta** tem exatamente a mesma forma, preenchida pelo outro lado.
Não existe caixa de mensagem, não existe anexo solto, não existe resposta fora
desses campos. Quem quiser perguntar algo usa as perguntas estruturadas que a
lei já previu, com limite de três.

### 4.2 As rodadas são contadas, e o silêncio tem fim

- **Quem propõe primeiro é o aluno.** O cliente descreveu o trabalho; quem
  põe preço em trabalho é quem vai fazê-lo. Isso também evita a âncora baixa,
  que é o jeito clássico de o comprador definir o preço antes de o profissional
  falar.
- **Rodadas máximas:** parâmetro `rodadas_de_negociacao`, valor inicial **3**
  para cada lado. Esgotadas sem acordo, o projeto vai ao plantão, que fecha ou
  devolve o projeto à pista de origem.
- **Cada proposta tem validade** (parâmetro `validade_da_proposta`, inicial
  **24 horas úteis**, no mesmo relógio de horas úteis que a lei já definiu para
  a oferta). Vencida sem resposta, a vez volta.
- **Negociar não muda o lugar na fila.** Vale a mesma regra da lei: só o
  abandono muda o lugar. Propor, ser recusado e desistir são todos gratuitos.

### 4.3 O Acordo congela o combinado

Quando um lado aceita a proposta que está de pé, nasce o **Acordo**: valor,
prazo, entregáveis e correções inclusas ficam gravados na encomenda e **não
mudam mais**. Mudar depois só por mediação do plantão, com autor e motivo
registrados.

O Acordo é o que torna a disputa julgável. Sem ele, uma reclamação de "não é
o que eu pedi" é palavra contra palavra; com ele, o plantão compara a entrega
com um documento que os dois lados aceitaram.

### 4.4 O que acontece com o preço de tabela

Ele não morre: **vira preço de referência.** O cardápio continua mostrando um
valor por tipo de peça, agora rotulado como referência, e ele aparece nos dois
lados da negociação. Serve para três coisas:

- o cliente não descreve um projeto sem ideia nenhuma de custo;
- o aluno tem um chão para ancorar a própria proposta;
- o plantão tem uma régua para enxergar proposta muito fora da curva.

---

## §5 Onde o dinheiro entra, e por que nada disso toca a trava dele

A trava de 22/08/2026 continua de pé: **nenhum trabalho de cobrança, checkout
ou Mercado Pago até o mantenedor dizer que o site vai vender.** Ele reafirmou
isso na terceira resposta de 04/09/2026.

O que muda de lugar, e não de dono:

- Antes: pagar era a **porta de entrada** da encomenda. Não dava para ser
  diferente, porque o preço já era conhecido antes de qualquer aluno ver o
  pedido.
- Agora: o valor só existe **depois do Acordo**. Então a confirmação de
  pagamento passa a ficar entre o Acordo e o começo da produção.

**Isto não adianta uma linha de código de cobrança**, porque a resposta dele
foi "só a escola por enquanto". Na prática, hoje: o plantão abre o projeto em
nome da escola, o aluno propõe, o plantão aceita, e o plantão registra "pago
pela escola" com autor e data. É exatamente o que o invariante
**[INV-ENC-D13]** já media, e ele continua medindo a mesma coisa: **a
confirmação registrada com autor**, não o webhook.

Quando ele destravar o dinheiro, a única coisa que entra é a segunda fonte da
mesma confirmação: o webhook da célula de pagamentos. Nada do que está neste
plano precisa ser reescrito para isso acontecer.

---

## §6 Prazos, regras e disputas

Esta parte do pedido dele **já estava inteira na lei aprovada**, e não se
reescreve aqui para não criar o mesmo fato em dois lugares. O que segue é o
mapa de onde cada coisa mora, mais o que a negociação acrescenta.

| O que ele pediu | Onde já está | O que a negociação muda |
|---|---|---|
| **Prazos** | §6.6 da lei: prazo por tipo de peça, uma extensão de 48h pedida até 24h antes, prazo vencido é abandono | O prazo deixa de vir da tabela e passa a vir do **Acordo**. A extensão e o abandono continuam iguais |
| **Regras** | §6 inteiro da lei: elegibilidade, prioridade, oferta, chamada aberta, uma por vez, cancelamento, revisão, aprovação, correção | Ganham as regras de negociação do §4 deste plano |
| **Disputas** | §6.7 e §6.9 da lei: cancelamento com mediação, uma correção inclusa, segundo pedido de ajuste vai à mediação, plantão decide reembolso e registra | A mediação passa a ter o Acordo como documento de referência, o que a torna julgável em vez de opinativa |
| **Quem julga** | §5.7 da lei: a tela de plantão do professor, lista única por urgência, ação de um clique | Ganha dois itens novos na lista: negociação esgotada sem acordo, e proposta fora da curva |

---

## §7 A proteção do aluno na negociação

O mantenedor escolheu negociação em tudo sabendo do risco que estava escrito
na opção. A engenharia responde com quatro travas, e nenhuma delas é impedir
que ele negocie.

1. **Piso por nível.** Parâmetro `piso_por_nivel`, dado e não código, como
   todos os outros. Proposta abaixo do piso não é bloqueada, mas **avisa o
   aluno antes de enviar** e **acende no plantão**. A escola pode ver um aluno
   se subvalorizando e conversar com ele. Bloquear seria decidir por ele;
   avisar é ensinar.
2. **O preço de referência sempre à vista**, nos dois lados (§4.4).
3. **Rodadas contadas** (§4.2). Negociação sem fim é o formato em que o lado
   com mais tempo e mais experiência ganha por cansaço.
4. **O plantão vê tudo**, porque toda proposta é campo estruturado e nenhum
   texto escapa (§4.1, invariante S1).

E a trava que já existia e continua: **nenhuma primeira entrega chega ao
cliente sem um humano olhar.**

---

## §8 Os invariantes novos

Formato do `INVARIANTES.md`. Entram lá **com o guarda**, no PR indicado,
provados por mutação com vermelho na asserção. Os códigos são definitivos.

### O Mural

| Código | O quê | Guarda |
|---|---|---|
| **[INV-ENC-M1]** | O Mural nunca mostra projeto a aluno com zero entregas aprovadas | `services/encomendas/tests/test_inv_m1_mural_so_para_quem_ja_entregou.py` |
| **[INV-ENC-M2]** | Projeto de nível Iniciante só chega ao Mural pela chamada aberta | `.../test_inv_m2_iniciante_passa_pela_fila.py` |
| **[INV-ENC-M3]** | Um projeto do Mural fica reservado a um aluno por vez; nunca duas propostas vivas para o mesmo projeto | `.../test_inv_m3_mural_nao_e_leilao.py` |
| **[INV-ENC-M4]** | A ordem do Mural é só a antiguidade do projeto; nenhuma outra chave ordena | `.../test_inv_m4_ordem_unica.py` |
| **[INV-ENC-M5]** | Nenhum projeto passa de 24h no Mural sem elegível disponível sem ir ao plantão; nada fica parado sem alguém saber | `.../test_inv_m5_nada_encalha_em_silencio.py` |

### A negociação

| Código | O quê | Guarda |
|---|---|---|
| **[INV-ENC-N1]** | Nenhum texto entre cliente e aluno fora dos campos estruturados da proposta; todos visíveis ao plantão | `.../test_inv_n1_negociacao_sem_texto_livre.py` |
| **[INV-ENC-N2]** | Rodadas limitadas pelo parâmetro; esgotadas, o projeto vai ao plantão e nunca fica em negociação eterna | `.../test_inv_n2_rodadas_contadas.py` |
| **[INV-ENC-N3]** | Acordo fechado congela valor, prazo, entregáveis e correções; mudança posterior só por mediação com autor registrado | `.../test_inv_n3_acordo_congela.py` |
| **[INV-ENC-N4]** | Nenhuma produção começa sem Acordo **e** confirmação de pagamento registrada com autor | `.../test_inv_n4_producao_so_com_acordo_e_pagamento.py` |
| **[INV-ENC-N5]** | Propor, ser recusado, deixar vencer ou desistir nunca alteram a data de entrada na fila | `.../test_inv_n5_negociar_e_gratis.py` |

**[INV-ENC-N4] substitui [INV-ENC-D13]** na ordem dos fatos, e não na
substância: continua exigindo confirmação registrada com autor, e agora exige
também o Acordo. O código D13 fica reservado e aposentado, nunca reutilizado
para outra coisa.

Os dez invariantes de justiça (J1 a J10) continuam **inteiros e sem exceção**.
Nenhuma regra deste plano toca a ordem da fila.

---

## §9 Os parâmetros novos

Somam-se à tabela `Parametro` da lei, com a mesma regra: mudar é acrescentar
uma linha com motivo e autor, nunca um `UPDATE`, e nenhum deles vive em código.

| Chave | Valor inicial | Unidade |
|---|---|---|
| `rodadas_de_negociacao` | 3 | rodadas por lado |
| `validade_da_proposta` | 24 | horas úteis |
| `relogio_da_reserva_no_mural` | 3 | horas úteis |
| `entregas_para_ver_o_mural` | 1 | entregas aprovadas |
| `piso_por_nivel.iniciante` / `.intermediario` / `.avancado` | a definir na Fase 1 | centavos |
| `limite_da_justificativa` | 500 | caracteres |

O piso nasce sem número de propósito: ele sai do piloto de papel, que é onde
os primeiros preços reais vão aparecer. Chutar um piso agora seria inventar um
número e depois defendê-lo.

---

## §10 A escada

O momento é bom e vale registrar: em 04/09/2026, **nenhuma tabela da célula
tinha sido construída ainda.** A tarefa das tabelas (TAR-120) estava na fila
sem dono. Esta emenda entra antes da primeira linha de modelo, então nada
precisa ser desfeito.

A escada aprovada não é substituída. Ela **cresce**, e os degraus novos se
encaixam onde a dependência manda:

| Degrau | Tarefa | O quê | Espera |
|---|---|---|---|
| **2.2 emendado** | **TAR-120** | A máquina de estados da encomenda nasce já com `em_negociacao` e `acordada`, e a encomenda já com os campos do acordo, nulos. As tabelas Proposta, Acordo e reserva **não** nascem aqui | a gênese, já feita |
| **2.11** | **TAR-133** | O Mural: as três regras de pista, a reserva com relógio, a ordem única, **M1 a M5** | TAR-123, a chamada aberta |
| **2.12** | **TAR-134** | A Proposta e o Acordo: rodadas, validade, congelamento, piso que avisa, **N1 a N5** | TAR-133 |
| **2.13** | **TAR-135** | O simulador passa a provar o Mural e a negociação, e as duas propriedades que só ele alcança | TAR-134 |
| **2.14** | **TAR-136** | Os seis parâmetros do §9 na semente e na tela do dono | TAR-134 |
| **4 emendado** | Fase 4 | A tela do aluno ganha um quarto estado: **no Mural** | o portão da Fase 3 |
| **7 emendado** | Fase 7 | O plantão ganha dois itens: negociação esgotada, proposta fora da curva | a Fase 5 |

**A porta de máquina (TAR-125) passou a esperar também a TAR-134**, e isso é
deliberado. O contrato congela no degrau seguinte, e congelar antes de o Mural
e a negociação existirem faria a porta nascer cega justamente para o estado
que o aluno mais consulta. A ordem dos degraus 2.7 a 2.10 não muda no resto:
porta de máquina, congelar contrato, provisionamento, entrar no ar.

---

## §11 O que ninguém pode inventar a partir daqui

A lista do "fora" da lei aprovada **encolheu em dois itens e só nesses dois**.
Continuam proibidos, e continuam sendo critério de morte:

- **Leilão, lance, ou duas propostas vivas para o mesmo projeto.** O Mural é
  "quem pega, pega" (§3.2).
- **O cliente escolher entre alunos.** Ele nunca vê uma lista de pessoas.
- **Ranking, nota pública, estrelas, média de avaliação.** Nada disso nasce
  aqui, nem no Mural, nem no Estúdio.
- **Chat livre.** Negociação é formulário com rodadas contadas (§4.1).
- **Segunda regra de ordem**, na fila ou no Mural: peso, destaque, relevância,
  prioridade paga.
- **Matchmaking por IA ou classificação de briefing por IA.**
- **Cobrança, retenção ou repasse morando nesta célula.** O dinheiro é da
  célula de pagamentos.
- **Parâmetro do §9 vivendo em código.**

Passa a ser **permitido**, por decisão dele de 04/09/2026, e só nesta forma:

- **Proposta e contraproposta**, estruturadas, com rodadas contadas.
- **Mural aberto**, para quem já entregou pelo menos uma vez.

---

## §12 O que volta para ele

Nada bloqueia a construção. Estas três respostas cabem na fase que as precisa,
e estão registradas no livro como pendência para não se perderem:

1. **O piso por nível** (§9), em centavos. Sai do piloto de papel, na Fase 1.
2. **O nome da área na tela.** "Mural" é o nome usado neste plano. Muda em uma
   linha se ele preferir outro.
3. **Quantas rodadas de negociação** parecem certas depois do piloto. O valor
   inicial 3 é palpite honesto, e é parâmetro, então muda sem PR.

---

## Estado

Emenda escrita em 04/09/2026, a partir das três respostas dele em pergunta
estruturada no mesmo dia. Aguarda: os degraus novos do §10 entrarem na fila e
a TAR-120 ser construída já com as tabelas emendadas. Quem responde "isto foi
feito?" é o livro (`painel/registros/`) e o balcão
(`python ci/fila.py listar --ao-vivo`), nunca este documento.
