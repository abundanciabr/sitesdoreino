# Guia do mantenedor

Leia antes de pedir decisão ou passo manual. A lei canônica é CLAUDE.md.
O mantenedor é leigo em código e terminal e lê somente português.
Sempre PT-BR e linguagem de resultado, celebrando marcos comprovados.
Execute tudo que estiver ao alcance no projeto, GitHub e ambiente local.
Ele só entra onde é insubstituível: segredos, decisão própria, console do
provedor ou capacidade que o agente realmente não tem. Sem SSH para agentes;
correções da VPS seguem PR e pipeline. Ausência de chave local não significa
ausência de acesso operacional: o agente dispara a esteira autenticada.

## Decisões

Decida biblioteca, nome, desenho e o que o código responde. A regra 4 não
autoriza decidir por ele em dinheiro, dados, acesso, produto ou ação
irreversível/destrutiva/cara. A sessão que recebeu o pedido reúne as decisões
que faltam em uma pergunta estruturada, com opções em português simples,
consequências e recomendação. Se fechar sem responder, é "não agora":
pare a parte dependente e não repita. O subagente despacho não pergunta:
escreve `bloqueada` na fila, registra `precisa_do_dono: true` e devolve
caminhos, impacto, reversão e ação para destravar à sessão responsável.
Não perguntar nunca foi calar: a sessão responsável explica o bloqueio em
Instruções, com o que houve e o que destrava.
Molde e reserva de registro em painel/LEIA-ME.md.

## Operações da VPS pelo agente

O agente executa `gh workflow run operacoes-vps.yml --ref main -f operacao=estado-servico -f servico=admin`.
Para espaço em disco, usa `operacao=espaco-disco` e `servico=plataforma`.
Os serviços aceitos vêm de `infra/docker-compose.yml` no SHA do disparo,
incluindo auxiliares. O canal é somente leitura: estado, saúde, reinícios,
digest da imagem ou bytes de disco. Não lê logs, ambiente ou dados de compradores.
Não envie segredos nem dados pessoais em inputs do GitHub, mesmo inválidos.

Acompanhe o run identificado pelo workflow, ator, horário e SHA com
`gh run view <id> --json status,conclusion,url,headSha` e consulte seu resumo.
Entregue URL, SHA e medição. PASS prova a coleta, não a saúde do serviço:
`exited` e `unhealthy` são achados. Erro, saída vazia ou run cancelado não são prova.

Correções continuam por PR e deploy; emergência usa `rollback.yml` (RITOS §4).
Provisionamento autorizado usa `provisionar.yml`. Antes de qualquer operação
com efeito, confira o mandato e os parâmetros do workflow correspondente.
Se a investigação exigir algo ainda ausente, acrescente uma operação fechada
por PR em `ci/operacoes_vps.py`, com teste de saída sanitizada, e dispare após
integração. Nunca aceite shell, Python, SQL, caminhos ou URLs livres como input.
Recusa do catálogo exige estender o canal, não repassar um script ao mantenedor.

O job usa `environment: vps`; `DEPLOY_SSH_KEY` fica somente nesse ambiente,
com política explícita de branch `main` (`custom_branch_policies`), sem tags.
Não use apenas `protected_branches`: a prova real permitiu iniciar um ramo
não protegido quando o repositório usava rulesets. A main continua protegida
pelo ruleset. O workflow também recusa outras refs e usa o SHA do disparo.
A impressão digital pública da VPS fica fixada no workflow; divergência
interrompe a conexão. Rotação exige conferir por canal confiável e atualizar
por PR, nunca aceitar automaticamente a chave observada na rede.
Não copie a chave para a sessão. Falha de acesso exige medir a configuração do
GitHub; peça somente o ajuste exclusivo da conta que realmente faltar, com
local e resultado esperado. Nenhum diagnóstico deste canal altera a produção.

## Passo manual

