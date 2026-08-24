<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.4  ·  referencias antigas "ARMADILHAS §3.4" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.4 Docker Desktop frio no meio do trabalho

**Sintoma:** 1–2 minutos parado esperando o Docker subir, bem quando você ia rodar
os testes.
**Solução:** suba o container de banco **no início da sessão**, em background, em
paralelo com a leitura da constituição. Nunca no meio.
**Origem:** Prompt 2 (catalogo, PR #15).
