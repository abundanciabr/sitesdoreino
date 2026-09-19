# DESPACHO: o texto da página de oferta

> Escrito em 19/09/2026 e reescrito no mesmo dia, contra `origin/main = 4d802c85`.
> A estrutura da página (as seções e os espaços de texto dentro de cada uma)
> está sendo construída agora. Este documento é a outra metade: o texto de
> venda que vai dentro dela, o que o mercado chama de copy.
>
> Tudo que a casa já sabe sobre o produto está preenchido aqui, com o arquivo e
> a linha de onde saiu. O que sobra são perguntas que só você pode responder,
> porque as respostas viram afirmação pública e a casa não inventa afirmação.
>
> **A lista de seções e de espaços de texto usada aqui não é deste documento.**
> Quem é dono dela é a célula `catalogo`, no arquivo
> `services/catalogo/apps/paginas/vocabulario.py` (PR #1773), e o contrato que
> a publica é o PR #1772. Aquela lista já foi corrigida para as onze seções que
> você especificou, e este documento agora bate com ela, espaço por espaço. Se
> a lista de lá mudar, é a de lá que vale, e este documento acompanha.

---

## Leia isto primeiro, se você já começou a responder

Este documento nasceu em 19/09/2026 com sete seções que a casa tinha inventado,
e foi reescrito no mesmo dia com as **onze seções que você especificou** em
05/09/2026. As perguntas daqui nunca tiveram número: cada uma é chamada pelo
nome do espaço, e vários nomes mudaram.

Se você já respondeu alguma coisa citando um nome antigo, nada se perdeu. A
tabela diz onde cada resposta foi parar.

| Nome antigo | Onde ele está agora |
| --- | --- |
| `hero.eyebrow` | não existe mais: as onze seções não têm linha de topo, e o que você diria ali cabe na `cubo.subheadline` |
| `hero.headline` | `cubo.headline` |
| `hero.subheadline` | `cubo.subheadline` |
| `hero.cta_texto` | `cubo.cta_texto` |
| `hero.cta_destino` | `cubo.cta_destino` |
| `hero.imagem` | `cubo.imagem` |
| `problema.headline` | `viloes.headline` |
| `problema.texto` | virou três espaços, um por vilão: `viloes.vilao_1`, `vilao_2` e `vilao_3` |
| `mecanismo.headline` e `mecanismo.texto` | `metodo.headline` e `metodo.texto`; o que era sobre instrumentos e sobre percurso ganhou seção própria |
| `mecanismo.imagem` | `metodo.imagem` |
| `prova.headline` | não existe mais: prova deixou de ser seção e virou um espaço dentro de cada seção que afirma alguma coisa |
| `prova.depoimento` | o espaço `prova` de `viloes`, `metodo`, `instrumentos`, `percurso` ou `tempo`, conforme o que a fala prova |
| `prova.numeros` | `tempo.texto` e `tempo.prova` |
| `prova.autoridade` | `carta.texto`, e agora a carta é seção inteira, com `carta.assinatura` |
| `oferta.headline` | `oferta.headline` |
| `oferta.ancora_de_preco` | removido: a ferramenta 74 proíbe valor riscado |
| `oferta.preco_texto` | `oferta.preco_texto` |
| `oferta.parcelamento` | `oferta.parcelamento` |
| `oferta.bonus` | `oferta.o_que_recebe` |
| `oferta.cta_texto` | `oferta.cta_texto` |
| `garantia.headline`, `garantia.texto`, `garantia.prazo` | removidos: viraram a pergunta "você devolve o dinheiro?", no fim deste documento |
| `faq.headline` | `perguntas.headline` |
| `faq.perguntas` | `perguntas.perguntas` |

Seções que não existiam neste documento e agora existem, porque são suas:
`instrumentos`, `percurso`, `tempo`, `para_quem_nao_serve`, `se_eu_parar` e
`carta`.

---

## Como responder

Responda na conversa, em texto corrido, dizendo o nome do espaço e a resposta.
O nome completo é `secao.espaco`, por exemplo `cubo.headline`. Não precisa
preencher tudo hoje, e não precisa responder na ordem.

**Espaço em branco é resposta legítima.** Seção sem nenhum texto simplesmente
não aparece na tela. A página funciona incompleta, e ela já vai nascer melhor
que a de hoje com meia dúzia de frases suas. Você decide o que fica vazio.

**A casa não escreve no seu lugar.** Nenhuma promessa, nenhum depoimento,
nenhum número e nenhuma garantia sai daqui inventado. Onde a coluna "o que a
casa já sabe" diz "nada ainda", é porque não existe mesmo, em lugar nenhum do
projeto.

---

## A pergunta que vem antes de todas: em que endereço esta página mora?

Hoje a raiz do site (`meshcraft.top/`) é a HOME, não a oferta. Foi decisão sua
em 27/08/2026: a raiz deixou de ser vitrine e virou porta. Quem não entrou vê o
convite para entrar; quem entrou vê o aviso de novidade e o caminho da categoria
dele. Está escrito em `services/funil/apps/core/views.py:112-119` e
`services/funil/templates/funil/landing_i18n.html:4-7`.

A página de oferta precisa de um endereço, e a rota nasce no PR seguinte a este.
As três saídas, com a consequência de cada uma:

| Saída | O que acontece com a HOME de hoje | O que acontece com quem já entrou |
| --- | --- | --- |
| A oferta passa a ser a raiz (`meshcraft.top/`) | a HOME de hoje some, ou muda de endereço | o aluno que abre o site cai na página de venda de um curso que ele já comprou |
| A oferta ganha endereço próprio (por exemplo `meshcraft.top/curso`) | a HOME fica como está | o aluno continua caindo na porta de sempre |
| A raiz decide sozinha: oferta para quem não entrou, HOME para quem entrou | a HOME continua existindo, escondida de quem não entrou | o aluno nunca vê a página de venda |

**Pergunta:** qual das três? Se for a segunda, qual palavra você quer no
endereço? A palavra vira link permanente e trocá-la depois quebra o que alguém
guardou ou anunciou.

---

## A estrutura está decidida: são as suas onze seções, na sua ordem

Este documento perguntava, na primeira versão, se as sete seções inventadas pela
casa acomodavam as suas onze. A pergunta está respondida e não se pergunta de
novo: **valem as onze, na ordem que você escreveu.**

Em 05/09/2026 você descreveu a página de vendas inteira, na ferramenta 73 do seu
documento "As ferramentas do projeto Meshcraft"
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). A célula `catalogo` já
gravou essa lista como a única válida, com o comentário dizendo que mudar a
lista é mudar a sua especificação, e que o caminho é ela e não o código
(`services/catalogo/apps/paginas/vocabulario.py`, PR #1773). As onze, na ordem,
com o nome técnico que a casa valida e os espaços de texto de cada uma:

| # | Seção | O que ela é, em uma linha | Espaços de texto |
| --- | --- | --- | --- |
| 1 | `cubo` | a abertura da página | `headline`, `subheadline`, `cta_texto`, `cta_destino`, `imagem` |
| 2 | `viloes` | os três vilões | `headline`, `vilao_1`, `vilao_2`, `vilao_3`, `prova` |
| 3 | `metodo` | o método | `headline`, `texto`, `imagem`, `prova` |
| 4 | `instrumentos` | os instrumentos, com o índice de estúdios como prova | `headline`, `texto`, `indice_de_estudios`, `prova` |
| 5 | `percurso` | o percurso | `headline`, `texto`, `prova` |
| 6 | `tempo` | quanto tempo leva, admitindo que os números ainda não existem | `headline`, `texto`, `prova` |
| 7 | `para_quem_nao_serve` | para quem não serve, no meio da página, com seis recusas | `headline`, `recusa_1` a `recusa_6` |
| 8 | `se_eu_parar` | o que acontece se eu parar | `headline`, `texto` |
| 9 | `oferta` | o que recebe e o preço, uma vez e sem ancoragem | `headline`, `o_que_recebe`, `preco_texto`, `parcelamento`, `cta_texto` |
| 10 | `carta` | a carta do autor, por inteiro | `headline`, `texto`, `assinatura` |
| 11 | `perguntas` | as perguntas | `headline`, `perguntas` |

**O espaço `prova` aparece cinco vezes**, em `viloes`, `metodo`, `instrumentos`,
`percurso` e `tempo`. É a leitura que a casa fez da sua frase "cada afirmação
com prova ao lado": a prova fica pendurada na própria seção que afirma, para que
afirmação e prova viajem juntas e não se soltem uma da outra. A prova que você
escolheu para a página é o índice de estúdios, que sai do Padrão online da
ferramenta 70 (`documentos/ferramentas-do-projeto-meshcraft.md:929`), e nem o
índice nem o Padrão online existem hoje. Enquanto não existirem, os cinco
espaços de prova ficam vazios, e as seções que afirmam alguma coisa vão para a
tela sem prova ao lado ou não vão.

Na ferramenta 74, logo abaixo (`:971`), você listou o que a página nunca pode
ter: contagem regressiva, "últimas vagas", valor riscado, promessa de renda ou
de prazo, e superlativo. As tabelas abaixo respeitam essa lista.

---

## O que saiu deste documento, e por quê

Duas coisas que a primeira versão perguntava foram removidas, porque perguntar
por elas é a própria casa pedindo o que a sua lei proíbe: a âncora de preço
(`oferta.ancora_de_preco`) e a seção de garantia com o prazo de devolução
(`garantia.texto` e `garantia.prazo`) saíram porque a ferramenta 74
(`documentos/ferramentas-do-projeto-meshcraft.md:971`) proíbe valor riscado e
promessa de prazo, e um espaço de texto vazio é um convite a preencher.

A devolução de dinheiro não sumiu da conversa: ela virou pergunta de produto, no
fim deste documento, porque a resposta dela muda contrato, e não uma linha de
tela.

---

## O que a casa já sabe sobre o produto, antes das tabelas

Três fatos que pesam em quase todos os espaços abaixo:

1. **Não existe produto real cadastrado.** A única coisa à venda hoje é uma peça
   de teste chamada "Curso de Teste", a R$ 9,90
   (`infra/sites.json:16-28`). O comando que cadastra curso de verdade grava
   preço zero de propósito, e o comentário dele diz por quê: a plataforma ainda
   não vende (`services/catalogo/apps/produtos/management/commands/criar_curso.py:15-17`
   e `:53`).
2. **A grade do curso existe e é pública.** O curso `profissional`, de nome
   "Profissional", tem 12 blocos, 34 encomendas e 13 instrumentos
   (`services/cursos/apps/cursos/management/commands/semear_esqueleto.py:62-63`,
   `:68-81`, `:108-122`).
3. **O texto das aulas não está no projeto, e é assim de propósito.** Este
   repositório é público e o curso é obra sua não lançada, então o conteúdo só
   entra pela tela do painel (`armadilhas/331`,
   `services/cursos/apps/cursos/management/commands/semear_esqueleto.py:9-14`).
   Nenhum agente pode ler o seu material para escrever a página.

---

## Seção 1: `cubo` (a abertura da página)

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | A frase maior da página, a primeira coisa que a pessoa lê. Diz o que ela sai sabendo ou conseguindo. | A home diz só "Meshcraft" (`services/funil/traducoes/landing.yaml:22`), que é o nome da marca, não uma promessa. Você já decidiu que esta seção é "o cubo" e que nenhuma afirmação entra sem prova ao lado, sem promessa de renda nem de prazo e sem superlativo (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`). | Qual é a promessa do curso em UMA frase, dentro dessa regra? Se "o cubo" já é a frase, escreva ela como ela aparece na tela. |
| `subheadline` | Uma frase abaixo do título, que explica a de cima sem repetir as mesmas palavras. Costuma dizer para quem a coisa é, ou por qual caminho ela acontece. | A casa sabe o caminho: 34 encomendas em 3 partes, com uma banca fechando cada parte (`semear_esqueleto.py:68-81` e `:102-105`). Prazo está fora: você proibiu promessa de prazo, e escreveu que "quanto tempo leva" admite que os números ainda não existem (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`). | A frase fala do caminho (34 encomendas, 3 partes, 3 bancas) ou de para quem o curso é? Escreva do jeito que você diria em voz alta. Se você queria uma linha curta dizendo para quem a página é, o lugar dela é aqui: as onze seções não têm espaço separado para isso. |
| `cta_texto` | O que está escrito dentro do botão. | A página de venda que ainda serve os domínios antigos usa "Quero comprar" (`services/funil/templates/funil/landing.html:19`). Não é texto seu, é o padrão que veio da montagem. | Mantém "Quero comprar" ou troca? Vale escrever o que a pessoa ganha ao clicar, e não o que ela faz. A palavra é sua. |
| `cta_destino` | Para onde o botão leva. | O checkout existe e funciona em `/checkout/<apelido-da-oferta>/`, preservando de onde a pessoa veio (`services/funil/apps/core/views.py:141`). O cartão está sendo migrado para a Appmax e o Pix fica no Mercado Pago (`docs/decisoes/PLANO-MESTRE-APPMAX-NO-CARTAO.md:17-18`), e essa obra ainda não começou. Há um terceiro destino que você já desenhou e que ainda não existe: a conta gratuita com a Encomenda 00 aberta, na ferramenta 72 (`documentos/ferramentas-do-projeto-meshcraft.md:951`). | São três destinos possíveis, e você escolhe um: o pagamento direto, o pedido de entrada que a escola usa hoje (`documentos/como-funciona-a-entrada.md:21-33`), ou a conta gratuita da E00. O terceiro é o que você escreveu que quer, e ele ainda precisa ser construído. |
| `imagem` | A imagem do topo. | Nada ainda. Não há nenhuma foto ou arte do produto no projeto. | Você tem uma imagem? Se sim, mande o arquivo. Se não, este espaço fica vazio e a seção abre só com texto. |

---

## Seção 2: `viloes` (os três vilões)

São exatamente três espaços de vilão, porque a sua especificação diz três
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). Não existe `vilao_4`.

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção que descreve a situação em que a pessoa está hoje, antes de comprar. | Que você chamou esta seção de "os três vilões". | O título da seção sai dos três vilões, ou é outra frase? |
| `vilao_1` | O primeiro vilão: o que atrapalha a pessoa, descrito com as palavras que ela mesma usaria. Serve para ela pensar "é exatamente isso". | Nada. Quais são os três não está escrito em lugar nenhum do projeto. | Qual é o primeiro, e o que ele faz com a pessoa? Escreva do jeito que você ouve dela, sem arrumar. |
| `vilao_2` | O segundo vilão, na mesma forma. | Nada. | Qual é o segundo? |
| `vilao_3` | O terceiro vilão, na mesma forma. | Nada. | Qual é o terceiro? |
| `prova` | O que mostra que esses três vilões são reais, e não invenção de quem vende. | Nada ainda. Aqui é onde caberia a fala de uma pessoa que passou por isso, e nenhum depoimento está escrito em nenhum arquivo do projeto. | Você tem alguém que topa aparecer com nome dizendo que viveu isso? Se sim, mande a fala como ela mandou, sem arrumar, e diga se pode usar o nome inteiro. Se não, o espaço fica vazio. |

