# DECISÃO: Baseline de Otimização 10x

## Métricas Medidas (2026-09-11)

- **Tempo de bootstrap:** ~13 segundos (medido com `--sem-container`).
- As outras métricas (tokens por PR, tempo do lote completo, contagem de hooks) não puderam ser medidas de forma exata devido a limitações de ambiente, mas sabemos pelo plano mestre que o consumo atual é insustentável (40-90 min por tarefa, 40M tokens/PR).

O objetivo é reduzir drasticamente essas métricas aplicando o `PLANO-MESTRE-10X-OTIMIZACAO.md`.
