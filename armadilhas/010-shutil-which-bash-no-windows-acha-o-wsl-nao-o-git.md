<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.10  ·  referencias antigas "ARMADILHAS §3.10" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.10 `shutil.which("bash")` no Windows acha o WSL, não o Git Bash

**Sintoma:** `<3>WSL (…) ERROR: CreateProcessCommon:800: execvpe(/bin/bash) failed:
No such file or directory` ao rodar um `.sh` do repositório a partir de Python.
**Causa:** `C:\Windows\System32\bash.exe` (o lançador do WSL) vem antes do Git Bash no
PATH. Ele existe, é executável, e não roda script do Git Bash.
**Solução:** não basta *encontrar* a ferramenta — é preciso **sondá-la**. Ver `_bash()`
em `ci/ci.py` e `bash_utilizavel()` em `ci/tests/conftest.py`: cada candidato roda
`bash -c "printf sondagem-ok"` antes de ser aceito. Vale como regra geral em portão de
CI: presença no PATH não é prova de que funciona.
**Origem:** PR #22.