---

## Seção 3: `metodo`

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção que explica como o seu método resolve aquilo. | Que "o método" vem logo depois dos vilões, e antes dos instrumentos e do percurso, que agora são seções próprias. | Como você chama o seu método? |
| `texto` | A explicação de por que o método funciona. É o princípio, não a lista de aulas: a lista fica em `percurso`. | Nada sobre o princípio. O que a casa conhece é a mecânica, e ela está nas duas seções seguintes. | Em duas ou três frases, por que o seu jeito de ensinar funciona? |
| `imagem` | Uma imagem ou desenho que mostre o método. | Nada ainda. | Você tem um desenho? Se não, vazio. |
| `prova` | O que mostra que o método funciona. | Nada ainda. | Uma peça pronta, um antes e depois, um nome de estúdio que use isso? Se ainda não tem, vazio. |

---

## Seção 4: `instrumentos`

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção sobre as ferramentas de conferência que o aluno recebe. | Que você separou os instrumentos em seção própria. | O título. |
| `texto` | O que são os instrumentos e para que servem, do ponto de vista de quem vai usar. | Os 13 existem e têm nome canônico no projeto: Teste STUDS, Rubrica de Encomenda, Rubrica de Produto, Pronto para sair, Validação no motor, Prova dos 3 Movimentos, Prova das 5 Expressões, Selo UGC, Selo UGC de Personagem, Ficha de Série, Ficha de Delegação, Revisão de Estúdio e Laudo de Banca (`semear_esqueleto.py:108-122`). | Quais desses nomes podem aparecer numa página pública antes do lançamento? E o que um instrumento faz pela pessoa, em uma frase que ela entenda sem ter comprado? |
| `indice_de_estudios` | O texto que apresenta o índice de estúdios, que é a prova que você escolheu para esta seção. | O índice sai do Padrão online, a ferramenta 70 (`documentos/ferramentas-do-projeto-meshcraft.md:929`): site estático em `/padrao`, com índice de versões locais e mapa de calor. Nem o Padrão online nem o índice existem hoje. | Enquanto o índice não existir, este espaço fica vazio e nada se perde. Quando existir, o que a página diz sobre ele: quantos estúdios, ou só o convite para ver? |
| `prova` | O que mostra que os instrumentos funcionam fora da sua sala. | Nada ainda, pelo mesmo motivo do espaço acima. | Vazio até o índice existir. |

