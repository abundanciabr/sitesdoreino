---
schema_version: 2
armadilha: 212
estado: guardada
degrau: 3
confianca: estrutural
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_espelho_do_alarme_em_pr.py
sinal: null
---

# O check de PR ficou verde porque mediu a árvore que ELE MESMO acabou de modificar

**Sintoma.** Um PR fecha com todos os checks verdes — inclusive o required — e a
`main` fica vermelha logo depois do merge, na MESMA suíte de testes. Quem for
olhar vai encontrar o mesmo `pytest`, os mesmos arquivos, o mesmo comando, com
dois vereditos opostos. E a explicação que salta aos olhos ("essa suíte não roda
em PR") está errada: ela roda.

**Medido em 30/08/2026** (PR #580, TAR-022/TAR-025). O job `muralhas` roda dois
steps, nesta ordem:

```
python ci/ci.py --apenas muralhas    ← chama ci/muralha-do-indice.sh
python ci/ci.py --apenas testador    ← chama pytest ci/tests
```

O primeiro **materializa** `armadilhas/INDICE.md`, `GUARDAS.json` e
`SINAIS.json` (é literalmente a função dele). O segundo mede o disco **depois**
disso. O `alarme-main`, depois do merge, roda o mesmo `pytest ci/tests` num
checkout cru, onde os três não existem.

Reprodução na árvore exata do commit `caaeb2e8` (`git archive` do commit +
`pytest ci/tests`):

```
árvore crua, como o runner do alarme a viu ......... 29 reprovas
depois de a muralha materializar de passagem ....... 24 reprovas
```

As 5 de diferença são as que derrubaram a `main` — entre elas
`test_o_sinal_do_repositorio_real_e_lido_pelo_sino`, morrendo em
`JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. (As 24 comuns
vêm da árvore sintética da reprodução e são idênticas dos dois lados, logo se
cancelam: o número que decide é a DIFERENÇA.)

**Causa.** Um step que ESCREVE no repositório antes de um step que MEDE o
repositório faz o check de PR observar um mundo mais rico do que o mundo que a
`main` vai ter. Não é falso-verde por não ter medido (`armadilhas/123`, H13): é
falso-verde por ter medido **outra coisa**, e essa é pior, porque a saída é
indistinguível de uma medição correta. Enquanto a ordem for essa, essa classe de
quebra é invisível para o PR **por construção** — nenhuma quantidade de testes
novos ajuda.

**Solução (30/08/2026, TAR-025).** Um job de PR que é o job de push copiado
passo a passo, com checkout limpo e nada escrevendo antes: `espelho-da-main` no
`muralhas.yml` é o `guardas-do-repositorio` do `alarme-main.yml`. É a
RETROSPECTIVA-FASE-D §3 (a prova vem de fora) aplicada ao próprio portão: o PR
passa a ser medido pelo instrumento e na árvore que a `main` vai usar.

Três decisões que não são óbvias:

| decisão | porquê |
|---|---|
| job separado, não reordenar os steps | reordenar consertaria este caso e deixaria a garantia dependendo de uma ORDEM que ninguém enxerga no diff |
| o `muralhas` continua rodando a suíte | ele é o required check do conjunto de regras; tirar a suíte de lá enfraqueceria o único caminho que o botão de merge do site respeita |
| cópia guardada por teste | cópia sem guarda apodrece: `test_espelho_do_alarme_em_pr.py` compara os dois jobs passo a passo e reprova quem mudar um só |

Custo medido (run 33315506488): o `muralhas` leva 71 s, o `painel-no-navegador`
49 s em paralelo; o espelho fica na mesma faixa e roda junto — o relógio do PR
não muda.

**A regra que fica, maior que o caso:** quando um check de PR e um check de push
rodam o MESMO comando, pergunte se eles rodam na mesma árvore. Se algum step
anterior escreve no repositório, eles não rodam — e o verde do PR é uma
afirmação sobre um mundo que não vai existir. **A cura é um espelho: o que vai
rodar depois do merge, rodando antes dele, com nada escrevendo no meio.**

**Por que esta entrada não tem `sinal`, declarado em vez de fingido:** o sintoma
não tem mensagem própria. Ele é a AUSÊNCIA de vermelho no PR, e depois um
vermelho na `main` cuja mensagem pertence ao teste que quebrou, não a esta
armadilha. Um `sinal` aqui casaria a mensagem de outra entrada e tocaria o sino
no lugar errado. Quem guarda esta lição é o teste, não o sino.

**Categoria** (`RETROSPECTIVA-FASE-D`): falso-verde · prova de fora · garantia
sem mecanismo. **Origem:** TAR-025, aberta a partir da `main` vermelha de
30/08/2026 (PRs #580 e #591).
