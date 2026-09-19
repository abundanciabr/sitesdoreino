# DESPACHO: o texto da página de oferta

> Escrito em 19/09/2026 contra `origin/main = dfb5a381`. A estrutura da página
> (as seções e os espaços de texto dentro de cada uma) está sendo construída
> agora. Este documento é a outra metade: o texto de venda que vai dentro dela,
> o que o mercado chama de copy.
>
> Tudo que a casa já sabe sobre o produto está preenchido aqui, com o arquivo e
> a linha de onde saiu. O que sobra são perguntas que só você pode responder,
> porque as respostas viram afirmação pública e a casa não inventa afirmação.
>
> **A lista de seções e de espaços de texto usada aqui não é deste documento.**
> Quem é dono dela é a célula `catalogo` (PR #1773), e o contrato que a publica
> é o PR #1772. Este documento só pergunta o texto de cada espaço. Se a lista de
> lá mudar, é a de lá que vale, e este documento acompanha.

---

## Como responder

Responda na conversa, em texto corrido, dizendo o nome do espaço e a resposta.
Não precisa preencher tudo hoje, e não precisa responder na ordem.

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

## A segunda pergunta: você já escreveu uma página, e ela tem onze seções

Em 05/09/2026 você descreveu a página de vendas inteira, na ferramenta 73 do seu
documento "As ferramentas do projeto Meshcraft"
(`documentos/ferramentas-do-projeto-meshcraft.md:961`). São onze seções, nesta
ordem: o cubo, os três vilões, o método, os instrumentos (com o índice de
estúdios como prova), o percurso, quanto tempo leva (admitindo que os números
ainda não existem), para quem não serve (no meio, com seis recusas), o que
acontece se eu parar, o que recebe e o preço (uma vez, sem ancoragem), a carta
do autor por inteiro, e as perguntas. A regra que você escreveu para todas
elas: cada afirmação com prova ao lado.

A estrutura que está sendo construída agora tem sete seções, e elas não são as
suas. O encaixe da maior parte é direto:

| A sua seção | Onde ela cai nas sete |
| --- | --- |
| o cubo | `hero` |
| os três vilões | `problema` |
| o método, os instrumentos, o percurso | `mecanismo` |
| o índice de estúdios como prova | `prova` |
| quanto tempo leva | `prova` ou `faq` |
| o que recebe e o preço | `oferta` |
| a carta do autor | `prova.autoridade` |
| as perguntas | `faq` |

**Três das suas seções não têm lugar nas sete:** "para quem não serve", "o que
acontece se eu parar" e a seção de garantia (que existe nas sete e não existe
nas suas onze).

**Pergunta:** a estrutura de sete seções acomoda as suas onze, e as três que
sobram viram perguntas do `faq`, ou você quer que a estrutura mude para caber a
sua ordem? A resposta muda o trabalho do PR que constrói a página, e ela é sua.

Na ferramenta 74, logo abaixo (`:971`), você também listou o que a página nunca
pode ter: contagem regressiva, "últimas vagas", valor riscado, promessa de renda
ou de prazo, e superlativo. As tabelas abaixo respeitam essa lista.

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

## Seção 1: hero (o topo da página)

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `eyebrow` | A linha curtinha logo acima do título grande, que diz para quem é a página. Três a seis palavras. | Nada ainda. | Para quem é este curso, em até seis palavras? |
| `headline` | A frase maior da página, a primeira coisa que a pessoa lê. Diz o que ela sai sabendo ou conseguindo. | A home diz só "Meshcraft" (`services/funil/traducoes/landing.yaml:22`), que é o nome da marca, não uma promessa. Você já decidiu que esta seção é "o cubo" e que nenhuma afirmação entra sem prova ao lado, sem promessa de renda nem de prazo e sem superlativo (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`). | Qual é a promessa do curso em UMA frase, dentro dessa regra? Se "o cubo" já é a frase, escreva ela como ela aparece na tela. |
| `subheadline` | Uma frase abaixo do título, que explica a de cima sem repetir as mesmas palavras. Costuma dizer para quem a coisa é, ou por qual caminho ela acontece. | A casa sabe o caminho: 34 encomendas em 3 partes, com uma banca fechando cada parte (`semear_esqueleto.py:68-81` e `:102-105`). Prazo está fora: você proibiu promessa de prazo, e escreveu que "quanto tempo leva" admite que os números ainda não existem (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`). | A frase fala do caminho (34 encomendas, 3 partes, 3 bancas) ou de para quem o curso é? Escreva do jeito que você diria em voz alta. |
| `cta_texto` | O que está escrito dentro do botão. | A página de venda que ainda serve os domínios antigos usa "Quero comprar" (`services/funil/templates/funil/landing.html:19`). Não é texto seu, é o padrão que veio da montagem. | Mantém "Quero comprar" ou troca? Vale escrever o que a pessoa ganha ao clicar, e não o que ela faz. A palavra é sua. |
| `cta_destino` | Para onde o botão leva. | O checkout existe e funciona em `/checkout/<apelido-da-oferta>/`, preservando de onde a pessoa veio (`services/funil/apps/core/views.py:141`). O cartão está sendo migrado para a Appmax e o Pix fica no Mercado Pago (`docs/decisoes/PLANO-MESTRE-APPMAX-NO-CARTAO.md:17-18`), e essa obra ainda não começou. Há um terceiro destino que você já desenhou e que ainda não existe: a conta gratuita com a Encomenda 00 aberta, na ferramenta 72 (`documentos/ferramentas-do-projeto-meshcraft.md:951`). | São três destinos possíveis, e você escolhe um: o pagamento direto, o pedido de entrada que a escola usa hoje (`documentos/como-funciona-a-entrada.md:21-33`), ou a conta gratuita da E00. O terceiro é o que você escreveu que quer, e ele ainda precisa ser construído. |
| `imagem` | A imagem do topo. | Nada ainda. Não há nenhuma foto ou arte do produto no projeto. | Você tem uma imagem? Se sim, mande o arquivo. Se não, este espaço fica vazio e a seção abre só com texto. |

