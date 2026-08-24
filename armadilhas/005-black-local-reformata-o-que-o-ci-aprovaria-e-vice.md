<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.5  ·  referencias antigas "ARMADILHAS §3.5" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.5 `black` local reformata o que o CI aprovaria (e vice-versa)

**Sintoma:** `black --check` verde local, vermelho no CI (ou o contrário).
**Causa:** a versão instalada globalmente nesta máquina é mais nova que a pinada no
`requirements.txt` da célula (o CI instala a pinada).
**Solução:** rode `black .` antes do commit e prefira construções cuja formatação não
muda entre versões. Se o CI reclamar de formatação que passou local, é isto.
**Origem:** Prompt 4 (checkout).
