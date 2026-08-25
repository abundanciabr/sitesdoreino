# O portão de merge reprova um check que o GitHub mostra VERDE — dois runs do mesmo workflow no mesmo commit

**Sintoma:** `python ci/mergear.py <N> --conferir` devolve

```
--- FAIL check/muralhas ----------------------------------------------
RESULTADO  FAIL
MERGE RECUSADO. Há algo reprovado acima.
```

e, no mesmo instante, `gh pr checks <N>` diz `muralhas  pass`, e a aba Checks do
PR está verde. Nada mudou entre as duas leituras. O PR fica intransponível pelo
caminho oficial, e o único jeito aparente de sair é o botão do site — que é
justamente o que o portão existe para tornar desnecessário.

**Causa:** o mesmo workflow rodou **duas vezes no mesmo commit**, e o GitHub
mantém as duas execuções penduradas naquele SHA. Medido em 25/08/2026, no PR
#187:

```
muralhas  conclusion=FAILURE  startedAt=2026-08-25T19:35:07Z   (antes da label)
muralhas  conclusion=SUCCESS  startedAt=2026-08-25T19:39:33Z   (depois da label)
```

O gatilho mais comum é o próprio rito da casa: `muralhas.yml` dispara em
`labeled`, então **aplicar a label `arquitetural`** — a válvula do orçamento de
arquivos — roda o workflow de novo no mesmo SHA. A primeira execução (a que
reprovou por orçamento) não some; ela fica ali para sempre.

`ci/mergear.py` percorria o `statusCheckRollup` emitindo **um veredito por
entrada**, sem desduplicar por nome. Resultado: dois `check/muralhas`
contraditórios no mesmo relatório, e o pior vencendo o agregado — para sempre.
`gh pr checks` e a interface do GitHub mostram só a execução mais recente de
cada nome, que é o que "o estado do check X" significa.

**Por que isto é pior do que um portão chato:** um portão que reprova o que está
comprovadamente verde não é conservador — ele **ensina a ser contornado**. É a
única maneira de matar uma catraca: fazê-la errar contra quem está certo.

**Solução:** desduplicar por **nome**, ficando com a execução de `startedAt` mais
recente (`completedAt` como reserva). E o desempate importa tanto quanto a regra:

* **hora diferente ⇒ a mais recente vale**, inclusive quando ela é a PIOR (um
  rerun que ficou vermelho tem de reprovar, mesmo com um verde antigo ao lado);
* **sem hora, ou hora igual ⇒ fica a PIOR das empatadas.** "Não consegui saber
  qual é a atual" jamais pode virar "então considero a verde" ([INV-CI01]).

Ver `_mais_recente_por_nome` em `ci/mergear.py`.

**A mutação que quase passou despercebida, e a lição de teste que ela deixou.**
Ao provar o conserto, três mutações ficaram vermelhas e uma **passou**: trocar a
comparação de hora por `if True` (= "fica sempre com a última entrada
percorrida") deixava a suíte inteira verde. Motivo: todas as fixtures tinham o
rerun no **fim** da lista, então a ordem acidental do dado concordava com a
regra errada. O `statusCheckRollup` não promete ordem nenhuma.

**Regra que generaliza, e vale para qualquer teste de desduplicação ou de "pegue
o mais recente": monte pelo menos um caso com a ordem INVERTIDA.** Sem ele, o
guarda passa a testar a ordem da fixture em vez da regra — e só descobre isso no
dia em que a API devolver na outra ordem.

**Origem:** lote 4 da Caixa de Sugestões, 25/08/2026, ao mergear o PR #187
(EVO-40) depois de abrir a válvula do orçamento com a label `arquitetural`.
