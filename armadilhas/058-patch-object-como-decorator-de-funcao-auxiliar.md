<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.6  ·  referencias antigas "ARMADILHAS §6.6" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.6 `@patch.object` como decorator de função auxiliar embaralha os argumentos

**Sintoma:** `AttributeError: 'str' object has no attribute 'post'` — silencioso até
quebrar longe da causa.
**Causa:** decorar uma função **auxiliar** (não um método de teste) injeta o mock como
**último** argumento posicional, depois dos que o chamador passou. E sob `mypy --strict`
o decorator não esconde o parâmetro: toda chamada reprova com `Missing positional
argument`.
**Solução:** não decore a auxiliar — use `with patch.object(...):` **dentro** dela.
Resolve a ordem dos argumentos e o mypy de uma vez.
**Origem:** Prompt 3b (pagamentos, PR #19).
