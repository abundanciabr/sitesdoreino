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

Na tríade (docs/decisoes/DECISAO-triade-de-ias.md), `maestro` é a sessão
que rege o lote (Claude Code por regra); `despacho` é a tarefa autora
(o Codex pela ficha despacho; no trabalho cirúrgico da maestro, a própria tarefa
da fila que ela fechou, para os três IDs serem distintos); `revisor` é o
revisor da casa que leu o SHA final. A verificação da sentinela (Antigravity)
vem depois do merge e não substitui este atestado.

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
lidos dos YAMLs vigentes no SHA avaliado pela API de conteúdo do GitHub.
Antes da separação dos dados admin, a imagem admin comprova também painel
e fila; jobs criados depois não são exigidos retroativamente. Só valem
runs de push na main com SHA exato. Para
cada workflow vale o run mais recente, inclusive reprovação; cancelled e
skipped não aprovam. Resposta truncada é erro de instrumento. Cada run
precisa provar os jobs exigidos: deploy da célula, sincronização de infra,
ou publicar-dados-admin para dados do painel/fila. Dados isolados não
exigem imagem admin; alteração da imagem não é comprovada pelo publicador
de dados. Os portões de detecção e publicação também precisam ter concluído.

Um run posterior só recupera a entrega quando o GitHub confirma que seu SHA
contém o original e o job da mesma publicação concluiu verde. A consulta usa
o limite de histórico já adotado pela vacina `rerun_de_deploy.py`; prova não
encontrada mantém a pendência. A evidência `publicacoes` separa SHA integrado,
SHA publicado, run e job. Um job mais recente reprovado não é encoberto por
um verde anterior. `terminal` é técnico: não comprova aceite funcional, tarefa
concluída nem baixa de alerta. Essas provas pertencem ao reconciliador da entrega.

## Ordem e continuidade

Antes de cada merge, o portão atualiza a referência main e consulta o último
commit first-parent que tocou cada célula e seus provedores transitivos,
conforme `celulas.yml`. Preserva os caminhos de imagem separados dos dados e
consulta o último job de cada célula, paginando o histórico até encontrá-lo
ou chegar ao fim. Dados admin verdes não apagam uma imagem falha. Confere
também a última publicação da infraestrutura;
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

## Recuperação sem esconder falhas

Um PR que corrige a própria falha declara `Corrige-publicacao: RUN_ID` no
corpo; múltiplos runs usam IDs separados por vírgula. O atestado independente
precisa conter `"corrige_publicacao": [RUN_ID]` com a mesma lista. Isso impede
adicionar a declaração ao corpo depois da revisão sem pedir avaliação nova.
O revisor julga se a mudança corrige a causa observada.

A exceção só aceita runs FAILURE vigentes, jobs de célula identificados,
arquivos de código da própria célula falha ou seu Dockerfile/requirements.txt
na raiz do serviço, usados pelo build real, e cobertura de todas as células
que a nova publicação precisa recuperar. Recibo, consumidor, teste isolado,
run inexistente e publicação ainda em curso não abrem essa passagem. Falhas
múltiplas não tratadas continuam bloqueando. Checks e SHA revisado continuam
obrigatórios. Falha de sincronização de infra exige alteração em caminho que
dispara deploy-infra. Jobs sem célula ou publicação identificada não recebem
exceção automática. Falha de instrumento pede diagnóstico, nunca alteração cega.

Rollback saudável comprovado por run e imagem restaura o serviço, mas não
entrega o código que falhou. Registre a restauração e mantenha a publicação
pendente até recuperação comprovada. A última alteração do código não é
uma sonda da imagem que está rodando; esta consulta não declara saúde atual
da VPS nem substitui a prova funcional.