---

## Seção 2: problema

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção que descreve a situação em que a pessoa está hoje, antes de comprar. | Você chamou esta seção de "os três vilões" (`documentos/ferramentas-do-projeto-meshcraft.md:961`). | O título da seção sai dos três vilões, ou é outra frase? |
| `texto` | Dois ou três parágrafos descrevendo esse incômodo com as palavras que a própria pessoa usaria. Serve para ela pensar "é exatamente isso". | Que a seção existe e que são três vilões. Quais são os três, não está escrito em lugar nenhum do projeto. | Quais são os três vilões, e o que cada um faz com a pessoa? Escreva do jeito que você ouve dela, sem arrumar. |

---

## Seção 3: mecanismo (como o seu método funciona)

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção que explica como o seu método resolve aquilo. | Você separou isto em três seções suas: o método, os instrumentos e o percurso (`documentos/ferramentas-do-projeto-meshcraft.md:961`). Nas sete seções, as três cabem aqui. | Como você chama o seu método? E as três viram uma só aqui, ou você quer as três separadas na tela? |
| `texto` | A explicação do caminho, em passos, para a pessoa entender por que funciona. | A estrutura inteira: 3 partes, 12 blocos, 34 encomendas (da "Encomenda 00" à "Encomenda 32", mais a "Encomenda Bônus"), 12 encomendas grandes que fecham bloco e 3 bancas que fecham parte, conferindo os títulos Modelador Nível 1, 2 e 3 (`semear_esqueleto.py:68-81`, `:87-105`, `:125-129`). Há 13 instrumentos de conferência, com nome: Teste STUDS, Rubrica de Encomenda, Rubrica de Produto, Pronto para sair, Validação no motor, Prova dos 3 Movimentos, Prova das 5 Expressões, Selo UGC, Selo UGC de Personagem, Ficha de Série, Ficha de Delegação, Revisão de Estúdio e Laudo de Banca (`semear_esqueleto.py:108-122`). | O nome de cada bloco e de cada encomenda é obra sua e não está no projeto. Quais desses nomes podem aparecer numa página pública antes do lançamento? E o método tem um nome de uma frase que você queira usar aqui? |
| `imagem` | Uma imagem ou desenho que mostre o método. | Nada ainda. | Você tem um desenho do caminho? Se não, vazio. |

---

## Seção 4: prova (por que acreditar em você)

