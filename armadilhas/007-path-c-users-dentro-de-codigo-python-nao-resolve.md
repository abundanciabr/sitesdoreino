<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.7  ·  referencias antigas "ARMADILHAS §3.7" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.7 Path `/c/Users/...` dentro de código Python não resolve

**Sintoma:** o mesmo caminho funciona como argumento no bash e falha dentro do script.
**Causa:** o `python.exe` nativo do Windows não entende paths estilo MSYS quando eles
são **literal de string no código** — só quando o próprio Bash converte o argv.
**Solução:** dentro de código Python, escreva `C:/Users/.../arquivo.json` (o Python
aceita `/` como separador no Windows).
**Origem:** Prompt 3a (pagamentos, PR #16).
