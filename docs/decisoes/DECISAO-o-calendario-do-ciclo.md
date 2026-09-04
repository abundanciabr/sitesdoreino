# DECISÃO — a meta do ciclo cresce por semana, e não em linha reta

> **Pedida pelo mantenedor em 04/09/2026**, com o calendário dele por escrito e
> a curva descrita na frase que define tudo:
>
> *"quero que nas primeiras semanas as vendas fiquem na faixa de 0 enquanto nós
> vamos aprendendo e testando as campanhas, criativos, copys, landing pages,
> funis, e etc"*, para que *"nas últimas semanas hajam vendas muito maiores do
> que no início onde ainda não aprendemos nada"*.
>
> Este documento é **lei** para tudo que julgar ritmo de meta nesta casa. Ele
> se soma a `PLANO-PAINEL-DE-GESTAO.md` (§5, a cadência) e ao cartão
> `painel/cartoes/compras-no-ciclo.json`, onde a régua mora.

---

## 1. O que muda

Até 04/09/2026 a meta grande do ciclo era repartida em **linha reta**: cada dia devia trazer a mesma
fatia, e o placar dizia "ganhando" ou "perdendo" contra ela.

A partir de agora ela é repartida por uma **curva de 14 semanas**, declarada no
campo `semanas` do cartão da meta. A linha reta continua existindo e continua
correta para todo cartão que não declara curva.

## 2. Por que a linha reta media a coisa errada

Uma linha reta afirma que a primeira semana e a última valem o mesmo. Num
lançamento perpétuo isso é falso, e falso de um jeito caro: as primeiras
semanas são de descobrir o que funciona (a campanha, o criativo, a copy, a
página de venda), e as últimas são de repetir o que já se sabe que funciona.

Com a linha reta, o painel diria **"perdendo"** todos os dias de setembro, com
o mantenedor fazendo exatamente o que devia estar fazendo. Um painel que grita
erro enquanto o trabalho vai bem é um painel que ensina a ignorá-lo, e um
painel ignorado não existe.

## 3. O calendário e a curva

A meta grande é **de 0 para 1000 pessoas, de 03/09 a 15/12/2026** (dobrada por
ele em 04/09/2026), repartida assim:

| Semana | De | Até | Meta | Acumulado | Cresce |
|---|---|---|---|---|---|
| Preparação | 07/09 | 11/09 | 0 | 0 | |
| 1 | 14/09 | 18/09 | 0 | 0 | |
| 2 | 21/09 | 25/09 | 0 | 0 | |
| 3 | 28/09 | 02/10 | 0 | 0 | |
| 4 | 05/10 | 09/10 | 0 | 0 | |
| 5 | 12/10 | 16/10 | 20 | 20 | |
| 6 | 19/10 | 23/10 | 31 | 51 | +55% |
| 7 | 26/10 | 30/10 | 45 | 96 | +45% |
| 8 | 02/11 | 06/11 | 69 | 165 | +53% |
| 9 | 09/11 | 13/11 | 103 | 268 | +49% |
| 10 | 16/11 | 20/11 | 154 | 422 | +50% |
| 11 | 23/11 | 27/11 | 231 | 653 | +50% |
| 12 | 30/11 | 04/12 | 347 | 1000 | +50% |
| Recuperação | 07/12 | 11/12 | 0 | 1000 | |

As datas são as do mantenedor, conferidas: todas de segunda a sexta, cinco dias
cada.

### 3.1 A regra que gera os números, e por que ela não é escolha de gosto

A curva **não é uma lista de números bonitos**: é `50% a mais que a semana
anterior`, aplicado às 8 semanas que vendem. Isso responde ao pedido dele de
*"um crescimento progressivo conforme os testes e aprendizados acontecem"* e
resolve, de graça, o incômodo que ele apontou na primeira versão: **uma curva
percentual nunca repete um valor.**

### 3.2 O laço de três pontas, que é o achado desta decisão

Com o calendário fixo, **três coisas puxam umas às outras, e só se escolhem
duas**:

> o **total** · quantas **semanas vendendo** · a **taxa de crescimento**

E a consequência é contraintuitiva o bastante para merecer estar escrita:
**quanto MENOR a taxa, MAIOR tem de ser a primeira semana.** Quem cresce pouco
precisa começar grande para chegar ao mesmo lugar. Medido, para 1000 em 10
semanas vendendo:

| Taxa | A 1ª semana precisa ser | A última chega a |
|---|---|---|
| 10% | **63** | 148 |
| 20% | 39 | 199 |
| 30% | 23 | 249 |
| 40% | 14 | 296 |
| 50% | 9 | 339 |

Ele pediu *"10, 20 ou 30% por semana"*, e a conta mostrou que essa faixa é a
mais DIFÍCIL de todas com esse total: a 10% ao ano de 12 semanas, a máquina
teria de vender 63 na primeira semana em que liga, logo depois de semanas
vendendo zero.