Só peça comando na VPS se a esteira estiver comprovadamente indisponível e
nenhum caminho autorizado resolver. Canal ainda não implementado exige PR,
não trabalho de terminal para o mantenedor. Registre a evidência da exceção. Entregue UM bloco de colar,
fail-closed com "PAROU POR SEGURANÇA". Diga a janela: PS C:\> é PC;
deploy@srv... ou root@srv... é VPS. Avise surpresas antes: senha invisível,
silêncio pode ser sucesso, >> acrescenta e > apaga. Não obrigue o mantenedor
a compor comandos ou respostas livres.

## Entregas para reler

Toda entrega durável mora em meshcraft.top. Se depende de fatos conhecidos
(votos, alunos, tarefas, dinheiro ou estado), faça tela calculada em /admin/
com teste, nunca documento com números copiados. Planos, leis, explicações
e roteiros usam o editor /admin/documentos/. Para IA externa, /mapa-ia/planos/;
artefato privado da conversa não substitui publicação. Prévia e resposta
curta continuam permitidas.

A administração é acessada no site da VPS, em `https://meshcraft.top/admin/`;
documentos ficam em `https://meshcraft.top/admin/documentos/`. Não orientar o
mantenedor a iniciar `ci/ligar_administracao.py` nem a abrir `localhost` para
usar o painel. Se a rota não abrir depois do login, trate como problema de
publicação ou acesso do site e corrija pelo PR e pipeline; não ofereça a cópia
local como substituto.

Regra de destino: quando o mantenedor pedir manual, documento, página, guia,
roteiro, texto ou conteúdo, a entrega é criar e publicar no site. O editor e
a migração própria de documento novo são caminhos válidos. Um arquivo em
`docs/` no GitHub é apenas fonte técnica e não
encerra o pedido. O GitHub só recebe código, testes, templates, contratos,
configuração, infraestrutura, workflows, leis mecânicas ou registros que o
projeto exige para funcionar. Se o site não puder ser publicado, informe o
bloqueio e não apresente um PR de documentação como se fosse a entrega.

Pedido de criar documento é ordem para o robô produzir o texto, gravá-lo no
banco e conferir a URL pública. Escolha um caminho executável: editor
autenticado ou, para documento novo, a receita de `armadilhas/347`, com arquivo
em `documentos/` e migração própria que chama `semear_documento` apenas para
esse nome. Confira a URL depois do deploy; PR, migração e pipeline verdes não
provam que a página está no ar. Se o nome já existe no banco, essa receita
não altera o texto: procure um meio autorizado de editar a linha existente e
registre o bloqueio concreto quando ele faltar. Uma falha da ferramenta web
em página privada não impede a publicação por migração.

Documento enviado pelo mantenedor é ordem de serviço, não conteúdo para
arquivar. Inventarie o que precisa existir, compare código e site, abra
lacunas na fila pelo RITOS §5 citando o documento e comece o despacho na
mesma sessão. A página com o documento é subproduto.

## Fechamento

Checklist final e cinco blocos: O que mudou; O que foi verificado; Pendências;
Veredito PRONTO ou NÃO PRONTO com motivo; Instruções com o que acontece agora.

Instruções fecha toda prestação de contas, e o gancho recusa o fim do turno sem
ele. Em PRONTO, "nada a fazer" é resposta completa. Em NÃO PRONTO é obrigatória
uma lista, em português de leigo, que responde: o que houve para a tarefa não
ter acabado; se a bola é dele ou sua; o que destrava e quanto leva. Vale igual
quando NADA depende dele, e nesse caso diga o que está sendo esperado: ele
precisa entender o que aconteceu com a tarefa que pediu, não receber trabalho.
Terminar no veredito deixa a tarefa parada, e foi a falha que ele mandou
consertar em 20/09/2026.

PRONTO sobre a última medição vermelha é recusado pelo mesmo gancho: se a
suíte ou o portão reprovou, conserte e meça de novo, ou diga NÃO PRONTO e
explique. Prometer o conserto não é consertar. Mudança anuncia CODEOWNERS
nominalmente; prova identifica comando e saída. Só declare integração ou
publicação quando conferidas. Pendências explicam bloqueio, ação e dono;
se não houver, diga isso. Cortes somente se houver, auditoria item a item
somente se relevante. O formato não dispensa qualidade nem evidência.
