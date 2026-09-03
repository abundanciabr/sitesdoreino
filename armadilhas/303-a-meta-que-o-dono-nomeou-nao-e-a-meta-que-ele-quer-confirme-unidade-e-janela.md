---
schema_version: 2
armadilha: 303
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a ambiguidade mora na frase do mantenedor, antes de existir cartão ou código para medir; o que existe é a pergunta de confirmação (unidade + janela + fonte) antes de gravar a régua, e o cartão de métrica que obriga a escrever `definicao` e `formula` por extenso
sinal:
  - `alvo: null`
  - `aguardando você`
  - `de X para Y até`
---

# A meta que o dono nomeou não é a meta que ele quer: confirme unidade, janela e fonte antes de gravar a régua

**Sintoma.** O mantenedor responde numa pergunta estruturada "a meta é o
número de alunos na plataforma", o robô constrói o placar naquela mesma tarde
(cartão, tela, testes, deploy verde), e à noite o mantenedor diz: *"essa meta
foi eu quem a escolhi aleatoriamente sem estudar melhor os documentos"*. O que
ele queria era outra coisa: **quantas pessoas compraram neste mês**, zerando
todo dia 1. Caso real de 03/09/2026: o placar do PR #924 mediu o número errado
por umas oito horas, e a reforma custou um Rito de Contrato (PRs #933 e #934) e
a reescrita da tela (PR #936).

E dentro da reforma, o segundo tropeço da mesma família: perguntado o alvo, ele
escreveu *"500 até o dia 15 de dezembro de 2026"*. Lido de um jeito é 500 POR
MÊS (a barra de dezembro chega a 500, 2,5 vezes a maior turma); lido de outro é
500 SOMADAS de setembro a dezembro (uns 150 por mês, perto do histórico). Os
dois cabem na frase. Perguntado, ele escolheu a soma. Se o robô tivesse gravado
a primeira leitura, o placar diria "perdendo" todo dia até dezembro, com a
régua errada e a voz de medição.

**Causa.** Uma meta tem QUATRO partes e o dono, leigo, nomeia só a primeira: o
nome do número ("alunos"), a **unidade e a janela** (por mês? acumulado? desde
quando?), o **alvo** (Y e a data) e a **fonte** (qual campo, qual data conta).
Quem constrói ouve o nome e preenche o resto com a interpretação mais óbvia
para si, e o painel nasce medindo a interpretação, não a intenção. É a
`RETROSPECTIVA-FASE-D.md` padrão 8 (não afirme viabilidade sem ler a
configuração) virada para o lado da PESSOA: não afirme a meta sem ler a
intenção. Duas vezes no mesmo dia, com o mesmo mantenedor.

**Solução.** Antes de gravar alvo, partida e data num cartão de métrica:

1. **Explique retrovisor e volante em uma frase** (o que se olha depois; o
   que se move na semana) e pergunte a qual dos dois a meta pertence. Foi
   essa explicação que fez o mantenedor trocar "alunos na plataforma" por
   "compras do mês".
2. **Confirme a unidade e a janela por caixa estruturada, com as leituras
   possíveis escritas por extenso e o que cada uma implica** ("500 por mês: a
   barra de dezembro chega a 500, 2,5× a maior turma" contra "500 somadas de
   hoje até 15/12: uns 150 por mês"). Uma opção por leitura; nunca gravar a
   primeira que pareceu óbvia.
3. **Confirme a fonte: qual campo, qual data conta.** "Compraram" pode ser a
   data que a pessoa digitou (`comprou_em`, opcional), a liberação
   (`decidido_em`) ou o pagamento (`enrolled_at`). O mantenedor escolheu as
   duas últimas, e a escolha custou um campo novo no contrato. Se o campo não
   existe em porta de LISTA, leia a `armadilhas/293` antes de abrir o rito.
4. **Grave a consequência que a fonte tem sobre a partida, por escrito.** Com
   a data da liberação como fonte, a turma liberada em lote na véspera
   (02/09) entraria como "compra de setembro"; a partida em 03/09 a deixa de
   fora, e o cartão diz isso na `definicao`.
5. **O cartão de métrica é o lugar da confirmação:** `definicao` e `formula`
   por extenso, em português de leigo, ANTES do código. Se a frase do cartão
   não sobreviver à leitura em voz alta pelo dono, o número está errado.

**O preço de não fazer:** um placar verde medindo a coisa errada, que é o
falso-verde mais caro que existe, porque ninguém desconfia de uma tela bonita
que responde "ganhando".

**Onde vive o caso:** registro `20260903-036` (as seis decisões da noite),
`painel/cartoes/compras-no-ciclo.json` (a `definicao` que carrega a
consequência da fonte) e `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §1.
