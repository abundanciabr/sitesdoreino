---
schema_version: 2
armadilha: 386
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: fechar isto exige decidir o que é "o mesmo defeito", e nenhum dado do repositório responde isso sozinho. O evento de conclusão pela porta do pouso (`ci/fila.py`, em sombra desde 06/09/2026) fecha por CITAÇÃO, e uma tarefa que ninguém citou é justamente a que fica aberta. O que existe hoje é humano, e barato, e está escrito na Solução: antes de pegar a tarefa, procurar o defeito dela na `main`, não só o número dela na fila
sinal:
  - já está na main
  - CONFLICT (content) in ci/
---

# Duas tarefas descrevem o mesmo defeito, e duas sessões pagam pelo mesmo conserto

**Sintoma.** Você pega uma tarefa no balcão, constrói o conserto inteiro, e no
primeiro `git rebase` a `main` devolve um conflito no arquivo que você acabou
de escrever. Lendo o commit que colidiu, ele é a sua própria cura, entregue por
outra tarefa, algumas horas antes.

```
CONFLICT (content): Merge conflict in ci/esperar.py
git log --oneline HEAD..origin/main
  ci: a espera de checks faz as duas perguntas do portao antes de dizer verde
```

**Causa.** A fila guarda uma tarefa por SINTOMA MEDIDO, e o mesmo defeito
produz sintomas diferentes em dias diferentes. Em 07/09/2026 a `TAR-141` nasceu
de "a espera diz verde num PR em conflito" (PR #1020, 04/09) e a `TAR-226` de
"a espera diz verde com um check só nascido" (PR #1189, 06/09). São a mesma
pergunta que a espera não fazia, e quem consertou a primeira consertou as duas,
corretamente. A `TAR-226` continuou no quadro descrevendo trabalho já feito.

Nada no repositório percebe isso. O evento de conclusão pela porta do pouso
(`ci/fila.py`, em sombra desde 06/09/2026) fecha tarefa por CITAÇÃO: o PR
#1282 citou a `TAR-141`, que era a sua tarefa, e não tinha por que citar uma
tarefa que ele nem sabia que estava resolvendo.

**O que custou:** a `TAR-226` foi pega DUAS vezes no mesmo dia depois de já
estar resolvida. A primeira sessão morreu no minuto seguinte sem escrever nada
(e deixou a tarefa travada no balcão, `armadilhas/364`); a segunda construiu o
conserto inteiro, com testes, antes de o rebase contar a verdade. Duas sessões
pagas pelo que já estava na `main`.

**Solução, ao pegar qualquer tarefa.** O quadro diz que a tarefa está livre; ele
não diz que o DEFEITO está vivo. Antes de escrever a primeira linha, procure o
defeito na `main`, não o número da tarefa:

```bash
git fetch origin
git log --oneline -20 origin/main -- <o arquivo que a tarefa manda tocar>
```

Se algum commit recente mexeu ali, leia-o inteiro antes de continuar. Custa
segundos, e é a única leitura que responde "isto ainda existe?".

**Quando descobrir tarde**, com o conserto pronto: não empurre o que já existe.
Meça o que a `main` cobre, guarde só o que ela não tem, e feche a tarefa no
quadro apontando o PR que a resolveu de verdade — senão a próxima sessão paga
uma terceira vez.

```bash
python ci/fila.py concluir TAR-NNN --quem <voce> --evidencia <URL do PR que a fez> --verificado-em AAAA-MM-DD
```

**Origem:** 07/09/2026, `TAR-226`, resolvida na `main` pelo PR #1282 da
`TAR-141`. Parente: `armadilhas/364` (a espera que morre com a sessão e deixa o
PR órfão) descreve o outro jeito de uma tarefa ficar presa no balcão.
