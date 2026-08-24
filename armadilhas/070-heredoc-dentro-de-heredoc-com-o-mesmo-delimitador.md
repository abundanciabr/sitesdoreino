<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §8 — Ferramentas do agente (o harness também tem armadilha)
     ID historico: §8.2  ·  referencias antigas "ARMADILHAS §8.2" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 8.2 Heredoc dentro de heredoc com o mesmo delimitador

**Sintoma:** `SyntaxError: unterminated triple-quoted string literal` no Python, seguido
de `bash: syntax error near unexpected token`.
**Causa:** escrever um script Python via `python - <<'PY'` cujo conteúdo contém outro
heredoc `<<'PY'` — o delimitador interno fecha o externo antes da hora.
**Solução:** delimitadores distintos (`<<'PYEOF'` dentro de `<<'PY'`), ou escreva o
arquivo com a ferramenta de escrita em vez de heredoc. Vale para qualquer par aninhado.
**Origem:** sessão de 19/08/2026, ao endurecer `ci/freeze-de-contrato.sh`.
