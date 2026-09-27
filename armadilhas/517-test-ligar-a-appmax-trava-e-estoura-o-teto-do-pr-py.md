---
schema_version: 2
armadilha: 517
estado: documentada
degrau: 2
confianca: media
custo_por_queda: alto
gatilho:
  - ci/tests/test_ligar_a_appmax.py
  - ci/pr.py
sinal:
  - "TIMEOUT.*ligar-a-appmax"
  - "test_ligar_a_appmax"
guarda:
  tipo: nenhum
  motivo: "a causa da travada (docker/curl de mentira nao interceptados na maquina local) ainda nao foi isolada; ate isolar, o guarda seria um --ignore permanente, que e correcao de codigo, nao licao"
licao: "ci/tests/test_ligar_a_appmax.py trava (nao falha, trava) em pelo menos uma maquina local, e o comando de validacao do ci/pr.py estourou o teto de 900s por causa dele (TAR-757). Ate a causa ser isolada, rode a suite ampla com --ignore=ci/tests/test_ligar_a_appmax.py e rode esse arquivo isolado, com timeout curto proprio, antes de confiar no resultado."
---

# 517: `ci/tests/test_ligar_a_appmax.py` trava e estoura o teto do `ci/pr.py`

**Data:** 26/09/2026 · **Onde:** `ci/tests/test_ligar_a_appmax.py`, TAR-757,
obra Appmax · **Custo evitado:** o comando de validação do `ci/pr.py`
consumindo o teto inteiro (900 s) sem produzir PASS nem FAIL, escondendo o
resultado real da suíte.

## Sintoma

Rodar a suíte ampla (`ci/tests`) numa máquina local com `ci/pr.py` estourou
o prazo padrão de 900 segundos sem terminar (TAR-757). Isolando o arquivo,
`ci/tests/test_ligar_a_appmax.py` trava: não levanta exceção, não imprime
FAIL, o processo simplesmente não retorna, consistente com um subprocesso
que fica esperando algo que nunca chega (rede real, `docker` ou `curl` real
em vez do de mentira que o teste espera encontrar no `PATH`).

## Causa

Não isolada nesta entrada. O teste roda `infra/ligar-a-appmax.sh` de
verdade contra um `docker` e um `curl` de mentira colocados no `PATH`
(ver o cabeçalho do próprio arquivo); numa máquina onde essa substituição
de `PATH` não pega (ordem de `PATH`, shell diferente, hooks de shell que
reintroduzem o binário real), o roteiro deve estar chamando o binário
verdadeiro e esperando uma rede ou um Docker que não existe.

## Solução

Até a causa ser isolada e corrigida:

1. Ao rodar a suíte ampla localmente antes de `ci/pr.py`, exclua o arquivo:
   ```bash
   python -m pytest ci/tests --ignore=ci/tests/test_ligar_a_appmax.py -q
   ```
2. Rode esse arquivo isolado, com um teto curto próprio, para não perder o
   resultado dele:
   ```bash
   python -m pytest ci/tests/test_ligar_a_appmax.py -q --timeout=60
   ```
3. **Correção fora do alcance desta entrada:** isolar por que a
   substituição de `docker`/`curl` no `PATH` não intercepta em toda
   máquina, e corrigir o teste ou o roteiro. Candidata a tarefa própria na
   fila.

## Origem

TAR-757, obra Appmax, sessões de coordenação de 26/09/2026.
