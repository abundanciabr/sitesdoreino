# Entrega sem espera ativa

O mantenedor aprovou os Diamantes e pediu encaminhamento imediato em
12/09/2026. O gargalo era o agente continuar ativo para esperar trabalho que
a pista já executa por eventos.

`python ci/mergear.py <N> --pousar` confere o PR, a revisão independente e o
recibo; admite checks ainda ausentes ou em andamento, cálculo de
mergeabilidade e base atrasada. Em seguida confirma a etiqueta `pousar` e o
SHA no GitHub e retorna JSON `ENFILEIRADO`, com `integrado: false`.
Falhas reais, conflitos e erros de consulta continuam recusados. Resposta
incoerente após etiquetar retorna ERROR e pede conferência antes de repetir.

O agente encerra. A pista existente recebe `pull_request_target` com etiqueta
e `workflow_run` dos checks. A varredura agendada recupera eventos perdidos.
Só a pista integra, usando o mesmo portão que continua exigindo checks verdes.
Ela publica o desfecho no PR. Não se cria outro monitor nem um processo de
espera no computador do mantenedor. `esperar.py` continua disponível para
diagnóstico explícito; deixa de ser o caminho normal do fechamento.

A bancada acumula alterações até uma mudança completa e revisável. Um
commit técnico de fechamento substitui a obrigação de commit a cada verde;
`make pr` continua acrescentando recibo e eventos. O agente seleciona o diff
e preserva alterações alheias e commits publicados. O histórico do painel
permanece íntegro; a máquina executa a escrituração já automatizada.

## Merge Queue

Em 12/09/2026 a API do GitHub informou `owner.type: User` e permissão
administrativa para `abundanciabr/sitesdoreino`. A
[documentação oficial](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-a-pull-request-with-a-merge-queue)
limita Merge Queue a repositórios públicos de organizações e organizações
elegíveis no plano Enterprise. Não é falta de acesso administrativo e não
há botão aplicável para ativá-la nesta conta pessoal. A etapa opcional não
justifica transferir o repositório ou alterar suas proteções sem decisão do
mantenedor. A pista atual continua recebendo os PRs por eventos.

## Prova

`ci/tests/test_pouso_assincrono.py` mede admissão de pendências sem aprovação
para merge, recusa de falhas reais, rascunhos, conflitos, falhas de consulta,
etiqueta ausente e mudança do SHA remoto. Guardas marcados são provados por
`ci/provar_guardas.py` em cópia isolada. A suíte existente mede o portão do
merge e executa o laço real da pista com respostas controladas do GitHub.

O alvo de metade dos tokens e lote em uma hora exige medição de lotes reais
após integração. Testes locais do encaminhamento não comprovam esse ganho.
