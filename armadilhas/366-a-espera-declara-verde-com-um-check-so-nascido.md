---
schema_version: 2
armadilha: 366
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: o `ci/esperar.py --checks` mede "todos os que EXISTEM completaram" e não tem, hoje, a lista de checks obrigatórios que o `ci/mergear.py` exige — são dois julgamentos do mesmo fato, e só o segundo é completo. Fechar o buraco é ensinar a espera a esperar os obrigatórios NASCEREM (a lista já está no portão), e isso é conserto em `ci/`, caminho CODEOWNERS. Enquanto ele não existir, o que segura é o próprio portão recusar o pouso — nenhum PR entra por causa desta falha, só se perde o pedido
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

**Solução, hoje.** Se a espera devolver verde em menos de meio minuto, ou citar
um número de checks menor que o normal do repositório (sete, em 09/2026), NÃO
trate como verde: confira quantos existem e arme de novo.

```bash
gh pr checks <N>                    # quantos nasceram até agora
gh run list --branch <ramo> --limit 10 --json name,status,conclusion
```

Com todos nascidos, a mesma espera de sempre resolve, e o pouso sai:

```bash
python ci/esperar.py --checks <N> --teto 20 --dizendo "os checks do PR <N>" --e-pousar
```

**Solução definitiva** (registrada na fila): ensinar `ci/esperar.py` a esperar
os checks OBRIGATÓRIOS nascerem, usando a mesma lista que o `ci/mergear.py` já
conhece. Enquanto forem dois julgamentos separados do mesmo fato, eles vão
divergir de novo — é a Classe do "falso-verde por universo incompleto", a mesma
que já mordeu esta casa no H13 (os greens históricos do deploy-celula) e na
regra de nunca ler veredito de run pelo exit de um pipe.
