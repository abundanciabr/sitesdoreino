---
schema_version: 2
armadilha: 313
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o pedido chega em prosa na conversa, e nenhum portão lê prosa; o que existe é o critério de morte escrito na própria lei ("pare e reabra a decisão com o mantenedor") e o hábito de rodar ci/reconhecer.py antes de planejar, que é o que faz a lei aparecer
sinal:
  - "crie um plano de"
  - "pare e reabra a decisão com o mantenedor"
  - "critério de morte"
  - "o que fica FORA"
  - "dito explicitamente para nenhum agente melhorar por conta própria"
---

# O mantenedor pede, com as próprias palavras, exatamente o que a lei que ele aprovou anteontem proíbe

**Sintoma.** O mantenedor abre uma sessão pedindo um plano para uma
funcionalidade nova, descrita em linguagem de produto e sem citar nenhum
documento. O pedido é claro, é dele, e é razoável. Só que a funcionalidade já
tem lei escrita, aprovada **por ele**, dias ou horas antes, em outra sessão. E
a lei não só cobre o assunto: ela lista, na seção "o que fica fora", os itens
que ele acabou de pedir, com a instrução literal *"quem se pegar desenhando
qualquer item desta lista para e reabre a decisão com o mantenedor"*.

Caso real de 04/09/2026: ele pediu *"uma área de negociação tipo contratação de
freelancer... onde pessoas possam criar projetos e os alunos possam pegar os
projetos"*. A `DECISAO-fila-do-primeiro-dolar.md` tinha sido aprovada por ele
em 03/09/2026, a célula `encomendas` já tinha nascido, dezenove eventos já
estavam congelados em contrato, e o §2 daquela lei dizia: *"Não há freelancer a
escolher, não há proposta, não há lance: é exatamente o que os marketplaces de
fora vendem, e é exatamente o que este produto existe para não ter."*

**Os dois desfechos errados, e os dois são fáceis de cair.**

1. **Construir o que ele pediu.** O plano sai completo, coerente e em conflito
   frontal com uma lei de um dia. Duas fontes de verdade passam a existir para
   o mesmo produto, que é a doença que o `CLAUDE.md` chama de duplicação. A
   próxima sessão lê a lei antiga e desfaz o trabalho, ou lê a nova e viola o
   critério de morte.
2. **Responder "isso já existe, não precisa".** Pior que o primeiro. O pedido
   dele **não** era redundante: das três coisas que descreveu, uma já estava
   pronta e duas eram genuinamente novas. Tratar o pedido inteiro como
   repetição joga fora a parte nova e soa como recusa. Este projeto já quase
   perdeu o mantenedor uma vez por um agente recomendando corte de escopo
   (`feedback_jogaria_fora_sem_do_03_09` na memória, 03/09/2026).

**Causa.** O mantenedor não carrega o corpus na cabeça, e não deveria: ele é
leigo, tem dezenas de sessões paralelas rodando, e a lei em questão foi
aprovada numa conversa que não é esta. **A lei é nova demais para ele lembrar e
velha demais para o agente supor que não existe.** Some-se a isso que o clone
principal pode estar dezenas de commits atrás: a célula inteira era invisível
no commit base do worktree, e só apareceu porque o `ci/reconhecer.py` lê do
`origin/main`, não do disco.

**Solução, em três passos, e a ordem importa.**

1. **Reconheça antes de planejar.** `python ci/reconhecer.py <palavras do
   pedido>` é o primeiro comando, não o quinto. No caso real, ele devolveu um
   caminho de uma célula que não existia no worktree (`services/encomendas/…`),
   e essa única linha fora do lugar foi o que salvou a sessão. **Caminho
   desconhecido na saída do reconhecimento é sinal de parar e investigar, nunca
   ruído.**
2. **Pare e reabra com ele, na mesma resposta.** Não construa, não recuse.
   Meça a diferença exata entre o que ele pediu e o que a lei permite, e leve
   **só a diferença** para uma caixa de pergunta estruturada, com a
   consequência prática de cada lado escrita em português leigo. Ele é a única
   pessoa que pode reabrir; o critério de morte existe para levá-lo até essa
   caixa, não para bloquear o pedido.
3. **A resposta dele vira emenda na lei existente, mais um plano só do que é
   novo.** Nunca um plano paralelo que cubra o mesmo produto de novo. A lei
   ganha uma seção registrando a reabertura e o que saiu da lista do "fora"; o
   desenho novo mora num documento próprio; e o critério de morte é reescrito
   para continuar valendo sobre o que **não** foi liberado. No caso real,
   "propostas" saiu da lista proibida e "lances" ficou, e essa distinção é o
   produto inteiro.

**O detalhe que mais economiza retrabalho:** confira se algum degrau da escada
já foi construído antes de emendar. Em 04/09/2026 a tarefa das tabelas ainda
estava no balcão sem dono, então a emenda entrou antes da primeira migração e
nada precisou ser desfeito. Se estivesse pronta, a emenda custaria uma migração
de dados, e isso muda o que se recomenda a ele.

**O que NÃO conta como este caso.** Ele mudar de ideia sobre uma decisão dele é
direito dele e acontece com frequência (o reembolso foi decidido duas vezes em
sentidos opostos). A armadilha não é "ele contradisse a si mesmo": é o agente
não perceber a contradição e escolher sozinho um dos lados.

**Parentes.** `armadilhas/299` (documento de fora reintroduz decisão revogada)
é a mesma família com o vetor invertido: lá a premissa velha chega por um
documento externo, aqui pelo próprio mantenedor. `armadilhas/148` (ler do
`origin/main`, nunca do clone principal) é a pré-condição: sem ela a lei nem
aparece. Padrão 7 da `RETROSPECTIVA-FASE-D.md` (sessões paralelas): se a lei
descreve um estado que o repositório não tem, é trabalho em voo, e se pergunta
em vez de improvisar.