---

## Seção 5: `percurso`

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção que mostra o caminho do começo ao fim. | Que "o percurso" vem depois dos instrumentos. | O título. |
| `texto` | O caminho em passos, para a pessoa ver onde entra e onde chega. | A estrutura inteira: 3 partes, 12 blocos, 34 encomendas (da "Encomenda 00" à "Encomenda 32", mais a "Encomenda Bônus"), 12 encomendas grandes que fecham bloco e 3 bancas que fecham parte, conferindo os títulos Modelador Nível 1, 2 e 3 (`semear_esqueleto.py:68-81`, `:87-105`, `:125-129`). | O nome de cada bloco e de cada encomenda é obra sua e não está no projeto. Quais desses nomes podem aparecer numa página pública antes do lançamento? |
| `prova` | O que mostra que alguém percorreu esse caminho até o fim. | Nada ainda. | Alguém já terminou? Se sim, pode aparecer com nome? Se não, vazio. |

---

## Seção 6: `tempo` (quanto tempo leva)

Esta é a seção que você escreveu admitindo que os números ainda não existem
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). Ela não tem espaço de
prazo, e isso é de propósito: prazo prometido está na lista de proibidos da
ferramenta 74 (`:971`).

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Que ela existe e que admite a falta de números. | O título. |
| `texto` | A resposta honesta para "em quanto tempo eu chego lá". | Nada que possa ir para a tela. O projeto tem regra dura contra número copiado em documento, porque ele vira mentira no dia seguinte (`documentos/LEIA-ME.md`, seção "O que se escreve aqui"). Quantos alunos existem hoje é dado do banco de produção, não deste repositório. | Você mantém a escolha de admitir que os números não existem, e escreve isso na cara? Se sim, escreva a frase. Se já tem um número que é verdade hoje e que você aceita corrigir na tela quando mudar, diga qual e de onde ele sai. |
| `prova` | O que sustenta o que o texto diz sobre tempo. | Nada ainda. | Só existe quando houver gente que terminou. Vazio até lá. |

