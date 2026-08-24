<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.12  ·  referencias antigas "ARMADILHAS §3.12" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.12 CRLF num `.sh` comitado a partir do Windows quebra dentro de container Linux

**Sintoma:** nada quebra localmente (o Git Bash tolera), mas o mesmo script rodando
dentro de um container Linux (ou clonado num runner Linux) falha com erros
estranhos de shebang ou parsing.
**Causa:** `core.autocrlf=true` (comum em máquina Windows) reescreve `.sh` para CRLF
no working tree; sem uma regra explícita, o `\r` pode entrar no blob comitado.
**Solução:** `.gitattributes` com `*.sh text eol=lf` na raiz do repo — força LF no
blob independente do `core.autocrlf` de quem commitou. Confira sempre com
`git show :<arquivo> | grep -c $'\r'` (deve dar 0) antes de considerar um `.sh`
pronto.
**Origem:** `e2e/esqueleto.sh` e `e2e/postgres-init.sh` (despacho e2e/esqueleto).
