# DECISÃO: adiar é decisão do mantenedor

**Data:** 22/09/2026
**Quem decidiu:** o mantenedor, nesta sessão, com as palavras dele
**Estado:** vigente

## O pedido

Ele descobriu, lendo a avaliação da conclusão do Appmax, que um robô tratava
uma entrega como deliberadamente adiada. Ninguém tinha pedido a palavra dele
naquele ato, e ele ficou dias esperando uma coisa que não ia ficar pronta.
Pediu a regra no sistema: nenhum robô define uma tarefa como deliberadamente
adiada sem conhecimento, anuência e permissão expressa do mantenedor.

## A lei, em uma frase

**Adiar tarefa, entrega ou escopo só vale com a palavra dele, escrita no
mesmo ato.** Sem isso a tarefa continua aberta, e ele fica sabendo na hora.

## Por que recusar um evento chamado `adiada` não resolve

A fila nunca teve estado `adiada`. Um arquivo com esse nome já reprova em
`validar`, porque o evento não existe. O adiamento que o deixou no escuro não
nasceu nesse arquivo. Nasceu na fala do robô, no meio da tarefa, sem evento,
sem bloqueio e sem o bloco do painel que diz o que espera por ele.

Portão em porta que ninguém usa é intenção. A mesma lição da decisão das
Instruções no fecho: regra só em texto apodrece.

## O que foi decidido

1. O fecho que declara tarefa, entrega ou escopo como adiado, sem a linha
   `Anuência do mantenedor:` e as palavras dele, é recusado pelo Stop.
2. `bloquear` com motivo de adiamento só grava se `--anuencia` traz as
   palavras dele (pelo menos 20 letras) e `--espera mantenedor`. Assim a
   pausa aparece no bloco "Esperando uma decisão sua".
3. `cancelar` não serve de pausa. Motivo de adiamento é recusado, e a tarefa
   continua na fila.
4. `validar` reprova o mesmo ato escrito à mão, fora do comando.

Sem a palavra dele, o caminho honesto é NÃO PRONTO. As Instruções dizem o
motivo, de quem é a bola e o que destrava. Isso não é adiamento. A tarefa
segue aberta.

## O que foi rejeitado

Um estado novo `adiada` na fila. O painel já tem o bloco do que espera por
ele. Segundo estado para o mesmo fato esconderia a pausa de novo, que é o
bug que esta decisão fecha.

## Quem faz valer

`ci/prestacao_de_contas.py` no Stop e `ci/fila.py` em `bloquear`, `cancelar`
e `validar`, com os testes de `ci/tests/test_prestacao_de_contas.py` e
`ci/tests/test_fila.py`.