---

## Seção 7: `para_quem_nao_serve`

Ela fica no meio da página, e não no fim, porque foi assim que você escreveu
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). São seis recusas, nem
mais nem menos: não existe `recusa_7`.

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Que ela existe e tem seis recusas. | O título. |
| `recusa_1` a `recusa_6` | Cada uma é um tipo de pessoa, ou uma expectativa, que este curso não atende. Uma frase por recusa, dita sem rodeio. | Nada. As seis não estão escritas em lugar nenhum do projeto. | Quais são as seis? Cada uma tira uma pessoa da compra, e é para isso mesmo que a seção serve. Escreva as que você diria olhando no olho. |

---

## Seção 8: `se_eu_parar`

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Que ela vem logo depois das recusas. | O título. |
| `texto` | O que acontece com quem comprou e parou no meio: o que ela perde, o que ela mantém, e se dá para voltar. | Uma consequência já é lei aqui, e é de reembolso, não de parada: quem é reembolsado perde o acesso ao curso, ao fórum e à Caixa, e a ficha dela continua guardada (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`, 31/08/2026). O que acontece com quem só para de estudar não está decidido em lugar nenhum. | Quem parou continua com acesso para sempre? O material some? Dá para voltar de onde saiu? Responda pensando em quem está lendo isso ANTES de comprar, com medo de não dar conta. |

---

## Seção 9: `oferta` (o que recebe e o preço)

O preço aparece uma vez, sem ancoragem, e é por isso que não existe aqui espaço
de valor riscado (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`).

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção onde o preço aparece. | Que você chamou esta seção de "o que recebe e o preço". | Esse é o título que aparece na tela, ou é só o nome interno da seção? Se for interno, qual é o título? |
| `o_que_recebe` | A lista do que entra na compra, escrita do ponto de vista de quem paga. | A grade que a pessoa recebe (34 encomendas, 12 blocos, 13 instrumentos, 3 bancas com título) já está apurada nas seções 4 e 5 acima. Para o que entra junto sem custar a mais, existe estrutura com nome: o `Bump`, produto extra oferecido no checkout, com nome, preço e frase de chamada (`services/catalogo/apps/ofertas/models.py:39-52`). Nenhum está cadastrado. A "Encomenda Bônus" da grade (`semear_esqueleto.py:125-129`) é conteúdo do curso, não bônus de compra. | O que entra na compra, em itens curtos? E tem bônus? Se tiver, diga se ele é de graça (entra nesta lista) ou se é o extra pago do checkout (aí é `Bump`, e não é texto desta página). São coisas diferentes. |
| `preco_texto` | O preço à vista, escrito como a pessoa lê na tela. | O único preço cadastrado é R$ 9,90, e é peça de teste (`infra/sites.json:26`). Curso cadastrado de verdade nasce com preço zero (`criar_curso.py:53`). | Quanto custa? Enquanto este número não existir, nada além desta página é possível: o botão de compra não tem para onde levar. |
| `parcelamento` | Em quantas vezes e de quanto fica cada parcela. | Nada ainda. O parcelamento depende da Appmax, cuja obra ainda não começou (`PLANO-MESTRE-APPMAX-NO-CARTAO.md:17-18`). | Em quantas vezes você quer vender? Diga também se quer mostrar "ou R$ X à vista". |
| `cta_texto` | O que está escrito no botão desta seção. | Nada ainda. Costuma repetir o botão do topo. | Mesmo texto do botão de cima, ou outro? |

