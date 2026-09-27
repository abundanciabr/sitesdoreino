---
schema_version: 2
armadilha: 553
estado: documentada
degrau: 2
confianca: media
custo_por_queda: alto
gatilho:
  - ci/mergear.py
sinal:
  - "isDraft.*false"
guarda:
  tipo: nenhum
  motivo: "a Lei 4 tornou o pouso automatico apos muralhas e ci-celula-gate verdes, sem revisor obrigatorio nem etiqueta; ensinar a pista a esperar uma segunda aprovacao humana antes de integrar um PR de leitura de producao e mudanca de politica do mantenedor, fora do alcance de uma entrada de licao"
licao: "PR verde e em dia integra sozinho pela pista assim que muralhas e ci-celula-gate passam (Lei 4); nao ha pausa embutida para revisao humana em PRs sensiveis. Os PRs 2228, 2226 e 2242 chegaram verdes com defeitos reais e so nao integraram porque foram voltados a rascunho (gh pr ready N --undo) enquanto o revisor lia. Rascunho e o unico jeito de pausar a pista num PR ja verde."
---

# 553: revisar um PR verde de leitura de produção exige voltá-lo a rascunho antes que a pista integre

**Data:** 27/09/2026 · **Onde:** `ci/mergear.py`, PRs #2226, #2228 e #2242,
obra Appmax · **Custo evitado:** um PR com defeito real de produção
integrando sozinho antes de terminar a revisão, só porque os checks
obrigatórios (`muralhas`, `ci-celula-gate`) já estavam verdes.

## Sintoma

Três PRs de leitura de produção (operações da VPS / diagnóstico) chegaram
com `muralhas` e `ci-celula-gate` verdes e, ainda assim, traziam defeitos
reais que só apareceram na revisão manual:

- sem teto de tempo (uma chamada podia travar indefinidamente);
- `except` que disfarçava falha como se fosse dado válido;
- corte silencioso dos registros mais antigos, sem aviso a quem lê;
- mutações de teste que sobreviviam ao guarda (guarda não mordia de
  verdade);
- contrato com semântica errada (campo com nome certo, significado
  diferente do documentado).

Nenhum desses defeitos derruba `muralhas` nem `ci-celula-gate` — os checks
obrigatórios não testam esse tipo de julgamento. Sem intervenção, a pista
(`pouso.yml` → `ci/mergear.py --automatico`) integraria o PR na próxima
varredura.

## Causa

A Lei 4 (`CONSTITUICAO.md`) tornou o pouso automático depois de
`muralhas` e `ci-celula-gate` verdes, deliberadamente sem revisor
obrigatório, atestado, etiqueta de pouso ou gesto de coordenação. Isso
resolveu o gargalo de espera pelo mantenedor, mas também significa que não
existe mais nenhuma pausa embutida na pista para revisão humana antes de
integrar — mesmo em PRs que leem produção. `isDraft` é o único sinal que
`integrar_abertos` (`ci/mergear.py`) usa para pular um PR sem tentar
integrá-lo (`if item["isDraft"] or item["isCrossRepository"]: continue`).

## Solução

Ao revisar um PR verde e sensível (leitura de produção, operações da VPS,
contratos), volte-o a rascunho **antes** de começar a ler, e só o devolva a
pronto depois de decidir:

```bash
gh pr ready <N> --undo   # antes de ler
# ... revisão ...
gh pr ready <N>          # só depois de aprovar
```

Isso é o único mecanismo hoje disponível para impedir que a pista integre
um PR verde enquanto a revisão de julgamento (que os checks automáticos não
cobrem) ainda está em curso.

## Origem

PRs #2226, #2228 e #2242, obra Appmax, sessão de coordenação de 27/09/2026;
`ci/mergear.py::integrar_abertos`; Lei 4 (`CONSTITUICAO.md`).
