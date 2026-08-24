<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.9  ·  referencias antigas "ARMADILHAS §3.9" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.9 Subir a célula inteira só para rodar teste

**Solução:** só o banco basta — `docker compose -f docker-compose.dev.yml up -d db`.
Ou um container avulso, como no §2. As dependências (catálogo, pagamentos) nunca sobem:
elas existem como contrato mockado.
**Origem:** Prompt 3a (pagamentos, PR #16).
