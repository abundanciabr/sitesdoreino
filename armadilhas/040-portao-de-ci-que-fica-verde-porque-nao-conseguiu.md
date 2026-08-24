<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.6  ·  referencias antigas "ARMADILHAS §5.6" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.6 Portão de CI que fica verde porque *não conseguiu* medir

**Sintoma:** um portão imprime `✅ ... OK` (exit 0) e, logo acima, o `git`/`python`
gritou `fatal:` ou `command not found`.
**Causa:** o padrão `X=$(comando || true)` seguido de `if [[ -z "$X" ]]; then
echo "nada a fazer"; exit 0; fi`. Falha da ferramenta e "não há nada a verificar"
chegam ao `if` com o mesmo valor — vazio.
**Solução:** separar os três casos. Modelo usado em `ci/cerca-de-celula.sh`,
`ci/cross-smoke.sh` e `ci/orcamento-de-mudanca.sh`:

```bash
if ! DIFF="$(git diff --name-only "$BASE"...HEAD)"; then
  echo "❌ ERROR <portao>: não foi possível calcular o diff."   # não consegui medir
  exit 2
fi
if [[ -z "$DIFF" ]]; then echo "SKIP <portao>: git leu o diff e não há nada"; exit 0; fi
```

O mesmo vale para `git grep`, cujo exit code tem TRÊS significados: `0` achou, `1` não
achou, `>1` **erro** (ver `ci/guarda-de-segredos.sh`). Tratar `>1` como "não achou" faz
a guarda de segredos passar sem ter varrido nada.
**A versão em YAML da mesma armadilha:** em `.github/workflows/ci-celula.yml`, o
`git diff ... | head -1 || true` fazia falha de git virar "nenhuma célula tocada" ⇒ job
de teste pulado ⇒ veredito final aceitava `skipped` como verde ⇒ **merge sem um único
teste ter rodado**. Hoje a detecção usa `python ci/ci.py --detectar-celulas` e carimba
que concluiu; sem o carimbo, o gate é vermelho.
**Origem:** auditoria dos portões no PR #22.
