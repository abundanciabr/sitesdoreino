---
schema_version: 2
armadilha: 364
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão deste repositório vê um PR aberto e parado. As muralhas rodam DENTRO do PR, o portão do pouso só age quando alguém o chama, e a pista só acorda com a etiqueta `pousar` — que neste caso nunca chegou. O que existe é a conferência de dois segundos deste arquivo (`gh pr view <N> --json state,labels`), feita pela maestro antes de dar um despacho por fechado
sinal:
  - pouso automático armado
  - mergear sozinho
  - `"estado":"OPEN","etiquetas":\[\]`
---

# O pouso automático armado pelo despacho morre com a sessão dele: o PR fica verde, pronto e órfão

**Data:** 06/09/2026 · **Onde:** PR #1160 (Alavanca 3 das alavancas de 10x), aberto por um sub-agente `despacho` · **Custo medido:** 12h30 de um PR verde parado, e a `main` andando 74 commits por cima dele.

## Sintoma

O sub-agente `despacho` abre o PR, arma a espera pela ferramenta `Monitor` e
fecha o relatório dizendo, com todas as letras:

```
o Monitor está com o pouso automático armado e vai atualizar o ramo
com a `main` e mergear sozinho
Nada depende de ninguém.
```

O harness confirma: `<status>completed</status>`. A maestro lê aquilo, vê que os
checks ficaram verdes minutos depois, e segue a vida.

Doze horas e meia depois (PR aberto às 01:49:41Z, conferido às 14:18Z) o PR
continua exatamente onde estava:

```
$ gh pr checks 1160
muralhas          pass    2m14s
ci-celula-gate    pass    1m03s
... 7 de 7 pass, verdes desde a primeira hora

$ gh pr view 1160 --json comments -q '.comments | length'
0

$ gh pr view 1160 --json labels -q '[.labels[].name]'
[]

$ git log origin/main --oneline --since=2026-09-06T01:49:41Z | wc -l
74
```

Os sete checks verdes, ZERO comentários (a pista comenta em TODO PR que atende,
então nenhum comentário é a prova de que ela nunca foi acionada), nenhuma
etiqueta `pousar`, e o PR já passou de `CLEAN` a `BEHIND` porque a `main` andou
74 commits por cima dele. Um único `python ci/mergear.py 1160 --pousar` rodado à
mão pôs o PR na fila, e ele pousou em 3 minutos (merge commit `c789a0bf`, às
14:18:49Z). Não havia nada de errado com o PR: faltava alguém pedir o pouso.

## Causa

**A espera armada pela ferramenta `Monitor` dentro da sessão de um sub-agente
não sobrevive ao fim daquela sessão.** O `despacho` reporta "pouso armado" de
boa-fé, porque ele de fato armou. Só que o processo do
`ci/esperar.py --checks <N> --e-pousar` morre junto com o turno dele, e o turno
dele acaba em segundos: bem antes de os checks ficarem verdes, que é o único
instante em que aquele comando teria feito alguma coisa. Nenhum pedido de pouso
chega à pista, e o PR fica órfão: verde, pronto e parado, sem ninguém para
empurrá-lo.

O `--e-pousar` não falhou. Ele nunca chegou a rodar até o fim.

**A confusão que fez isso durar doze horas, e que é a metade mais importante
desta lição.** A `armadilhas/355` ensina que "o despacho que parece morto está
vivo: não redispare". Isso continua certo, e a maestro estava obedecendo. Mas
ela leu aquilo como **não confira**, e são coisas diferentes:

- **não redisparar** é sobre não duplicar trabalho, e custa caro errar;
- **conferir** custa dois segundos e não duplica nada.

E a prova que separa um despacho vivo de um PR órfão NÃO é a tela de checks
verdes nem o texto do relatório: é a **etiqueta `pousar` no PR**. É a mesma
prova que a `armadilhas/310` já apontava para o caso vizinho (lá o `--e-pousar`
rodava e o portão devolvia ERROR; aqui ele nem roda). Nas duas, a frase que
fica é a mesma: nenhum relatório de robô substitui uma consulta ao GitHub.

## Solução

**O despacho nunca arma o pouso automático.** A ficha `.claude/agents/despacho.md`
foi corrigida no mesmo PR desta entrada: o despacho devolve o NÚMERO DO PR à
maestro no relatório, e ponto. Quem arma a espera é a maestro, cuja sessão
sobrevive ao turno porque é ela quem conversa com o mantenedor.

E antes de dar qualquer despacho por fechado, a maestro faz a consulta de dois
segundos. Se a etiqueta `pousar` não estiver lá, o pouso não foi pedido, por
mais verde que a tela esteja.

```bash
# a maestro arma a espera na PRÓPRIA sessão, que sobrevive:
python ci/esperar.py --checks <N> --teto 20 --dizendo "os checks do PR <N>" --e-pousar
# e a prova de dois segundos, antes de dar um despacho por fechado:
gh pr view <N> --json state,labels -q '{estado:.state, etiquetas:[.labels[].name]}'
```
