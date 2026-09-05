# DECISÃO: juntar ideias na Caixa, com prévia e desfazer

**Pedida por ele em 05/09/2026**, nas palavras dele:

> "Coloque o botão de fundir que mostra o modal de como ficaria se fossem
> fundidas, e pede a confirmação da fusão, com a opção de desfazer tudo."

## O que existia antes, e por que não bastava

`Sugestao.Status.MESCLADO` existe desde o primeiro dia da Caixa, e a
`ESPECIFICACAO-CELULA.md` §8 (V1.1) já escrevia os invariantes de uma junção.
O que a casa tinha construído até aqui era a **proibição de fingir**: `mesclado`
não entra pela tela de mudar fase, com teste-guarda, porque *"deixá-lo no
`<select>` daria à equipe um jeito de marcar mesclado sem que nada tivesse sido
mesclado, e a lista de mescladas nasceria mentindo"*.

Ou seja: a casa sabia que junção de mentira é pior que junção nenhuma, e
esperou a de verdade. Ela é esta.

## As três peças, e a regra que liga as três

**1. A prévia não escreve nada.** É o que ele vê antes de decidir. Se ela
mexesse no banco, "ver como ficaria" já teria mudado a Caixa.

**2. A confirmação é um gesto separado**, dentro do modal, depois de ver os
números.

**3. O desfazer devolve de verdade** — e só existe porque a junção guarda o
recibo do que moveu, voto a voto.

**A regra que liga as três: sem prévia não há botão.** Se a Caixa não responde
a prévia, a análise continua na tela (ler vale sem o botão) e o gesto de juntar
desaparece. Fail-open na leitura, fail-closed na ação.

## A decisão de produto que o número carrega

**Depois da junção, o total de votos quase nunca é a soma.** Quem votou em duas
ideias juntadas continua sendo uma pessoa com um voto: o `unique_together` do
`Voto` não deixaria ser diferente, e nem deveria.

A tela mostra os dois números lado a lado (o de depois e o que seria se fosse
soma) e explica a diferença em português. Mostrar só a soma seria prometer uma
popularidade que a junção não entrega, e ele descobriria isso depois de clicar;
mostrar só o número menor, sem explicação, pareceria defeito ou perda de voto.

## O que o desfazer devolve, e o que ele NÃO devolve

Devolve: os votos que mudaram de ideia, os votos que a junção apagou (de quem
já tinha votado nas duas), os comentários e a fase de cada ideia absorvida.

**Não devolve o voto que a pessoa tirou depois da junção**, e isso é honestidade
e não descuido: ressuscitá-lo seria votar no lugar dela. Um comentário apagado
também não volta.

## Quem faz valer

- `services/sugestoes/tests/test_fusoes.py` — os invariantes da espec §8, o
  desfazer que devolve e o desfazer que não inventa.
- `services/admin/tests/test_caixa_fusao.py` — sem prévia não há botão, o
  número menor explicado, o impedimento escrito, e o rastro na auditoria.
- `contracts/sugestoes.openapi.yaml` — as quatro operações, congeladas.
