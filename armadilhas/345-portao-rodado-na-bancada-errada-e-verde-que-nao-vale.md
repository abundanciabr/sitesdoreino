---
schema_version: 2
armadilha: 345
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  detector: ""
  motivo: nenhum portão sabe qual bancada VOCÊ quis medir; o comando estava certo e a resposta era verdadeira sobre a pasta em que rodou
sinal:
  - `RESULTADO  PASS` seguido de PR reprovado no mesmo portão
---

# Portão rodado na bancada errada é verde que não vale

**Sintoma.** Você roda o portão da casa antes de mandar o PR, lê `RESULTADO
PASS`, manda, e o mesmo portão reprova na pista:

```
  mapa-do-site          PASS   ✅ O mapa do site diz a verdade sobre o roteamento e o código.
```

...e, minutos depois, no PR:

```
  cobertura           FAIL   o mapa e o código discordam sobre que endereços existem
  - FALTA no mapa: admin → 'caixa/analise/'
```

Aconteceu em 05/09/2026: o PR #1074 voltou vermelho em três checks depois de um
`ci/ci.py --apenas muralhas` verde rodado dez minutos antes.

**Causa.** Trabalhar com várias bancadas ao mesmo tempo é o normal desta casa
(uma por tarefa, RITOS §1), e o `cd` da vez decide o que o portão mede. O verde
tinha sido colhido em `wt-lei-entrega-no-site` — uma bancada que **não tem a
rota nova**. O portão respondeu a verdade: naquela pasta, o mapa e o código
concordavam mesmo.

Nada acusa. O comando é o certo, a saída é a real, e a única coisa errada é a
pasta — que não aparece em lugar nenhum da saída.

**Solução.** Rodar o portão **da bancada do PR**, e provar isso na mesma linha:

```bash
cd ../wt-<area>-<tarefa> && pwd && python ci/ci.py --apenas muralhas
```

O `pwd` colado no comando é o remédio inteiro: ele põe a pasta na mesma tela do
`RESULTADO`, e um verde de outra bancada fica visível na hora de ler.

**A régua, para a próxima vez:** verde de portão só vale com o caminho da
bancada ao lado dele. Sem isso, o que você mediu foi outra coisa com o mesmo
nome.

**Por que não tem guarda:** nenhum portão sabe qual bancada você QUIS medir. O
que existe do lado da pista é a medição de verdade, no ramo de verdade — e foi
ela que pegou o caso. O custo de cair aqui é uma rodada de CI, não um estrago.
