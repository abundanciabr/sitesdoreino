---
schema_version: 2
armadilha: 366
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: teste
  dono: ci/tests/test_espera.py
  motivo: desde a TAR-141 (07/09/2026) o `ci/esperar.py --checks` faz as MESMAS duas perguntas do portão antes de dizer verde, com a lista de obrigatórios IMPORTADA de `ci/mergear.py`, nunca copiada. Sem os obrigatórios no rollup o alvo não apareceu e a graça mata a espera; com o PR em conflito ela para na hora e ensina o `git merge origin/main`. Provado por mutação: arrancada a pergunta, o teste devolve o falso-verde do #1020 e o pedido de pouso
sinal:
  - `todos os 1 checks verdes`
  - `ERROR checks obrigat[óo]rios`
---

# A espera declara VERDE com um check só nascido, e o pouso é recusado em seguida

**Sintoma.** Você abre o PR, arma a espera com pouso automático, e ela devolve
o verde em segundos, quando o normal são minutos:

```
⏳ 0s de 20min · 0 de 1 checks prontos
✅ todos os 1 checks verdes · levou 16s.
🛬 checks verdes: passo pelo portão e peço pouso do PR 1189…
```

Logo depois o portão recusa o pouso que ela mesma acabou de pedir:

```
--- ERROR checks obrigatórios -----------------------------------------
Estes checks precisam existir em todo PR. A ausência deles pode
significar workflow renomeado, desabilitado, ou que nem disparou —
e nenhuma dessas coisas é aprovação.
MERGE RECUSADO.
```

**Causa.** Os dois medem o mesmo PR e respondem perguntas diferentes. A espera
pergunta *"algum check está pendente?"* e, quando o GitHub ainda criou só um
deles, a resposta honesta é "nenhum" — ela declara verde sobre um universo de
um. O portão pergunta *"os checks obrigatórios estão todos aqui e verdes?"*, e
essa é a pergunta completa.

A janela é real e curta: entre o `gh pr create` e o nascimento dos sete checks
passam alguns segundos, e é exatamente aí que uma sessão eficiente arma a
espera. Em 06/09/2026 aconteceu no PR #1189, e custou um pedido de pouso
perdido mais uma rodada de espera. **Nada entrou indevidamente na `main`** — o
portão recusou, que é o desenho funcionando: a espera é conveniência, o portão
é autoridade.

O caso vizinho JÁ era tratado: a espera reconhece **zero** checks e aponta a
`armadilhas/150` (conflito com a main). O buraco é o "poucos", não o "nenhum".

**Solução definitiva, feita na TAR-141 em 07/09/2026.** `ci/esperar.py` deixou
de ter julgamento próprio: antes de qualquer verde ele faz as duas perguntas do
portão, na ordem do `--conferir`.

1. *O PR conflita com a base?* `CONFLICTING` para a espera na hora, com o que
   fazer escrito no desfecho (`git fetch origin && git merge origin/main`), em
   vez de esperar checks que não vão nascer (`armadilhas/198`).
2. *Os obrigatórios existem?* A lista é **importada** de `ci/mergear.py`, nunca
   copiada — copiada, um check obrigatório novo lá nasceria invisível aqui.
   Faltando algum, o alvo NÃO apareceu: a graça mata a espera nomeando o que
   falta, e o pouso nunca é pedido.

Era a Classe do "falso-verde por universo incompleto", a mesma que já mordeu
esta casa no H13 (os greens históricos do deploy-celula) e na regra de nunca ler
veredito de run pelo exit de um pipe. Enquanto foram dois julgamentos separados
do mesmo fato, divergiram duas vezes em três dias (#1020 e #1189); agora é um
julgamento só, com o teste de mutação em `ci/tests/test_espera.py`.