---

## Seção 10: `carta` (a carta do autor)

Você escreveu que a carta entra por inteiro, e não resumida
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). Por isso ela é seção, e
não uma caixinha dentro de outra coisa.

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Nada ainda. | O título, ou nada. |
| `texto` | A carta inteira, na sua voz. É onde a pessoa decide se confia em você. | O texto da carta não está no projeto, e nenhum agente pode escrevê-la: ela é a sua voz sobre a sua vida. | Mande a carta. Se ela ainda não existe, o que você fez que dá a você o direito de ensinar isso, em duas ou três linhas, serve como primeira versão. |
| `assinatura` | Como a carta termina: o nome, e o que vem junto do nome. | Nada ainda. | Como você assina? Só o nome, ou nome e o que você é? |

---

## Seção 11: `perguntas`

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Nada ainda. | Uma frase, ou nada: "Perguntas frequentes" já serve. |
| `perguntas` | A lista de perguntas com as respostas. Vale a pena responder aqui o que faz a pessoa desistir na hora de pagar. | A casa sabe algumas respostas de mecânica, e elas já estão escritas em português para o aluno: como se pede entrada e o que acontece depois (`documentos/como-funciona-a-entrada.md`); que entrar com o Google não é virar aluno (mesmo arquivo, linha 12); que o site fala português, inglês e espanhol (`infra/sites.json:17-22`). | "Para quem não serve" e "o que acontece se eu parar" NÃO entram aqui: você fez as duas serem seções próprias, e repeti-las seria dizer a mesma coisa duas vezes. Fora essas, quais são as três perguntas que mais aparecem quando alguém quase compra e não compra? |

