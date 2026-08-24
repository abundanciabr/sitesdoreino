<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.1  ·  referencias antigas "ARMADILHAS §6.1" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.1 Evidência vermelho→verde sem criar branch descartável

O protocolo (INVARIANTES.md, Lei 3) exige a saída **crua** do guarda vermelho sem o
fix e verde com o fix. O jeito rápido:

```bash
git stash push -- <arquivo-do-handler>   # tira só a proteção
python -m pytest tests/test_inv_pX_*.py -q   # VERMELHO
git stash pop                                 # devolve
python -m pytest tests/test_inv_pX_*.py -q   # VERDE
```

Mais rápido e limpo que criar branch/commit só para isso.
**Origem:** Prompt 2 (catalogo, PR #15).
