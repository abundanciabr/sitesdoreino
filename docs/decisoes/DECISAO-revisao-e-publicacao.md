# Revisão independente e acompanhamento até publicação

Em 09/09/2026, o mantenedor autorizou exigir revisão independente do SHA
final e acompanhar a entrega até integração e publicação. A pista continua
executando apenas código da main. Nenhuma credencial nova é necessária.

## Atestado da avaliação

Depois de todos os commits, inclusive recibo e eventos, a maestro entrega
o SHA completo a uma tarefa revisor distinta do despacho. O revisor lê o
diff e devolve achados ou aprovação. A maestro confere o relatório real e
publica um comentário novo no PR, com este formato (JSON puro, sem cerca):

    <!-- revisao-independente:v1 -->
    {"sha":"SHA completo de 40 caracteres","despacho":"ID da tarefa autora","revisor":"ID da tarefa revisora","maestro":"ID da maestro","veredito":"APROVADO","resumo":"Conclusão objetiva da avaliação e verificações feitas.","evidencia":"Identificador da tarefa revisora e trecho objetivo conferido pela maestro."}

`REPROVADO` registra achados pendentes. A referência permite à maestro
reencontrar a avaliação sem publicar conversas, prompts ou dados privados.
Não se copia uma aprovação para um SHA novo. Commit novo, inclusive atualização
da base pela pista, exige nova avaliação e novo comentário.

O portão aceita somente comentários com associação OWNER, MEMBER ou
COLLABORATOR informada pelo GitHub. Entre comentários com o marcador, o mais
recente por ID prevalece, inclusive se inválido. Comentários externos não
aprovam nem revogam o atestado. A ausência e o formato inválido recusam.
Os três IDs precisam existir e ser distintos. A API dos comentários é lida
com paginação completa. O merge usa `--match-head-commit` com o SHA conferido.

**Limite da prova:** o comentário é um atestado da maestro. IDs distintos
não provam independência; a associação GitHub autentica o publicador, não
o processo do agente. Não há assinatura criptográfica do runtime. A maestro
responde por conferir uma avaliação real de outra tarefa e por não fabricar
a evidência. O scanner antigo de quatro heurísticas continua consultivo;
LIMPO ou NAO-REVISADO desse scanner nunca substituem o atestado.

## Consulta da entrega

    python ci/esperar.py --entrega NUMERO_DO_PR

A consulta retorna JSON uma vez e não inicia espera. `sha_atual` identifica
o ramo consultado; `sha_integrado`, o commit real do merge. `celulas`,
`workflows` e `runs` mostram a publicação exigida e observada. `terminal`
só fica verdadeiro quando o resultado foi concluído, inclusive encerramento
sem integração, que é explicitamente identificado e não recebe exit zero.

Exit 0 significa PUBLICADO ou SEM_PUBLICACAO. Exit 1 indica estado conhecido
que não comprova entrega: revisão necessária, rascunho, pouso ausente ou
recusado, integração/publicação pendente, falha ou PR encerrado sem integrar.
Exit 2 significa erro de instrumento. `acao` contém o próximo gesto da maestro.
Falha e ausência de publicação mantêm `terminal: false`.

A publicação exige todos os workflows disparados pelos caminhos do diff,
lidos dos YAMLs da main. Só valem runs de push na main com SHA exato. Para
cada workflow vale o run mais recente, inclusive reprovação; cancelled e
skipped não aprovam. Resposta truncada é erro de instrumento.

## Ordem e continuidade

Antes de cada merge, o portão atualiza a referência main e consulta o último
commit first-parent que tocou cada célula e seus provedores transitivos,
conforme `celulas.yml`. Confere também a última publicação da infraestrutura;
entrega de infraestrutura exige as células. Dependência explícita por PR
exige a publicação do SHA daquele PR, além do merge.

Falha, ausência ou publicação em andamento bloqueiam a célula afetada e seus
consumidores. Conjuntos independentes continuam elegíveis. Recibos em painel/
e eventos em fila/ compartilham a publicação admin; essa interseção é real e
não é ignorada. Não se mantém arquivo paralelo de estado nem outro cron.

Depois de integrar, a pista consulta o estado uma vez. O heartbeat nativo da
maestro volta ao mesmo CLI até o resultado, encaminha nova revisão quando o
SHA muda e encaminha falhas ao despacho. A publicação ainda precisa de registro
no livro após o veredito. A consulta e o pedido de pouso não fazem esse registro
nem autorizam novas tarefas da fila. Prazos das esperas existentes continuam
vindo da régua viva de `ci/tempos_esperados.json`.
