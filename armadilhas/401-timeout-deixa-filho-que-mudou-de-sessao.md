---
schema_version: 2
armadilha: 401
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_pr.py
  detector: test_timeout_encerra_filhos_e_netos_reais
sinal: 'TIMEOUT encerra o pai mas deixa filho setsid vivo'
gatilho:
  - ci/pr.py
  - ci/pr_processos_linux.py
  - ci/pr_processos_windows.py
licao: 'killpg não alcança filhos que mudam de sessão. No Linux, adote órfãos antes de iniciar a validação e encerre/recolha as gerações; no Windows, associe o processo suspenso a um Job Object antes de executá-lo. Preserve processos alheios e prove também pai encerrado cedo.'
---

# 401: Timeout deixa vivo um filho que mudou de sessão

**Data:** 08/09/2026. **Onde:** auditoria independente do fechamento, PR #1383.

## Sintoma e causa

O runner levantava TIMEOUT, mas um filho Linux criado com
`start_new_session=True` continuava vivo. `killpg` alcança somente o grupo
original; saída antecipada do pai também pode apagar a relação de parentesco.

## Correção comprovada

O Linux ativa `PR_SET_CHILD_SUBREAPER` antes do comando, adota os órfãos,
encerra e recolhe cada geração e restaura o estado anterior. Recusa filhos
preexistentes e validações concorrentes para preservar processos alheios.
No Windows, o comando nasce suspenso, entra no Job Object e só então executa.
O encerramento do job inclui os descendentes mesmo quando o pai já terminou.

O teste precisa criar filhos e netos reais, mudar sessões, encerrar o pai
cedo e conferir ausência dos processos. No Docker, use `--init`: pytest como
PID 1 adotaria órfãos implicitamente e poderia esconder a ausência do subreaper.
Outros sistemas não receberam garantia: o runner os recusa explicitamente.

## Evidência

Em `041ddea2`, a reprodução independente e a regressão Linux reprovaram.
Em `0d69aaf5`, o revisor confirmou TIMEOUT com o filho morto e recolhido,
34 testes Linux aprovados e 90 Windows aprovados, com cinco casos exclusivos
Linux não aplicáveis no Windows. Sabotar adoção, encerramento, restauração,
preservação, concorrência ou leitura de `/proc` fez as guardas reprovarem.

A catraca classificou os decorators condicionais novos em um arquivo antigo
como desligamentos. Os cinco testes novos específicos de sistema foram
separados em módulos próprios em `9b67cc8a`, preservando assinaturas,
decorators e corpos byte a byte. Contagens e seleção foram repetidas em ambos
os ambientes; nenhuma guarda antiga, condição ou catraca foi alterada.