Esta é a seção em que a casa mais precisa de você e menos pode ajudar.
Depoimento, número e autoridade são afirmações sobre o mundo real. Um agente que
escrevesse qualquer uma delas estaria escrevendo mentira numa página pública.

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Nada ainda. | Uma frase que anuncie a prova. |
| `depoimento` | A fala de uma pessoa real que fez o curso, com o nome dela e a permissão dela para publicar. | Nenhum depoimento está escrito em nenhum arquivo do projeto. A prova que você escolheu para esta seção não é depoimento, é o índice de estúdios (`documentos/ferramentas-do-projeto-meshcraft.md:961`), que sai do Padrão online da ferramenta 70 (`:929`), e nem o índice nem o Padrão online existem hoje. | Você tem alguém que topa aparecer com nome? Se sim, mande a fala como ela mandou, sem arrumar, e diga se pode usar o nome inteiro. Se a sua prova é só o índice de estúdios, este espaço fica vazio até o índice existir, e isso é coerente com o que você escreveu. |
| `numeros` | Números verificáveis: quantos alunos, quantas peças prontas, quanto tempo de escola. | Nada que possa ir para a tela. Você já escreveu que a seção "quanto tempo leva" admite que os números ainda não existem (`documentos/ferramentas-do-projeto-meshcraft.md:961`), e o projeto tem regra dura contra número copiado em documento, porque ele vira mentira no dia seguinte (`documentos/LEIA-ME.md`, seção "O que se escreve aqui"). Quantos alunos existem hoje é dado do banco de produção, não deste repositório. | Você mantém a escolha de admitir que os números não existem, ou já tem um número que é verdade hoje e que você aceita corrigir na tela quando mudar? |
| `autoridade` | Por que você é a pessoa que pode ensinar isso. | Você já decidiu o formato: a carta do autor por inteiro, não um resumo (`documentos/ferramentas-do-projeto-meshcraft.md:961`). O texto dela não está no projeto. | Mande a carta. Se ela ainda não existe, o que você fez que dá a você o direito de ensinar isso, em duas ou três linhas, serve como primeira versão. |

---

## Seção 5: oferta

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção onde o preço aparece. | Você chamou esta seção de "o que recebe e o preço" (`documentos/ferramentas-do-projeto-meshcraft.md:961`). | Esse é o título que aparece na tela, ou é só o nome interno da seção? Se for interno, qual é o título? |
| `ancora_de_preco` | Um valor de referência mostrado ANTES do preço, para a pessoa ter com o que comparar. Exemplo de formato, de outro mercado, só para você ver o formato: uma academia escreve "uma aula particular custa R$ 120" antes de dizer que a mensalidade é R$ 99. | **Você já disse não a este espaço.** Em 05/09/2026 escreveu que o preço aparece uma vez, sem ancoragem, e pôs "valor riscado" na lista de padrões proibidos da página (`documentos/ferramentas-do-projeto-meshcraft.md:961` e `:971`). | Essa decisão continua de pé? Se sim, não responda nada aqui e o espaço fica vazio para sempre. Se você mudou de ideia, diga qual é o valor de comparação e de onde ele sai. |
| `preco_texto` | O preço à vista, escrito como a pessoa lê na tela. | O único preço cadastrado é R$ 9,90, e é peça de teste (`infra/sites.json:26`). Curso cadastrado de verdade nasce com preço zero (`criar_curso.py:53`). | Quanto custa? Enquanto este número não existir, nada além desta página é possível: o botão de compra não tem para onde levar. |
| `parcelamento` | Em quantas vezes e de quanto fica cada parcela. | Nada ainda. O parcelamento depende da Appmax, cuja obra ainda não começou (`PLANO-MESTRE-APPMAX-NO-CARTAO.md:17-18`). | Em quantas vezes você quer vender? Diga também se quer mostrar "ou R$ X à vista". |
| `bonus` | O que entra junto sem custar a mais. | A estrutura para isso existe e tem nome: o `Bump`, que é um produto extra oferecido no checkout, com nome, preço e uma frase de chamada (`services/catalogo/apps/ofertas/models.py:39-52`). Nenhum está cadastrado. A grade já tem uma "Encomenda Bônus" dentro do curso (`semear_esqueleto.py:125-129`), que é conteúdo do curso, não bônus de compra. | Tem bônus? Qual, e ele é de graça ou é o extra pago do checkout? São coisas diferentes. |
| `cta_texto` | O que está escrito no botão desta seção. | Nada ainda. Costuma repetir o botão do topo. | Mesmo texto do botão de cima, ou outro? |

---

