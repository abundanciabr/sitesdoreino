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

Até 04/09/2026 a meta grande do ciclo (**de 0 para 500 pessoas, de 03/09 a
15/12/2026**) era repartida em **linha reta**: cada dia devia trazer a mesma
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

## 3. O calendário, como ele deu

| Semana | De | Até | Meta | Acumulado |
|---|---|---|---|---|
| Preparação | 07/09 | 11/09 | 0 | 0 |
| 1 | 14/09 | 18/09 | 0 | 0 |
| 2 | 21/09 | 25/09 | 0 | 0 |
| 3 | 28/09 | 02/10 | 5 | 5 |
| 4 | 05/10 | 09/10 | 10 | 15 |
| 5 | 12/10 | 16/10 | 15 | 30 |
| 6 | 19/10 | 23/10 | 25 | 55 |
| 7 | 26/10 | 30/10 | 35 | 90 |
| 8 | 02/11 | 06/11 | 50 | 140 |
| 9 | 09/11 | 13/11 | 65 | 205 |
| 10 | 16/11 | 20/11 | 85 | 290 |
| 11 | 23/11 | 27/11 | 105 | 395 |
| 12 | 30/11 | 04/12 | 105 | 500 |
| Recuperação | 07/12 | 11/12 | 0 | 500 |

As datas são as do mantenedor, conferidas: todas de segunda a sexta, cinco dias
cada. Os números da coluna "Meta" são **proposta minha**, montada sobre a forma
que ele descreveu; ele ajusta quando quiser, editando um arquivo.

**A semana de recuperação não tem meta própria de propósito.** O que ela carrega
é o que faltar quando a semana 12 fechar. Dar meta a ela seria transformar a
rede de segurança em mais um degrau, e a meta grande deixaria de fechar em 500.

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

## 7. O que ficou em aberto para o mantenedor

O pedido dele dizia *"a venda dos 500 cursos para atingir os 50 alunos"*. O
número que está no sistema, decidido por ele em 03/09/2026 (registro
`20260903-036`) e gravado no cartão, é **500 pessoas**. A curva foi montada
sobre 500. Se o número certo for outro, muda-se o `alvo` e as 14 linhas no mesmo
arquivo, e o validador garante que os dois continuem casando.

**Quem faz valer:** `placar._validar_as_semanas` (a soma, a ordem e as datas) ·
`services/admin/tests/test_ciclo.py` (a curva do cartão REAL soma a meta; o
veredito do placar muda com a régua; "não sei" nunca vira zero).
