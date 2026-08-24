<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.13  ·  referencias antigas "ARMADILHAS §5.13" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.13 `run: algo: coisa` sem aspas é `ScannerError: mapping values are not allowed here`

**Sintoma:** `yaml.scanner.ScannerError: mapping values are not allowed here`
apontando para uma linha de `run:` perfeitamente válida como shell — no caso,
`run: printf 'MOTIVO: %s
' "$MOTIVO"`. O GitHub recusa o workflow inteiro.
**Causa:** `: ` (dois-pontos + espaço) dentro de um escalar YAML **sem aspas**
abre um mapeamento. O comando estava certo; o YAML é que leu `run: printf 'MOTIVO`
como chave e o resto como valor.
**Solução:** escalar de bloco sempre — `run: |` na linha, comando embaixo. Custa
uma linha e imuniza contra `:`, `#` e `{}` no meio do comando.
**Como isto foi pego ANTES de chegar ao GitHub:** o teste de FORMA do workflow
(`yaml.safe_load` do arquivo real, em `ci/tests/test_rollback.py`) reprovou na
máquina. Todo workflow novo merece um: o YAML só é validado pelo GitHub depois do
merge, e workflow inválido é workflow que simplesmente não existe — sem alarme.
**Origem:** despacho infra/rollback-pelo-pipeline (23/08/2026).
