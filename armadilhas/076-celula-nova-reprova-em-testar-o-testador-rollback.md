# Célula nova reprova em `testar-o-testador`: `Right contains one more item: '<celula>'` — a lista fixa de `rollback.yml`

**Sintoma:** você cria uma célula nova, declara-a em `ci/manifesto-de-contratos.json`
como o próprio arquivo manda ("Ao criar uma célula nova, declare-a aqui no mesmo PR"),
o `make ci` da célula fica verde, as três muralhas ficam verdes — e o portão
`testar-o-testador` reprova com isto:

```
___________ test_opcoes_de_celula_do_workflow_batem_com_o_manifesto ___________
>       assert sorted(opcoes) == sorted(manifesto["celulas"])
E       AssertionError: assert ['alunos', 'c...sageria', ...] == ['alunos', 'c...sageria', ...]
E         Right contains one more item: 'sugestoes'
ci\tests\test_rollback.py:448: AssertionError
```

O mesmo vermelho aparece no check `muralhas` do PR (é ele que roda
`python ci/ci.py --apenas testador`) e depois no `alarme-main`.

**Causa:** o `workflow_dispatch` de `.github/workflows/rollback.yml` declara a célula
como `type: choice`, e **choice do GitHub Actions não aceita lista dinâmica** — as
oito células estão escritas à mão em `options:`. `ci/tests/test_rollback.py` exige
paridade exata entre essa lista e as chaves de `celulas` no manifesto, com um motivo
que está escrito no próprio teste: *"Se uma célula nova nascer e a lista aqui não
crescer, ela fica sem rollback — e ninguém descobre isso às 2h da manhã"* (RITOS §4).

Logo: **declarar a célula no manifesto obriga a mexer em `.github/`, no mesmo PR.**
Os dois arquivos são um par, exatamente como o manifesto e `services/<celula>/` são.

⚠ **`docs/caixa-de-sugestoes/AUDITORIA-AS-IS.md` Q4 diz o contrário** — a tabela
"o que uma célula nova precisa tocar para existir de ponta a ponta" marca
`.github/` como "❌ nada" nas duas linhas de workflow. A auditoria mediu
`ci-celula.yml` e `deploy-celula.yml` (que de fato detectam a célula sozinhos) e não
mediu `rollback.yml`, que não detecta nada. Quem se guiar por aquela tabela descobre
isto pelo vermelho, já com o PR aberto.

**Solução:** uma linha em `.github/workflows/rollback.yml`, no mesmo PR que declara a
célula no manifesto:

```yaml
        options:
          - pagamentos
          - quiz
          - <celula-nova>      # <- ordem alfabética, como as outras
```

**O que fazer se você não tiver mandato para `.github/`:** esse é o caso normal, e é
caminho **CODEOWNERS**. Não contorne (afrouxar o teste é proibido — RITOS §2.3), não
tire a célula do manifesto (o freeze reprova célula em `services/` não declarada, e o
PR fica pior). Abra o PR com o vermelho **nomeado no corpo**, diga qual é a linha
exata que falta, e peça o mandato a quem despachou. Um despacho de gênese de célula
deveria já nascer com esse mandato — vale pedir na primeira resposta, não no fim.

**Origem:** despacho EVO-10 (gênese da célula `sugestoes`, Lote 1 da Caixa de
Sugestões), 24/08/2026. O despacho listava `.github/` como fora de escopo, com base
na Q4 da auditoria; o portão provou que a Q4 estava incompleta.
