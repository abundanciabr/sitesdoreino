---
schema_version: 2
armadilha: 308
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: o portão continua dono da decisão e não pode ser afrouxado por um laço de retentativa; o guarda é o PAR de testes (o ERROR se remede, o FAIL nunca se remede), porque um teste só permitiria trocar um pelo outro sem ninguém notar
sinal:
  - "o portão RECUSOU o pouso do PR"
  - "O GitHub calcula isso de forma assíncrona"
  - "MOTIVO-DA-RECUSA: BASE-VELHA"
---

# O pouso automático morre justamente no instante em que o verde chega

**Sintoma.** `python ci/esperar.py --checks N --e-pousar` faz tudo certo: espera,
anuncia todos os checks verdes e chama o portão. E o portão recusa na hora:

```
✅ os checks do PR #954: todos os 7 checks verdes · levou 49s.
🛬 checks verdes: passo pelo portão e peço pouso do PR 954…
   --- ERROR conflitos ---
   O GitHub calcula isso de forma assíncrona; se você acabou de dar push,
   espere alguns segundos e rode de novo.
   RESULTADO  ERROR
🔴 o portão RECUSOU o pouso do PR 954 (exit 2)
```

O mesmo `python ci/mergear.py 954 --pousar` rodado à mão trinta segundos depois
passa sem reclamar de nada.

**Causa.** O GitHub calcula `mergeable` de forma assíncrona, e o gatilho desse
recálculo é a árvore mudar embaixo do PR. Ou seja: o campo fica `UNKNOWN`
exatamente na janela em que o último check acaba de virar verde, que é o único
instante em que o `--e-pousar` chama o portão. A automação não estava com azar,
estava mirando no pior segundo possível, todas as vezes.

Medido em 03/09/2026, num lote de cinco frentes: os dois primeiros PRs
(`#954` e `#956`) morreram aqui, um atrás do outro, e os dois pousaram com um
`--pousar` repetido à mão. Uma automação que falha 2 de 2 não é automação.

**Solução.** `pousar_pelo_portao` remede o portão quando, e só quando, a recusa
foi `ERROR` com a marca do recálculo do GitHub. Seis voltas de vinte segundos,
falando a cada uma, e então desiste. É a lição 3 do Lote 10
(`RUNBOOK-LOTES.md` §9) aplicada onde ela ainda não estava: **`FAIL` é sobre o
PR e nunca melhora sozinho; `ERROR` é "não consegui medir" e é a única recusa
que se remede.**

A cura tem duas metades, e a segunda é a que impede a primeira de virar
teimosia:

```python
recalculando = proc.returncode == 2 and MARCA_DO_GITHUB_RECALCULANDO in saida
if not recalculando or volta == VOLTAS_DE_REMEDICAO:
    break
```

Sem a marca no teste, remedir "toda recusa" passaria no guarda do ERROR e
transformaria dívida do livro e base velha em seis tentativas inúteis, cada uma
escondendo o motivo real atrás de vinte segundos de silêncio.

O código de saída também passou a preservar a distinção: `1` é reprovado, `2` é
não consegui medir, o mesmo `2` do estouro de teto. Um lote automatizado que
lesse "o GitHub não decidiu" como "o PR foi reprovado" mandaria um robô
consertar código que está certo.

**Prova.** `ci/tests/test_espera.py`, três guardas com portão de mentira roteirado
(uma resposta diferente por chamada). Vermelho contra a versão anterior: 2 de 3
falham. As duas mutações deliberadas, cada uma sozinha, depois do verde:

| mutação | quem cai |
|---|---|
| a marca do recálculo nunca casa (a remedição some) | o guarda do ERROR e o guarda do teto |
| remedir qualquer recusa (`returncode != 0`) | o guarda do FAIL e o guarda antigo da recusa |

**Onde mais isto vale.** Em qualquer lugar que trate o retorno de um portão como
booleano. A casa já tem a lei escrita (`FAIL ≠ ERROR`, `[INV-CI01]`), e ela caiu
aqui pelo mesmo motivo do Lote 10: saber a armadilha não protege, executar o
passo protege, e quando o passo é automático a distinção tem de estar dentro do
automatismo.
