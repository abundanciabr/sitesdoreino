# PR que toca `painel/` não fecha a janela de merge — separe o PR em vez de tentar de novo

**Sintoma:** você tenta mergear e entra num laço que não termina. A cada volta o
motivo muda, e cada um parece um problema isolado:

```
conflitos          FAIL   o PR conflita com a base          ⟵ painel.html / livro-*.js
(rebase, regenera, push)
checks             ERROR  no checks reported                ⟵ conflito ⇒ armadilhas/150
(rebase de novo)
dívida do livro    FAIL   1 merge(s) sem registro           ⟵ de OUTRA sessão
(paga a dívida)
conflitos          FAIL   a base envelheceu (BEHIND)        ⟵ política estrita
(update-branch, espera 90s)
conflitos          FAIL   o PR conflita com a base          ⟵ e recomeça
```

Medido em 28/08/2026: um PR de **4 arquivos e nenhuma linha de código** levou
**oito tentativas**. O mesmo PR, depois de separado, mergeou de primeira.

**Causa — três coisas verdadeiras ao mesmo tempo, e nenhuma delas com defeito:**

1. **Todo PR que acrescenta um registro regenera `painel/painel.html` e
   `painel/livro-AAAAMM.js`**, que são arquivos grandes de linha única. Duas
   sessões que regeneram colidem SEMPRE — não é conflito de conteúdo, é o
   formato.
2. **A política estrita** (`strict_required_status_checks_policy`, ligada em
   28/08 pela Onda 0 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`) exige que o PR
   esteja em dia com a `main` **no instante do merge**.
3. **A `main` deste projeto anda ~98 vezes por dia.** Cada volta do ciclo
   (atualizar → checks → mergear) gasta ~90 s, e nesse intervalo ela anda de
   novo. Quanto mais sessões em paralelo, menor a chance de fechar a janela.

Não adianta ser mais rápido: o ciclo é limitado pelos checks, não por você.

**Solução — separe o PR, não insista no laço.** O conserto real é a Onda 3
(gerado com escritor único) e a Onda 4 (pista de pouso). Enquanto elas não
existem:

```bash
# 1. o trabalho de verdade, SEM tocar painel/  → mergeia sem disputar nada
git reset --hard origin/main
git checkout <sha-do-trabalho> -- <só os arquivos de código>
# commit, push, merge

# 2. os registros, num PR próprio e pequeno
```

O PR sem `painel/` não colide com ninguém, então só precisa vencer o `BEHIND` —
um `gh pr update-branch` e o merge sai. O PR dos registros continua disputando,
mas é pequeno e barato de repetir.

**Duas coisas que economizam volta:**

- **`gh pr update-branch` NÃO regenera nada.** Se o seu PR toca `painel/`, o
  gerado fica velho em relação aos registros que vieram da `main` junto, e o
  check `painel-no-navegador` reprova. Rode `node painel/gerar_manifesto.js` e
  commite **antes** de esperar o verde.
- **Antes de pagar dívida do livro de outra sessão, confira se ela já não pagou**
  (`python -c "...divida(...)"` ou `grep -l "pull/<N>" painel/registros/*.js`).
  Em 28/08 dois registros meus foram escritos e jogados fora porque outra sessão
  registrou o mesmo fato enquanto eu tentava mergear — Classe 5 do plano
  mestre, três vezes no mesmo dia.

**Não é para desligar a política estrita.** Ela fecha a colisão semântica, que é
o pior acidente já medido aqui (`armadilhas/134`). O laço é o preço declarado, e
tem data para acabar.

**Origem:** PRs #414 e #421, em 28/08/2026 — o primeiro com cinco voltas, o
segundo com oito até ser separado. **Categoria** (`RETROSPECTIVA-FASE-D`):
sessões paralelas · contexto é orçamento.
