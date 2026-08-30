---
schema_version: 2
armadilha: 203
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: ci/tests/test_guarda_declarada_e_sino.py
sinal:
  - `entrada declara detector que a muralha não tem`
---

# `entrada declara detector que a muralha não tem` — você curou a armadilha com CÓDIGO PRÓPRIO e declarou `guarda: tipo: muralha`

**Sintoma.** Você construiu o mecanismo que cura uma armadilha, foi honestamente
atualizar o frontmatter dela de `tipo: nenhum` para uma guarda de verdade,
escolheu a palavra que descreve o que você fez — "é uma muralha, ela recusa" — e
apontou o `detector` para o seu arquivo:

```yaml
guarda:
  tipo: muralha
  detector: ci/fila.py
  dono: ci/tests/test_fila.py
```

`python ci/indice_de_armadilhas.py` aceita e regenera o índice sem reclamar. A
sua suíte passa. A suíte INTEIRA, cinco minutos e meio depois, não:

```
FAILED ci/tests/test_guarda_declarada_e_sino.py::test_todo_detector_declarado_existe_na_muralha
E  AssertionError: entrada declara detector que a muralha não tem: {'ci/fila.py'}
E  assert {'ci/fila.py', ...} <= {'crase_em_mensagem'}
```

**Causa.** No vocabulário deste projeto, `tipo: muralha` **não** quer dizer "um
mecanismo que recusa". Quer dizer uma coisa muito mais estreita: **uma regra de
`ci/muralha_das_armadilhas.py`**, o detector de texto que casa a assinatura de
uma armadilha e toca o sino. Por isso o campo se chama `detector` e por isso
existe um teste que cruza os dois lados: nome declarado no frontmatter ⊆ nomes
reais em `muralha.REGRAS`. O índice não faz essa conferência — ele valida o
schema, não a existência do detector; quem prova que os dois concordam é o
teste, e ele só roda na suíte inteira.

**Solução.** Guarda que é **código seu + teste-guarda seu** é `tipo: CI`, com
`dono` apontando para o teste. Sem `detector` — ele é do vocabulário da muralha,
não do seu:

```yaml
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
```

Os seis tipos aceitos (`ci/indice_de_armadilhas.py`) e o que cada um significa
de verdade:

| `tipo` | quando é este |
|---|---|
| `muralha` | regra de `ci/muralha_das_armadilhas.py` — exige `detector` com o nome REAL da regra |
| `sino` | detector em sombra que avisa e não reprova |
| `CI` | código próprio + teste-guarda; `dono` = o arquivo de teste |
| `teste` | um teste-guarda, sem mecanismo próprio |
| `vacina` | a família do `ci/rerun_de_deploy.py` |
| `nenhum` | buraco assumido — **exige `motivo`** |

**A regra que fica, e ela é maior que este campo:** ao preencher um vocabulário
fechado de outra pessoa, a palavra que descreve bem o que você fez **não é
necessariamente a palavra que aquele vocabulário usa**. Antes de escolher, leia
onde o valor é CONSUMIDO — aqui, `test_guarda_declarada_e_sino.py` — e não só
onde ele é validado. E rode a suíte inteira antes de abrir o PR: este erro só
aparece lá, e a rodada custa quase seis minutos.

**Origem.** 30/08/2026, TAR-018 (a cura do comprovante órfão da fila,
`armadilhas/192`, PR #582). A guarda nova era real — `ci/fila.py` recusando no
clone principal, com 7 testes vermelhos sem ela — mas foi declarada com a
palavra errada, e o único sinal foi a suíte completa reprovando cinco minutos
depois. **Categoria** (`RETROSPECTIVA-FASE-D`): não afirme viabilidade sem ler a
configuração — aqui, sem ler quem consome o campo.