Vendo isso, ele escolheu **manter setembro inteiro livre** (a decisão dele de
mais cedo no mesmo dia, que sobrou 8 semanas) e aceitar a taxa que essa escolha
implica: **50%**. Foi decisão informada, com os dois lados da conta na tela.

### 3.3 A alternativa que ficou registrada e não foi escolhida

Foi proposta uma curva de **taxa afunilando** (75% no começo, 22% no fim, 3
semanas em zero): 8, 14, 23, 38, 59, 88, 123, 168, 216, 263. O argumento a favor
é que porcentagem engana sobre o esforço, e vale ficar escrito: ir de 8 para 14
é +75% mas são 6 vendas a mais; ir de 216 para 263 é +22% mas são 47 a mais. Uma
taxa fixa fica mais pesada toda semana em pessoas de verdade; a afunilada faz o
esforço extra subir parelho.

Ele escolheu a taxa fixa de 50%, e o motivo é dele: **setembro inteiro livre
para aprender vale mais** que suavizar a reta final. Fica registrado para quando
o ciclo for revisto.

## 4. A regra dura: a curva e a meta grande nunca discordam

**A soma das metas semanais tem de ser exatamente `alvo` menos `partida`.** O
validador do cartão (`placar._validar_as_semanas`) reprova o cartão quando não
é, e a mensagem diz o conserto.

Sem essa regra, a curva e a meta grande seriam duas verdades sobre o mesmo
número, e no dia em que discordassem o placar diria uma coisa e o calendário
outra, os dois com ar de certeza. É a lei anti-duplicação do `CLAUDE.md`
aplicada dentro de um arquivo só.

## 5. A curva mora no CARTÃO, e a tela só lê

`painel/cartoes/compras-no-ciclo.json`, campo `semanas`. Não em código, não numa
tabela nova, não na tela.

Isso é o que faz **o painel inteiro seguir a mesma régua**: quem lê a curva é
`placar.esperado_em`, que já era o único lugar onde "quanto eu deveria ter hoje"
se decidia. Com ela andam, sem uma linha a mais:

- o veredito do ciclo (ganhando ou perdendo) em `/admin/placar/`;
- a meta do mês, que é a fatia da curva que cai naquele mês;
- a meta da semana da direção, que é a fatia daquela semana.

Se a curva vivesse na tela nova, essas três continuariam julgando pela linha
reta enquanto o calendário mostrasse outra coisa.

**Dentro de uma semana, o esperado sobe dia a dia**; no fim de semana, fica no
que a semana fechou. Sem isso o veredito daria um pulo toda segunda e ficaria
congelado o resto da semana, e a tela diria "ganhando" na terça de uma semana
que ia terminar perdida.

## 6. A tela

`/admin/placar/ciclo/` — as 14 linhas, com a meta da semana, a meta acumulada,
o que aconteceu de verdade e o veredito de cada semana **já fechada**. Semana
que está andando não recebe veredito: julgar uma semana pela metade é o "ontem
contra hoje engana" dos documentos.

Mora **dentro** de `placar/` e não ao lado: é a régua que o placar usa, e o menu
do topo casa a seção por prefixo, então o item "Placar" continua aceso. Item
novo no menu para uma segunda leitura da mesma meta seria o menu crescendo sem
realidade nova.

Sem a célula `alunos`, as colunas do que aconteceu ficam **em branco**, nunca em
zero: zero afirmaria que ninguém comprou naquela semana.

## 7. A meta é 1000 pessoas

O pedido original dizia *"a venda dos 500 cursos para atingir os 50 alunos"*, e
os dois números não podiam estar certos ao mesmo tempo. Perguntado em
04/09/2026, ele confirmou 500 — e, na mesma conversa, poucos minutos depois,
**dobrou para 1000**.

A pergunta foi feita em vez de adivinhada porque a diferença era de dez vezes, e
uma curva montada sobre o número errado seria uma régua errada julgando o ano
inteiro, com ar de certeza.

**O alvo mudou duas vezes num dia, e nenhuma tela precisou ser refeita.** É a
prova do desenho da §5: a régua mora no cartão. Onde o número aparecia COPIADO
(o mapa do site, o LEIA-ME dos cartões, o `_por_que` do cartão dos pedidos, o
docstring do `placar.py`), ele foi **retirado** em vez de atualizado. Cópia de
número é o que envelhece em silêncio, e a terceira mudança de alvo não vai
precisar de uma caçada por textos desatualizados.

**Quem faz valer:** `placar._validar_as_semanas` (a soma, a ordem e as datas) ·
`services/admin/tests/test_ciclo.py` (a curva do cartão REAL soma a meta; o
veredito do placar muda com a régua; "não sei" nunca vira zero).
