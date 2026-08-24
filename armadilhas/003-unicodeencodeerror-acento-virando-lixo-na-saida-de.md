<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.3  ·  referencias antigas "ARMADILHAS §3.3" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.3 `UnicodeEncodeError` / acento virando lixo na saída de comando Django

**Sintoma:** saída com emoji ou acento quebra no terminal (cp1252).
**Solução:** `export PYTHONUTF8=1` antes de rodar qualquer coisa localmente.
**Origem:** Prompt 2 (catalogo, PR #15).
