# `--e-pousar` morre no `mergeable=UNKNOWN` e o pouso NÃO foi pedido

**Sintoma:** o `esperar.py` termina os checks verdes, chama o portão sozinho e a
tarefa do `Monitor` morre com exit 1:

```
✅ o PR #957: todos os 7 checks verdes · levou 1s.
🛬 checks verdes: passo pelo portão e peço pouso do PR 957…
--- ERROR conflitos ---------------------------------------------------
O GitHub calcula isso de forma assíncrona; se você acabou de dar push,
espere alguns segundos e rode de novo.
RESULTADO  ERROR
🔴 o portão RECUSOU o pouso do PR 957 (exit 2)
```

O perigo não é a recusa: é o que ela deixa para trás. **A etiqueta `pousar` não
entrou**, ninguém está com o PR, e a mensagem do portão fala em "rode de novo"
sem dizer QUAL comando — quem lê depressa acha que a pista já assumiu e vai
embora. O PR fica aberto, verde e parado até alguém reparar.

**Causa:** a mesma da [130](130-mergeable-unknown-depois-de-um-merge-o-portao.md),
por outra porta. Lá o `UNKNOWN` vinha de um merge anterior mover a `main`; aqui
vem do **push que você acabou de dar** — o `--e-pousar` chega ao portão em
segundos, antes de o GitHub terminar de recalcular a mergeabilidade do PR. Quanto
mais rápido o CI fica, mais fácil é ganhar essa corrida: em 04/09/2026 aconteceu
**três vezes na mesma hora** (PR #954 duas vezes, #957 uma), uma delas com os
checks verdes em 1 segundo, porque eram os mesmos commits já medidos.

O portão está certo em recusar: `UNKNOWN` não é `MERGEABLE`, e "não consegui
medir" nunca vira PASS. O que falta é o segundo passo.

**Solução, em uma linha:** depois de um `--e-pousar` que morreu assim, rode o
pedido de pouso avulso.

```bash
python ci/mergear.py <N> --pousar
```

Ele passa: o estado agora é `BEHIND`, que é exatamente o caso que a pista existe
para atender, e a etiqueta entra. **Confira que entrou** antes de ir embora:

```bash
gh pr view <N> --json state,labels --jq '.labels[].name'
```

Se sair `pousar`, o PR está na fila e ninguém precisa esperar. Se não sair, o
pouso não foi pedido, por mais verde que estivesse a tela.

**O que NÃO fazer:** não repita o `--e-pousar` inteiro (ele espera os checks de
novo, que já estão verdes, e pode voltar ao mesmo lugar), não use
`gh pr merge`, e não trate a recusa como defeito do portão.

**Regra da casa que isto reforça:** toda espera tem voz e tem teto (`RITOS.md`
§2 peça 6) — mas *sair* de uma espera não é o mesmo que ter *entregado* o PR à
pista. A prova de que o trabalho saiu das suas mãos é a etiqueta, não a
mensagem verde que veio antes dela.
