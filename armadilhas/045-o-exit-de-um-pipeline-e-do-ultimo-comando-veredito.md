<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.10  ·  referencias antigas "ARMADILHAS §5.10" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.10 O exit de um pipeline é do ÚLTIMO comando — veredito de run nunca vem de `| tail`

**Sintoma:** `gh run watch <id> --exit-status | tail -25` termina com exit 0 e o
agente anuncia o run como verde — mas o run tinha **FALHADO**. Aconteceu de verdade
em 21/08/2026, no 1º run do `deploy-infra`: o exit era do `tail`, não do `watch`.
**Causa:** em `A | B`, o status do pipeline é o de **B**. Qualquer `| head`,
`| tail`, `| grep` pendurado num comando cujo exit importa mascara a falha — é a
versão de shell do §5.6.
**Solução:** o veredito de um run vem de
`gh run view <id> --json status,conclusion` DEPOIS do watch. Se precisar limitar a
saída do watch, capture o exit antes do pipe (`watch ...; ec=$?`) ou descarte a
saída (`>/dev/null`) e confira o JSON. Regra geral: **exit que decide algo nunca
atravessa pipe sem ser capturado**.
**Origem:** sessão deploy-infra (21-22/08/2026) — o agente reproduziu em si mesmo o
falso-verde que este repositório combate; corrigido na mesma sessão, veredito
refeito pelo JSON.
