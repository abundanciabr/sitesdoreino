# DECISÃO: PRONTO sobre medição vermelha é contradição

**Data:** 20/09/2026
**Quem decidiu:** o mantenedor, na sessão ("faz o 1713")
**Estado:** vigente
**Substitui:** o PR #1713, fechado no mesmo dia

## O problema

Em 18/09/2026 o robô via o check `muralhas` vermelho, escrevia "vou abrir o log
dessa falha e corrigir a causa concreta" e encerrava o turno. O relatório ficava
bonito e o trabalho ficava pela metade.

O PR #1713 nasceu disso e nunca pousou: ficou conflitado por dois dias e foi
fechado em 20/09/2026, junto de #1502, #1504 e #1655, quando a regra do bloco
`Instruções` entrou pelo #1801. O mantenedor mandou reconstruí-lo contra a main
de hoje.

## O que foi rejeitado do desenho original, e por quê

O #1713 caçava a **frase**: uma lista de verbos (`vou corrigir`, `investigarei`,
`repetirei`) cruzada com uma lista de objetos técnicos (`log`, `check`, `erro`),
mais exceções para citação histórica, pausa do mantenedor e bloqueio externo.

Três defeitos, e os três são de fundo:

1. **Recusava em laço.** Ele testava isso como virtude (`test_segunda_passada_
   nao_perdoa_promessa_tecnica`). Todo outro portão deste arquivo recusa uma vez
   e depois só avisa, porque portão que recusa sempre é a espera em laço com
   outro nome: uma sessão que não achasse a redação boa ficava presa.
2. **As exceções eram ajustadas aos próprios testes.** Liberar exigia a
   coincidência de três regex (`quando a credencial chegar` **e**
   `mantenedor.*liberar` **e** `403|401|acesso negado`). Qualquer bloqueio real
   escrito de outro jeito era recusado.
3. **Colidia com o bloco `Instruções`**, que entrou horas antes pelo #1801. As
   ações legítimas daquele bloco usam exatamente os verbos que o #1713 proibia.
   Um portão que briga com a regra que o mantenedor acabou de pedir é perda
   líquida.

E o caso concreto que o motivou, PR com check vermelho, **já era coberto**:
`_portao_do_voo` recusa o fecho quando o PR aberto pela sessão está vermelho,
pendente ou em rascunho.

## O que foi decidido

Mede-se o **vermelho**, não a redação.

**Declarar PRONTO sobre a última medição vermelha da sessão é recusado.**

- A medição é um comando que a casa já reconhece como verificação
  (`COMANDOS_QUE_VERIFICAM`: pytest, `ci/ci.py`, muralhas, `npm test`).
- O veredito sai da última linha da saída: `N failed` ou `RESULTADO FAIL` é
  vermelho, `N passed` ou `RESULTADO PASS` é verde.
- Vale a **última** medição, não a pior: reprovar, consertar e medir de novo é o
  laço normal de trabalho, e guardar o pior vermelho puniria quem consertou.
- Saída não reconhecível não vira vermelho. Fail-open de propósito: um comando
  cortado por um `grep` não informa nada, e supor reprovação seria o portão
  inventando fato, que é o pecado que ele existe para punir.
- `NÃO PRONTO` **sempre** passa. O portão nunca obriga a mentir: a saída honesta
  é dizer a verdade, e o bloco `Instruções` do #1801 já obriga a explicar o que
  reprovou, de quem é a bola e o que destrava.
- Recusa **uma vez** por dívida; depois avisa com exit 1, sem prender.

O que isto compra que a caça à frase não comprava: não se dribla reescrevendo, e
não briga com o `Instruções`.

O que isto **não** pega, dito na cara: uma promessa sobre algo que ninguém
mediu. Se o robô nunca rodou a suíte, não há vermelho para contradizer. A regra
6 continua cobrindo isso por texto ("ou rodou de verdade, ou escreve NÃO
RODEI"), sem mecanismo.

## Quem faz valer

`ci/prestacao_de_contas.py` (`_portao_do_vermelho`, `veredito_da_medicao`,
`_seguir_a_medicao`) no `Stop` do Claude Code e do Codex, com os testes de
`ci/tests/test_prestacao_de_contas.py`; `ci/padrao_de_trabalho.py` guarda a
frase "Prometer o conserto não é consertar" na regra 6.