---

## A pergunta que não virou espaço de texto: você devolve o dinheiro?

As suas onze seções não têm seção de garantia, e a lista da célula `catalogo`
também não tem, coerente com elas. Por isso a devolução não é uma linha de
tabela aqui: ela é uma pergunta de produto, e a resposta muda mais coisa do que
uma frase na tela.

O que já é lei aqui é a consequência, não a promessa: quem é reembolsado perde o
acesso ao curso, ao fórum e à Caixa, e a ficha dela continua guardada
(`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`, 31/08/2026). O Código de
Defesa do Consumidor obriga 7 dias de arrependimento em compra pela internet,
então esse direito existe com ou sem página.

**Pergunta:** você devolve o dinheiro além do que a lei já obriga, e em que
situação?

**A consequência de responder "sim":** aí a página precisa de um lugar para
dizer isso, e esse lugar não existe. Criar um é mudar a sua especificação de
05/09/2026 e a lista de seções da célula `catalogo`, e exige a sua palavra
escrita, não a interpretação de um agente. Responder "não" fecha o assunto e
nada muda.

---

## O mínimo viável, e é uma recomendação, não um cardápio

A página de hoje mostra três coisas: o nome do produto, o preço, e um botão
escrito "Quero comprar" (`services/funil/templates/funil/landing.html:17-19`).
Qualquer coisa acima disso já é ganho. A ordem abaixo é a que entrega mais cedo
o maior salto.

