---
schema_version: 2
armadilha: 454
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - .github/workflows/muralhas.yml
  - ci/instalar_navegador.py
  - ci/esperar.py
guarda:
  tipo: teste
  dono: ci/tests/test_instalar_navegador.py
sinal:
  - Hash Sum mismatch
licao: Falha transitória ao preparar o navegador se recupera na instalação, com prazo e tentativas limitadas. Erro de integridade prevalece sobre sinais de rede. Teste reprovado exige correção e a operação técnica continua com a maestro.
---

# A instalação do navegador falha e o robô pede ao dono para clicar em reexecutar

No PR #1502, run 34385324742, o apt recusou o índice do repositório Chrome
com `Hash Sum mismatch` antes de começar o teste do painel. A instalação não
tinha recuperação e a sessão transformou uma operação técnica em pedido humano.

A maestro executou `gh run rerun 34385324742 --job 102581010514`. A nova
instalação passou e o run terminou `completed/success` em 09/09/2026. O PR
continuou aberto: reexecutar um job não é merge.

`ci/instalar_navegador.py` limita cada instalação a três tentativas, com pausas
de 15 e 30 segundos. O GNU timeout do runner Ubuntu limita cada comando a
180 segundos e encerra o grupo de processos, com KILL após mais 10 segundos.
O workflow limita o job inteiro a 25 minutos. A versão permanece pinada.

Só sinais conhecidos de falha transitória ou timeout recebem nova tentativa.
Erros de integridade e permissão prevalecem mesmo em log misto. Esgotamento,
instrumento ausente e erro desconhecido continuam impedindo o teste do painel.
O step de teste roda uma vez, sem mascarar uma reprovação com repetição.

A saída da espera atribui diagnóstico e eventual reexecução à maestro. Essa
orientação não é uma garantia universal contra qualquer pedido humano: o
mecanismo cobre a preparação do navegador; contrato, segredo e decisão de
produto continuam fora dessa recuperação.