## Seção 6: garantia

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Nada ainda. | Uma frase. |
| `texto` | O que você devolve, em que caso, e o que a pessoa precisa fazer para pedir. | Nenhuma promessa de devolução existe em nenhum lugar do projeto, e nenhum agente pode escrever uma, porque garantia é compromisso legal seu. O que já é lei aqui é a consequência: quem é reembolsado perde o acesso ao curso, ao fórum e à Caixa, e a ficha dela continua guardada (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`, 31/08/2026). A sua lista de onze seções não tinha seção de garantia (`documentos/ferramentas-do-projeto-meshcraft.md:961`). | Você devolve o dinheiro? Em que situação, e a pessoa precisa justificar? E a página diz, na mesma frase, que o reembolso encerra o acesso? Dizer isso agora evita a reclamação depois. |
| `prazo` | Quantos dias a pessoa tem para pedir o dinheiro de volta. Este é o único prazo que a página pode dizer, e ele não é promessa de resultado: é o tempo em que você aceita desfazer a compra. | Nada ainda. | Quantos dias? O Código de Defesa do Consumidor já obriga 7 dias em compra pela internet, então qualquer número seu abaixo disso não vale, e igual a 7 não é diferencial nenhum. |

---

## Seção 7: faq (as perguntas frequentes)

| Espaço | O que é | O que a casa já sabe | O que falta, e só você tem |
| --- | --- | --- | --- |
| `headline` | O título da seção. | Nada ainda. | Uma frase, ou nada: "Perguntas frequentes" já serve. |
| `perguntas` | A lista de perguntas com as respostas. Vale a pena responder aqui o que faz a pessoa desistir na hora de pagar. | A casa sabe algumas respostas de mecânica, e elas já estão escritas em português para o aluno: como se pede entrada e o que acontece depois (`documentos/como-funciona-a-entrada.md`); que entrar com o Google não é virar aluno (mesmo arquivo, linha 12); que o site fala português, inglês e espanhol (`infra/sites.json:17-22`). Duas perguntas você já nomeou como seções próprias: "para quem não serve", com seis recusas, e "o que acontece se eu parar" (`documentos/ferramentas-do-projeto-meshcraft.md:961`). | Quais são as seis recusas de "para quem não serve", e qual é a resposta de "o que acontece se eu parar"? Fora essas, quais são as três perguntas que mais aparecem quando alguém quase compra e não compra? |

---

## O mínimo viável, e é uma recomendação, não um cardápio

A página de hoje mostra três coisas: o nome do produto, o preço, e um botão
escrito "Quero comprar" (`services/funil/templates/funil/landing.html:17-19`).
Qualquer coisa acima disso já é ganho. A ordem abaixo é a que entrega mais cedo
o maior salto.

**Responda hoje (8 espaços).** Isto é o que faz a página valer mais que a atual:

- `hero.headline` e `hero.subheadline`, porque hoje a pessoa não lê nenhuma frase
  que diga o que ela vai conseguir
- `hero.cta_texto` e `hero.cta_destino`, porque um botão precisa dizer o que faz
  e ter para onde ir
- `oferta.preco_texto` e `oferta.parcelamento`, porque sem preço real não existe
  venda, só uma peça de teste de R$ 9,90
- `garantia.texto` e `garantia.prazo`, porque é a objeção mais barata de derrubar
  e a única que você resolve com duas linhas

**Pode esperar a segunda rodada:** `problema.texto`, `mecanismo.texto` e
`faq.perguntas`. São os espaços que mais convencem, e também os que mais exigem
tempo seu escrevendo. A página funciona sem eles.

**Pode esperar de verdade:** a seção `prova` inteira e as três imagens. A prova
que você escolheu (o índice de estúdios) ainda não existe, depoimento e número
você só publica quando tiver, e imagem some sem deixar buraco.

**Recomendo deixar vazio para sempre:** `oferta.ancora_de_preco`. Você já disse
não a ela em 05/09/2026, e a recomendação aqui é só confirmar a sua decisão, não
propor outra. Âncora que não é verdade é a primeira coisa que um comprador
desconfiado checa.

---

## Exemplos de formato, de outro mercado, para nunca colar

Estão aqui só para você ver a FORMA dos três espaços que costumam travar mais.
São de uma academia, de uma padaria e de um dentista de propósito, para que
nenhuma linha destas possa acabar na sua página por engano.

- **Linha de topo, o `eyebrow` (academia):** "Para quem treina sozinho e não sai
  do lugar."
- **Garantia (padaria):** "Se o pão não agradar, traga de volta no mesmo dia e
  eu troco ou devolvo o dinheiro. Não pergunto o motivo."
- **Pergunta frequente (dentista):** "Dói? O procedimento é feito com anestesia
  local, e a maioria dos pacientes volta a trabalhar no mesmo dia."

---

## O que acontece depois que você responder

As respostas viram texto na página pela tela do painel, nunca por arquivo deste
repositório, porque o repositório é público e o que é obra sua entra pela tela
(`armadilhas/331`).

Três respostas destravam trabalho que hoje está parado, e elas não são frases de
venda:

1. **O endereço da página**, porque sem ele o PR seguinte não tem rota para criar.
2. **Sete seções ou as suas onze**, porque isso decide se a estrutura que está
   sendo construída agora serve ou precisa mudar.
3. **Quanto custa**, porque o único preço cadastrado é uma peça de teste de
   R$ 9,90 e o botão de compra não tem para onde levar sem um preço de verdade.

As outras respostas são texto, e texto entra a qualquer momento, um espaço por
vez.