**Responda hoje (7 espaços).** Isto é o que faz a página valer mais que a atual:

- `cubo.headline` e `cubo.subheadline`, porque hoje a pessoa não lê nenhuma frase
  que diga o que ela vai conseguir
- `cubo.cta_texto` e `cubo.cta_destino`, porque um botão precisa dizer o que faz
  e ter para onde ir
- `oferta.preco_texto` e `oferta.parcelamento`, porque sem preço real não existe
  venda, só uma peça de teste de R$ 9,90
- `oferta.o_que_recebe`, porque preço sem a lista do que vem junto é um número
  no vazio

**Pode esperar a segunda rodada:** os três vilões, `metodo.texto`,
`percurso.texto`, as seis recusas de `para_quem_nao_serve`, `se_eu_parar.texto`
e `perguntas.perguntas`. São os espaços que mais convencem, e também os que mais
exigem tempo seu escrevendo. A página funciona sem eles.

**Pode esperar de verdade:** os cinco espaços de `prova`,
`instrumentos.indice_de_estudios`, a seção `tempo` inteira, a `carta` e as duas
imagens. A prova que você escolheu ainda não existe, a carta é trabalho longo
seu, e imagem some sem deixar buraco.

---

## Exemplos de formato, de outro mercado, para nunca colar

Estão aqui só para você ver a FORMA dos três espaços que costumam travar mais.
São de uma academia, de uma padaria e de um dentista de propósito, para que
nenhuma linha destas possa acabar na sua página por engano.

- **Um vilão, o `viloes.vilao_1` (academia):** "Você começa na segunda animado,
  para na quinta, e no mês seguinte recomeça do zero pela quarta vez."
- **Uma recusa, o `para_quem_nao_serve.recusa_1` (padaria):** "Não serve para
  quem procura pão sem glúten. Eu não faço, e não pretendo fazer."
- **Uma pergunta, o `perguntas.perguntas` (dentista):** "Dói? O procedimento é
  feito com anestesia local, e a maioria dos pacientes volta a trabalhar no
  mesmo dia."

---

## O que acontece depois que você responder

As respostas viram texto na página pela tela do painel, nunca por arquivo deste
repositório, porque o repositório é público e o que é obra sua entra pela tela
(`armadilhas/331`).

Três respostas destravam trabalho que hoje está parado, e elas não são frases de
venda:

1. **O endereço da página**, porque sem ele o PR seguinte não tem rota para criar.
2. **Quanto custa**, porque o único preço cadastrado é uma peça de teste de
   R$ 9,90 e o botão de compra não tem para onde levar sem um preço de verdade.
3. **Se você devolve o dinheiro**, porque um "sim" muda a lista de seções e o
   contrato, e isso é decisão sua, não leitura de agente.

As outras respostas são texto, e texto entra a qualquer momento, um espaço por
vez.
