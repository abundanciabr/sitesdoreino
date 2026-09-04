# `--e-pousar` morre no `mergeable=UNKNOWN` e a etiqueta não entra

**Esta entrada virou ponteiro. O caso mora na
[310](310-e-pousar-chama-o-portao-no-pior-instante-e-sai-error.md), que é mais
completa e traz os sinais declarados.** Leia lá.

**Por que existem duas:** as duas nasceram na madrugada de 04/09/2026, em
sessões paralelas, com minutos de diferença, sobre o mesmo sintoma. Nenhuma
podia ver a outra: cada uma estava num PR que ainda não tinha pousado quando a
outra foi escrita. Nenhuma regra falhou (o número se pede ao almoxarife, e cada
uma pediu o seu). O que falta é o catálogo ter como avisar que **alguém já está
escrevendo sobre aquilo agora** — fica o caso concreto, para quem um dia
mecanizar isso.

**Resumo em duas linhas, para quem chegou pelo Ctrl+F:** o
`esperar.py --checks N --e-pousar` chama o portão segundos depois do push, antes
de o GitHub calcular a mergeabilidade, e sai `ERROR` com tudo verde. A etiqueta
`pousar` **não entra**, e o PR fica parado esperando alguém que não sabe que
está sendo esperado.

**O que esta entrada acrescenta à 310, e por isso ela fica:** a prova de que o
trabalho saiu das suas mãos **não é a mensagem verde, é a etiqueta**. Depois de
`python ci/mergear.py <N> --pousar`, confira antes de ir embora:

```bash
gh pr view <N> --json state,labels --jq '.labels[].name'
```

Se não sair `pousar`, o pouso não foi pedido, por mais verde que estivesse a
tela anterior. Em 04/09/2026 isto aconteceu quatro vezes numa hora (PRs #954
duas vezes, #957 e #960), e foi essa conferência que impediu um PR pronto de
dormir aberto.
