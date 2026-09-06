---
schema_version: 2
armadilha: 355
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o harness avisa "completed" toda vez que um sub-agente para de falar, inclusive quando ele só armou uma espera e vai acordar de novo; nenhum portão do repositório vê isso. O que existe é a consulta de dois comandos deste arquivo, feita pela maestro antes de disparar qualquer "retomada"
sinal:
  - Aguardo a notificação do processo
  - Espera em curso, sem nada a fazer até o próximo evento
  - status>completed</status
  - duas sessoes na mesma bancada
---

# O despacho que "terminou" está vivo: a retomada dobra o robô e suja a bancada

**Data:** 05/09/2026 · **Onde:** sessão-maestro do lote das alavancas de 10x (PRs #1128 e #1130) · **Custo evitado:** um robô inteiro de retomada (2 mil turnos de contexto), 3 testes fantasmas reprovando por corrida entre duas sessões na mesma bancada, e um PR quase aberto em dobro.

## Sintoma

A maestro dispara um despacho em fundo. Chega a notificação do harness dizendo
que o agente terminou, com um texto assim:

```
<status>completed</status>
<result>A suíte completa está rodando na bancada (Monitor armado, teto 40 min).
O commit do código já está feito; o rebase e o push esperam a suíte terminar.</result>
```

A maestro lê "completed" mais "o push espera", conclui que o robô morreu antes
de entregar, e dispara um segundo despacho para "retomar" a mesma bancada. O
segundo robô encontra a bancada limpa, roda a suíte de novo, e no meio dela os
arquivos mudam sozinhos: o primeiro robô estava vivo, fez o rebase, abriu o PR
e commitou o registro. Resultado medido em 05/09/2026:

```
3 failed, 1763 passed in 1320.52s
  test_verificar_painel::test_passa_no_repositorio_real
  test_muralha_do_painel::test_passa_no_repositorio_real
  test_registro_novo_e_MATERIALIZADO_e_nao_reprovado
  -> "20260905-086-... está num arquivo de mês e o Git NÃO o conhece"
```

Nenhum dos três era defeito: era o registro que o primeiro robô tinha escrito
no disco e ainda não tinha adicionado ao índice. O segundo robô quase abriu um
PR em dobro, e só não abriu porque conferiu `gh pr list` antes.

## Causa

A notificação `completed` do harness dispara **toda vez que o sub-agente para
de falar sem filho vivo aos olhos dele**, e uma espera armada pela ferramenta
`Monitor` não conta como filho: o agente cala, o harness avisa "terminou", e
quando o evento da espera chega o agente acorda e continua. A própria nota da
notificação diz isso em letra pequena ("the same task-id may notify more than
once"), e o texto do resultado diz "aguardo": os dois sinais estavam na tela e
a leitura apressada de "completed" venceu.

O mesmo despacho notificou "completed" **onze vezes** naquela tarde, uma por
evento da espera, e entregou no fim. Um despacho que espera checks de PR pelo
rito da casa (`esperar.py --e-pousar` pela `Monitor`) vai parecer morto a cada
volta da espera.

## Solução

Antes de disparar qualquer "retomada" de bancada, dois comandos, e só depois a
decisão:

```bash
git -C ../wt-<area>-<tarefa> log --oneline origin/main..HEAD   # há commits? o ramo anda?
gh pr list --head agent/<area>/<tarefa> --json number,state     # o PR já existe?
```

Se o ramo andou depois da notificação, ou o PR existe, o robô está vivo:
**não retome**. Espere a próxima notificação; ela vem. Se o resultado da
notificação contém "aguardo", "espera armada" ou "Monitor", é espera, não
morte, por definição.

Se for preciso mesmo assumir a bancada (o robô parou há mais de uma hora sem
espera armada, ou a máquina reiniciou), assuma **você**, na sessão-maestro, em
vez de disparar outro robô: um agente novo não conhece o que o anterior deixou
e vai remedir tudo. E nunca duas sessões na mesma bancada ao mesmo tempo: a
suíte de uma lê os arquivos da outra no meio da escrita.

Segunda lição, do mesmo lote: um despacho que roda a suíte inteira em fundo
(`run_in_background`) e termina o turno esperando o resultado é exatamente o
caso que produz a notificação enganosa. A suíte da bancada se roda em primeiro
plano, com o teto do próprio comando, e o turno só termina com o veredito na
mão.
