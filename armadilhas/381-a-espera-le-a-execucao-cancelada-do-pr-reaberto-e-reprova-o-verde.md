---
schema_version: 2
armadilha: 381
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: ci/tests/test_espera.py
  motivo: são DOIS testes porque a regra tem dois lados que se disfarçam um do outro - a cancelada VELHA não pode reprovar, e a cancelada ATUAL tem de reprovar; um teste só permitiria trocar a cura por um "ignore tudo que estiver CANCELLED", que passaria verde e cegaria a espera para o cancelamento de verdade
gatilho:
  - ci/esperar.py
  - ci/mergear.py
licao: o `statusCheckRollup` devolve UMA ENTRADA POR EXECUÇÃO, não por check. Quem for ler esse campo desdobra por NOME primeiro, com `mais_recente_por_nome` de `ci/mergear.py` IMPORTADA. Uma terceira leitura do mesmo fato é uma terceira chance de os portões discordarem entre si.
---

# A espera lê a execução CANCELADA do PR reaberto e anuncia REPROVADO num PR verde

**Sintoma.** A espera dos checks de um PR (`--checks <N> --e-pousar`) termina
assim, e o pouso nunca sai:

```
🔴 os checks do PR 1136: terminou REPROVADO — checks REPROVADOS: conferir o
   toca declarado · levou 0s.
```

No mesmo instante, `gh pr checks <N>` diz `pass` naquele mesmo check, e
`python ci/mergear.py <N> --pousar` — que é a fonte de direito — aprova o PR
sem uma ressalva. Três instrumentos da mesma casa, dois vereditos.

**Causa.** Medido em 05/09/2026, no Rito de Contrato do PR #1136. A receita da
`armadilhas/077`, para a etiqueta que o workflow não enxerga, manda **fechar e
reabrir o PR** para forçar um evento novo. Ela funciona, e deixa rastro: a
execução antiga fica pendurada no `statusCheckRollup` com `CANCELLED`, ao lado
da nova que passou. O rollup passa a ter duas entradas com o **mesmo nome de
check**:

```
conferir o toca declarado | COMPLETED | CANCELLED | 23:44:05
conferir o toca declarado | COMPLETED | SUCCESS   | 23:44:14
```

`gh pr checks` mostra uma linha por nome e diz `pass`. `ci/mergear.py` desdobra
por nome desde 25/08/2026 (`armadilhas/113`) e aprova. A espera lia o rollup
CRU, achava a `CANCELLED` na lista e reprovava. Duas soluções da casa se
atropelavam: quem seguisse a 077 levava um falso vermelho da espera.

**E falso vermelho é o pior defeito que um portão pode ter.** Vermelho errado
não é conservador: ele ensina o robô e o dono a ignorar o portão, e um portão
que se ignora é um portão morto. É a mesma frase da `armadilhas/113`, dita de
novo porque o mesmo defeito voltou por outra porta.

**Solução.** A regra do desdobramento **passa a ser uma só, importada**, nunca
copiada — o mesmo desenho das duas vacinas de deploy (`armadilhas/127`):

```python
# ci/esperar.py
from mergear import mais_recente_por_nome
...
rollup = mais_recente_por_nome(bruto)
```

A função perdeu o underscore de privada em `ci/mergear.py` porque virou
contrato entre dois módulos, e `ci/tests/test_espera.py` prova que os dois
chamam a MESMA função (`esperar.mais_recente_por_nome is
mergear.mais_recente_por_nome`), não duas cópias que podem divergir no dia em
que alguém mexer numa só.

O desempate continua **fail-closed**, e é ele que separa esta cura de um
atalho: hora diferente ⇒ vale a mais recente, **inclusive quando ela é a
pior**; sem hora, ou hora igual ⇒ fica a pior das empatadas. "Ignore tudo que
estiver `CANCELLED`" teria consertado o sintoma e cegado a espera para o
cancelamento de verdade — por isso a guarda são dois testes, um para cada
lado.

**Origem:** medido pela maestro no Rito de Contrato do PR #1136, 05/09/2026;
consertado na TAR-204, em 07/09/2026. **Categoria**
(`RETROSPECTIVA-FASE-D`): mesma verdade em dois lugares (dois leitores do
`statusCheckRollup`, um deles ingênuo) · cura de uma armadilha virando gatilho
de outra (a 077 alimenta esta).
