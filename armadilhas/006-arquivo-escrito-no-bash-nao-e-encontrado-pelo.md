<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.6  ·  referencias antigas "ARMADILHAS §3.6" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.6 Arquivo escrito no bash não é encontrado pelo Python em seguida

**Sintoma:** `> /tmp/x.json` funciona no bash, e o `open("/tmp/x.json")` do Python
logo depois estoura `FileNotFoundError: '\tmp\x.json'`.
**Causa:** o `/tmp` do Git Bash (MSYS) não é o mesmo `/tmp` que o `python.exe` nativo
do Windows enxerga.
**Solução:** para qualquer arquivo intermediário que um processo vá escrever e outro
ler, use o diretório de scratchpad da sessão, com **caminho absoluto do Windows**.
**A pegadinha fina:** `/tmp/x.json` pode significar **dois lugares na mesma linha de
comando**. Ao chamar um `.exe` nativo, o Git Bash *traduz* o argumento — `/tmp/x.json`
vira `C:\Users\<voce>\AppData\Local\Temp\x.json`. Mas `Path("/tmp/x.json")` **dentro**
do Python vira `C:\tmp\x.json`. Escrever por um caminho e ler pelo outro falha sem erro
óbvio: o arquivo existe, só não onde você olhou.
**Origem:** Prompt 3a (pagamentos) — repetido no Prompt 4 (checkout) e no PR #22.
