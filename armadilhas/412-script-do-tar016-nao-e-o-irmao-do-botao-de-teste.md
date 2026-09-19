---
schema_version: 2
armadilha: 412
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o teste existente nomeia o script certo, mas há dois scripts de aviso com nomes parecidos; uma alteração no irmão pode passar na leitura e deixar o fluxo do TAR-016 intacto.
sinal:
  - provisionar-aviso-no-celular.sh
  - provisionar-par-do-teste-de-aviso.sh
  - tarefa TAR-016
  - teste de Docker falso
gatilho:
  - infra/*aviso*.sh
  - ci/tests/test_provisionar_aviso_no_celular.py
licao: antes de corrigir um script de aviso, siga a constante SCRIPT do teste e o caminho citado no registro da fila. O fluxo do TAR-016 usa provisionar-aviso-no-celular.sh; o irmão provisionar-par-do-teste-de-aviso.sh pertence ao botão de teste da administração.
---

# 412: o script do TAR-016 não é o irmão do botão de teste

Dois scripts de infraestrutura têm nomes parecidos e tratam credenciais de avisos diferentes. O teste `ci/tests/test_provisionar_aviso_no_celular.py` aponta para `infra/provisionar-aviso-no-celular.sh`, que grava o par VAPID do site. O botão da administração usa `infra/provisionar-par-do-teste-de-aviso.sh`, que grava o par entre administração e notificações.

Antes de alterar qualquer um, conferir o caminho da constante `SCRIPT` do teste e a tarefa na fila. Um teste novo apontando para o irmão pode produzir uma correção verde no arquivo errado e deixar o caminho real sem a guarda necessária.
