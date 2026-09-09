---
schema_version: 2
armadilha: 440
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/sessao.py
  - .githooks/pre-commit
  - .githooks/pre-push
guarda:
  tipo: CI
  dono: ci/tests/test_sessao.py
  detector: 'test_pre_voo_recusa_ferramenta_ausente_antes_de_criar_bancada e testes de hooks'
sinal: 'a sessão cria estado e só depois descobre que falta uma ferramenta ou que o Git não usa os hooks versionados'
licao: 'O código versionado deve conferir no pré-voo as ferramentas da máquina e a instalação dos hooks; ausência reprova antes de worktree, branch, PR ou ambiente.'
---

# 440: a sessão começa sem conferir as peças locais

## Sintoma

Uma abertura podia criar worktree, branch e anúncio antes de descobrir que
faltava `gh`, Docker ou Make. O Git também podia estar sem `core.hooksPath`,
deixando os hooks versionados fora do caminho real de execução.

## Causa

A lista das peças existia no código, mas cada ferramenta era procurada apenas
no passo que a usaria. A configuração local dos hooks nunca era conferida.

## Lição

Faça um pré-voo fail-closed com a lista versionada de ferramentas, a
configuração `core.hooksPath` e os arquivos dos hooks. A recusa precisa ocorrer
antes de qualquer criação de bancada e dizer exatamente como corrigir a peça
ausente.
