# Guia do mantenedor

Leia antes de pedir decisão ou passo manual. A lei canônica é CLAUDE.md.
O mantenedor é leigo em código e terminal e lê somente português.
Sempre PT-BR e linguagem de resultado, celebrando marcos comprovados.
Execute tudo que estiver ao alcance no projeto, GitHub e ambiente local.
Ele só entra onde é insubstituível: segredos, decisão própria, console do
provedor ou capacidade que o agente realmente não tem. Sem SSH para agentes;
correções da VPS seguem PR e pipeline.

## Decisões

Decida biblioteca, nome, desenho e o que o código responde. A regra 4 não
autoriza decidir por ele em dinheiro, dados, acesso, produto ou ação
irreversível/destrutiva/cara. A maestro reúne decisões em uma pergunta
estruturada (AskUserQuestion), opções em português simples, porquê,
consequência e recomendada marcada. Se fechar sem responder, é "não agora":
pare a parte dependente e não repita. Despacho não pergunta: escreve bloqueada
na fila, registra precisa_do_dono: true, devolve impacto e reversão à maestro.
Não perguntar nunca foi calar: a maestro transforma esse retorno no bloco
Instruções, e bloqueio devolvido sem o que houve e o que destrava não serve.
Molde e reserva de registro em painel/LEIA-ME.md.

## Passo manual

Só peça comando quando faltar capacidade real. Entregue UM bloco de colar,
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
roteiro, texto ou conteúdo, a entrega é criar e publicar no site pelo editor
de documentos. Um arquivo em `docs/` no GitHub é apenas fonte técnica e não
encerra o pedido. O GitHub só recebe código, testes, templates, contratos,
configuração, infraestrutura, workflows, leis mecânicas ou registros que o
projeto exige para funcionar. Se o site não puder ser publicado, informe o
bloqueio e não apresente um PR de documentação como se fosse a entrega.

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
