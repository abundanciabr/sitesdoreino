# `deploy-celula` cancelado NÃO é deploy adiado — aquela célula fica para trás, em silêncio

**Sintoma.** O PR pousou, todos os checks verdes, a `main` tem o código. Mas o
comportamento novo **não aparece no site**. Nenhum run vermelho, nenhum alarme:
o `deploy-celula` daquele merge aparece como `cancelled`, sem uma linha de log e
sem nenhum job.

```
22:31  cancelled  | Merge pull request #527 ... (sugestoes)
22:33  success    | Merge pull request #528 ... (identidade)
```

O `#528` verde logo abaixo dá a impressão de que "o deploy seguinte pegou tudo".
**Não pegou.** Ele publicou só a `identidade`.

**Causa — e ela é a soma de duas coisas certas.**

1. `concurrency: { group: deploy, cancel-in-progress: false }` guarda **um único
   run pendente por grupo**. Quando um merge novo chega, o pendente anterior é
   **cancelado** para dar a vaga ([173](173-workflow-manual-no-grupo-deploy-e-cancelado-antes-de-comecar.md)).
2. Cada run decide **quais células publicar** pelo diff do próprio push:
   `BASE='${{ github.event.before }}'`. O run seguinte tem como base o sha do run
   cancelado — então o diff dele **não contém** o que o cancelado teria
   publicado.

Junte as duas e o resultado é: **num dia movimentado, o merge que perde a vaga
de pendente não publica a célula dele, e o próximo merge não a publica no lugar
dele.** O código está na `main` e a imagem no ar é a anterior.

A 173 descreve a mesma mecânica, mas do ponto de vista de um `workflow_dispatch`
manual. Aqui o cancelado é um **deploy de merge**, e a consequência é outra: não
é um comando que não rodou, é uma célula que ficou para trás.

**Por que passa despercebido.** `cancelled` não é `failure`: o `alarme-main` não
dispara, `gh run list` mostra a linha em cinza no meio de verdes, e quem confere
"o deploy do meu merge" costuma olhar o run mais recente — que está verde, e é
de outra célula.

**Como reconhecer, em um comando.** Liste os deploys recentes com a conclusão e
procure `cancelled` cuja célula ninguém publicou depois:

```bash
gh run list --workflow deploy-celula --limit 15 --json displayTitle,conclusion,createdAt
```

**Solução: redisparar o run cancelado.**

```bash
gh run rerun <id-do-run-cancelado>
```

A imagem é construída a partir do **checkout naquele sha**, não do diff — o diff
só escolhe *quais* células entram na matriz. Então redisparar um run cancelado
publica aquela célula com tudo que a `main` tinha naquele ponto, inclusive o que
mergeou depois dele e antes do run.

**Duas armadilhas dentro da solução:**

- **Não redispare um run que deu `success`.** A segunda tentativa entra na mesma
  fila disputada, quase sempre é cancelada, e o que fica no histórico é um
  `cancelled` sobre um deploy que deu certo — exatamente o sinal que este
  arquivo ensina a procurar. (Aconteceu em 29/08/2026, no mesmo dia em que a
  armadilha foi descoberta.)
- **O redisparo também pode ser cancelado**, pelo mesmo motivo de sempre. Confira
  o veredito com `ci/esperar.py --run <id>`, nunca pelo exit do `gh run rerun` —
  ele devolve 0 só por ter enfileirado.

**A cura de verdade ainda não existe**, e é maior que este arquivo: enquanto a
detecção usar `event.before`, todo run cancelado é uma célula que ninguém
publicou. Um portão que compare *o que está na `main`* com *o que está no ar*,
por célula, fecharia a classe inteira — hoje o que existe é este arquivo e o
olho de quem confere.
