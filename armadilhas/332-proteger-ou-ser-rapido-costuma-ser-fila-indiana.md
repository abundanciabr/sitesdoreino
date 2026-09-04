---
schema_version: 2
armadilha: 332
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  detector: ci/tests/test_suite_em_paralelo.py
  motivo: o guarda prova que `-n auto` é USADO quando o xdist existe e que a suíte não passa a EXIGIR o xdist para rodar; a velocidade em si não se guarda por teste (mediria a máquina, não o código), então o número medido mora no comentário de ci/ci.py::_em_paralelo
sinal:
  - "unrecognized arguments: -n"
---

# "Proteger ou ser rápido" quase nunca é escolha: é fila indiana

**Sintoma.** Você acabou de construir uma proteção que valeu a pena — ela achou,
no primeiro dia, um defeito que ninguém via — e ela é lenta. O relógio do PR
pula de 1min36s (mediana de 44 casos) para 14min17s. Aí aparece a pergunta
errada, que soa madura e responsável:

> *A gente mantém a proteção e aceita a lentidão, tira ela do caminho do PR, ou
> roda ela só às vezes?*

Três opções, todas ruins, e nenhuma delas conserta nada. Foi exatamente esse
cardápio que eu apresentei ao mantenedor em 04/09/2026 — e ele respondeu com a
única pergunta que importava: **"como resolve isso definitivamente?"**

**Causa.** A pergunta pulou uma etapa: *por que* a proteção é lenta. Medido:

```
os doze testes mais lentos da suíte, um a um:  de 10s a 24s cada
o que todos eles fazem:                        abrir outros programas
fronteiras de subprocesso na suíte:            119
```

A suíte não era pesada, era **serial**. E criar processo no Windows custa perto
de dez vezes o que custa no Linux, então o mesmo trabalho que o runner Linux
fazia em 1min30s virava 9 minutos ali. Não era "o Windows é lento": era 1685
testes esperando a vez em fila indiana, num sistema onde a vez custa caro.

**Solução.** `-n auto` (pytest-xdist), ligado em `ci/ci.py::_em_paralelo`:

```
em série ...................... 8min55s
4 processos (= runner do CI) .. 3min31s
12 processos (a máquina toda) . 3min07s
```

Não é trade-off nenhum: o mesmo `-n auto` acelera os jobs Linux E a suíte local
de todo agente, que caiu de 9 para 3 minutos, todo dia, para sempre. A proteção
ficou inteira e o relógio do PR voltou para perto do que era.

Passar de 4 para 12 rende quase nada, e isso também ensina: o piso vira o teste
mais lento, que não se divide. Depois de paralelizar, o próximo ganho está em
tornar os doze lentos mais baratos, não em comprar mais núcleos.

**O condicional que faz parte da cura.** `_em_paralelo()` devolve `-n auto` SE o
xdist estiver instalado, e lista vazia se não estiver. Um portão que passa a
EXIGIR uma dependência nova quebra a máquina de quem só fez `git pull`, com
`pytest: error: unrecognized arguments: -n` — e portão que não roda não protege
ninguém. Quem não tem o xdist roda em série: mais devagar, igualmente correto.

**A régua que fica.** Quando a escolha se apresentar como "proteção OU
velocidade", **desconfie e meça primeiro**. Trade-off de verdade existe, mas é
mais raro do que parece; o caso comum é trabalho sequencial que ninguém nunca
cronometrou. Um cardápio de três opções ruins é o sintoma de que a medição não
foi feita — e oferecer esse cardápio é pior do que não perguntar nada, porque
faz o corte parecer decisão informada.

**E a régua de baixo, que é sobre como perguntar.** Quando você monta uma
pergunta para o mantenedor, ela carrega as opções que VOCÊ enxergou. Se a
melhor saída não estiver entre elas, ele vai escolher a menos ruim e o buraco
fica. Antes de abrir a caixa de pergunta, confira se está perguntando por não
saber o que ele quer, ou por não ter medido o suficiente para saber a resposta.
