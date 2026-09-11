---
schema_version: 2
armadilha: 464
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o rito atual infere a tarefa por texto quando a sessão não leva vínculo explícito; o GPS futuro precisa provar a associação antes de submeter
sinal:
  - entrega documental cita uma TAR futura e o recibo passa a tratá-la como entregue
gatilho:
  - ci/pr.py
  - fila/tarefas/*
  - docs/decisoes/PROMPT-EQUIPE-MAPA-DE-EXECUCAO.md
licao: TAR citada como tarefa futura, dependência ou exemplo não identifica a entrega; passe ao rito a TAR efetivamente executada e confira o estado calculado de todas as citadas antes e depois da submissão.
---

# TAR citada não é a tarefa entregue

**Sintoma.** Um PR que preparava o prompt e registrava uma obra futura citou o
identificador dessa obra no corpo. Sem vínculo explícito com uma tarefa própria
da documentação, o rito associou o PR à TAR futura e escreveu um evento
`submetida`. A fila passou a dizer que a implementação do GPS estava em
execução, embora o PR entregasse somente o guia e a escrituração.

**Causa.** Na ausência de uma identidade explícita, o fechamento procurou uma
TAR no título e no corpo do PR. A ocorrência textual era referência de origem,
não identidade do trabalho entregue. O mecanismo não tem como deduzir essa
diferença sem um vínculo declarado.

**Solução.** Dê à entrega atual sua própria tarefa e passe esse identificador
explicitamente ao rito. Trate TARs citadas no prompt, no corpo, em dependências
e exemplos como referências. Antes e depois da submissão, calcule o estado de
todas elas e recuse qualquer mudança fora da tarefa vinculada. Se uma
associação errada já foi commitada, preserve a história com evento terminal
explicando o erro e registre a missão remanescente numa sucessora.

**Prova observada.** O PR documental #1533 criou automaticamente a submissão
da TAR-321. A correção append-only cancelou essa associação com motivo
explícito, registrou a obra futura na TAR-324 e vinculou a entrega documental à
TAR-323.
