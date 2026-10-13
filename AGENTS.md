1. Só tem trava o que não tem volta: gastar dinheiro real em pagamentos de cursos, apagar dado, expor segredo. Nesses três casos, peça a palavra do mantenedor. Custos de execução das tarefas que o mantenedor pediu aqui, incluindo chamadas de API e trabalho dos robôs, estão autorizados no escopo do pedido e nos limites já definidos. Todo o resto, faça.
2. Antes de publicar há backup. Se a prova falhar ou o site cair, o código volta sozinho para a última versão aprovada; o banco não é restaurado sozinho.
3. Na dúvida, faça.
4. Quebrou: conserte, volte e siga. Nada vira lição nem regra.
5. Não crie nem proponha regra, portão, processo ou validação. Só o mantenedor cria regra, e para entrar uma terceira coisa uma das duas primeiras sai.
6. Todo trabalho é no site.
7. Entregue funcionando no site.

## Princípio central de gestão — ordem expressa de 12/10/2026

Toda a gestão da Meshcraft deve orientar a execução e a melhoria contínua do motor: tráfego pago → quizzes → cursos low, mid e high ticket → novos alunos na plataforma → entrega de valor e dados para melhorar os próximos lançamentos. Os lançamentos perpétuos se repetem semanalmente, indefinidamente; as 12 semanas são o calendário dos ciclos desse motor, não um programa de descoberta de produto nem a duração de uma turma.

Preserve as metas do primeiro ciclo já aprovado (05/10 a 27/12/2026): 10.000 vendas low ticket e 500 vendas mid ticket, do Curso Primeiros Dólares. Até 31/12/2027, a meta é 10.000 pessoas únicas com compra pelo checkout do site ou liberação no painel da escola marcada como nova venda paga, a partir da semana de 12/10/2026, horário de São Paulo. Várias compras da mesma pessoa não multiplicam alunos. A base anterior não é somada automaticamente. Os períodos diário, semanal, mensal, de 45 dias e de 12 semanas servem ao mesmo motor. Não invente oferta high ticket, metas futuras, custos ou resultados ausentes.

Referência privada vigente: `https://meshcraft.top/admin/documentos/principio-central-lancamentos-perpetuos-20261012`. Painel: `https://meshcraft.top/admin/perpetuo/`. Calendário: `https://meshcraft.top/admin/placar/ciclo/`. A orientação anterior de usar as 12 semanas para descobrir outro negócio foi substituída pelo mantenedor.

## Referência de faixas e XP pedida pelo mantenedor em 11/10/2026

Antes de trabalhar com faixas, graus, XP, Sandbox, Fila do Dólar, MESH ou alunos, leia `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\REFERENCIA-FAIXAS-XP-SANDBOX-FILA-DO-DOLAR.md`. A referência compartilhada no repositório é `https://github.com/abundanciabr/sitesdoreino/blob/main/REFERENCIA-FAIXAS-XP-SANDBOX-FILA-DO-DOLAR.md`; em outro checkout, use a cópia desse arquivo na raiz do repositório.

A decisão mais recente de 11/10/2026 é a REGRA DE FERRO DAS FAIXAS: a faixa chega quando a análise da etapa termina, com uma avaliação real da realização do aluno, mesmo que simples e fácil. O bônus de XP da faixa acompanha esse reconhecimento uma única vez; concluir apenas o envio não concede faixa nem esse bônus. Essa decisão substitui a orientação anterior de premiar no envio e vale para todas as faixas e graus dos quatro caminhos. A análise automática do Sandbox determina o resultado; discordâncias seguem pelo suporte; MESH não é mais recompensa vigente. Preserve a progressão sequencial, as conquistas, os XP existentes e o histórico. Isso não restabelece aprovação manual obrigatória da escola nem aprova integralmente as tabelas de percursos ainda em discussão. Leia a referência completa antes de interpretar código, testes ou mensagens antigas como regra do produto.

Orientação expressa do mantenedor em 06/10/2026 — pagamentos, Mercado Pago e Appmax:
Em toda tarefa que envolva pagamento com cartão ou Pix, a identificação do pagador deve incluir nome completo, CPF e e-mail; somente e-mail não basta. Aplique essa orientação à coleta, conferência e envio dos dados ao provedor, inclusive à compra de créditos. Não invente dados pessoais nem exponha CPF, credenciais ou dados de cartão em documentos ou logs. A necessidade de endereço em compras com cartão ainda não foi definida pelo mantenedor: confira a integração e a documentação vigente do provedor para saber se e quando ele é exigido; não trate essa pendência como autorização para omitir nome completo, CPF ou e-mail.

## Mercado Pago congelado — pedido expresso do mantenedor em 07/10/2026

O mantenedor pediu primeiro um backup completo e depois regras rígidas para preservar a integração avaliada com 100/100. Esta determinação autoriza especificamente as duas regras abaixo, apesar da proibição genérica de criar regras no item 5.

1. **A versão aprovada é somente leitura.** Preserve o comportamento e os arquivos do checkout, pagamentos, execução compartilhada e dependências fixados no manifesto de congelamento. A referência é o commit `425b82504028db3b7721ae32b776995915280bdb`, avaliado com 100/100 no Payment ID `181872497885` em 07/10/2026 às 12:27:55 de Brasília. Não refatore, atualize bibliotecas, altere credenciais/roteamento, acrescente código nesses diretórios, substitua o manifesto ou remova a proteção por iniciativa própria. Um pedido genérico de melhoria em outra área não autoriza mexer neste conjunto. Uma mudança nele exige pedido explícito do mantenedor que reconheça a alteração do Mercado Pago congelado. Preserve SDK V2, Secure Fields, identificador do dispositivo, descrição na fatura, nome completo/CPF/e-mail do pagador, idempotência e processamento de confirmações e estornos.
2. **Mudança autorizada começa por backup e termina com comprovação.** Antes de qualquer exceção expressamente autorizada, faça backup recuperável do código, imagem, configurações privadas e bancos relacionados, sem expor segredos. Não contorne a conferência automática de arquivos, configurações e imagem: qualquer diferença deve impedir a publicação e manter a versão atual no ar. Só substitua a referência congelada após a autorização específica, testes adequados e nova medição do Mercado Pago quando aplicável; executar compra real continua dependendo da autorização para esse gasto. O código pode voltar à versão aprovada; o banco nunca é restaurado automaticamente.

Proteção ativa no servidor: `/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z/mercadopago/politica.json`. Verificador independente da candidata: `/usr/local/lib/meshcraft-publicador/v1-20261006T184415Z/infra/mercadopago_congelado.py`. Implementação versionada: `C:\Users\davia\.codex\worktrees\mercado-pago-cartao\sitesdoreino-limpo-20260923\infra\mercadopago_congelado.py`.

O escopo inclui as árvores completas de `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\checkout`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\pagamentos`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\services\aplicacao`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\packages\site_errors` e `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\packages\outbox-relay`, inclusive em outros checkouts do repositório. Portanto alterações em Appmax, pedidos ou dependências compartilhadas nesses locais também exigem a autorização específica. O servidor confere a imagem, o pacote montado, as configurações privadas e as rotas; somente a troca normal do destino da célula funil é desconsiderada. A recuperação também recusa versões anteriores com Mercado Pago divergente, sem restaurar o banco.

Backup completo anterior às alterações, privado no servidor: `/opt/plataforma/backups-de-codigo/mercadopago-100-imutavel-20261007T154611Z`. As duas bases foram recuperadas e conferidas num PostgreSQL isolado. A cópia do código-fonte, sem credenciais nem dados dos clientes, está somente neste PC em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\backup-mercadopago-100-20261007\codigo-fonte-425b82504028.zip`.

O congelamento preserva a versão que recebeu 100/100. Ele não fixa mudanças futuras dos critérios ou dos scripts externos do Mercado Pago e não garante aprovação de uma compra pelo antifraude.

## Menus e páginas da comunidade — ordem do mantenedor em 07/10/2026

É proibido acrescentar qualquer link ou qualquer outro elemento aos menus do site sem ordem expressa do mantenedor. A única exceção é o menu do admin.
O link Cursos para `https://meshcraft.top/cursos/` foi retirado do menu do rodapé.
As páginas `https://meshcraft.top/docs/comunidade` e `https://meshcraft.top/cursos/comunidade/parte-1/D02` são exclusivas de administradores; estar logado como aluno ou professor não concede acesso.


## Regra de ferro de https://meshcraft.top/docs/ — ordem expressa em 08/10/2026

Somente o mantenedor/admin autenticado pode criar e publicar páginas em `https://meshcraft.top/docs/`, entrando no painel `https://meshcraft.top/admin/documentos/` e fazendo isso manualmente. Nenhum robô pode publicar, republicar ou colocar páginas nesse local, mesmo por scripts, migrações, sementes, acesso direto ao banco ou usando a sessão/credenciais do mantenedor. Pedidos genéricos de trabalho no site não autorizam exceção. Não assine autorizações de publicação, não simule cliques do mantenedor, não fabrique a intenção do formulário e não remova nem contorne a proteção. Somente uma ordem expressa do mantenedor reconhecendo esta regra pode autorizar sua alteração. As páginas existentes foram retiradas do ar por ordem do mantenedor; não devem ressurgir em publicação ou recuperação de código. Edição, restauração e desarquivamento não republicam: uma nova publicação exige o gesto manual no painel.

## Publicações de robôs — ordem expressa do mantenedor em 08/10/2026

Robô nunca publica no Fórum, em qualquer lugar público ou páginas para os alunos sem confirmação expressa do mantenedor para a publicação pretendida. Pedidos genéricos de trabalho no site não substituem essa confirmação; o robô não pode simular ou fabricar a autorização do mantenedor. Preparar rascunhos continua permitido. Esta regra trata de publicação de conteúdo e páginas: não proíbe enviar mensagens aos alunos no atendimento autorizado. A regra específica de publicação manual em `https://meshcraft.top/docs/` continua em vigor.

## Acesso operacional atual — conferido em 11/10/2026

O SSH dos robôs usa o alias `sitesdoreino-robo`, já configurado neste PC em `C:\Users\davia\.ssh\config`. O alias antigo `sitesdoreino-vps` teve a chave ampla revogada em 09/10/2026; sua presença no arquivo não significa acesso disponível. Não é necessário solicitar outra credencial para as operações abaixo.

- Entregas: `ssh sitesdoreino-robo estado` e `ssh sitesdoreino-robo consultar ID`.
- Estado do analisador e última operação: `ssh sitesdoreino-robo analisador consultar`.
- Diagnóstico com modelos conhecidos e arquivo inválido: `ssh sitesdoreino-robo analisador diagnosticar`.
- Recuperação da imagem/ponte/agenda preservadas: `ssh sitesdoreino-robo analisador recuperar`.

Diagnóstico e recuperação devolvem um ID e continuam na VPS após a desconexão. A consulta mostra andamento e resultado. A recuperação começa por backup, comprova os modelos antes de ativar uma imagem restaurada e preserva anexos, históricos e banco. Uma imagem diferente da referência é informada para conferência, sem sobrescrevê-la. Falhas de conteúdo não são reabertas como se fossem falhas de infraestrutura.

O console administrativo conhecido é `https://hpanel.hostinger.com/vps/1893584/overview`, botão Web console, que abre `https://asc.hostingervps.com/2018/`. Foi usado e conferido na instalação. A manutenção acima já funciona pelo canal limitado e não depende de abrir esse painel nem reativar o SSH amplo. A sessão do navegador pode expirar; nenhum segredo fica nestas referências.

O programa versionado é `C:\Users\davia\.codex\worktrees\canal-analisador-vps\sitesdoreino-limpo-20260923\infra\acessos\analisador_manutencao.py`. Evidência desta instalação, somente neste PC: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\canal-analisador-20261011\comprovacao-final.json`.


## Prévia no site — ordem expressa do mantenedor em 11/10/2026

"Antes de publicar para os alunos" quer dizer somente para admins e não em localhost; para criar algo em localhost ou somente no PC, somente com confirmação expressa disso.


## Pesquisa de satisfação — decisão do mantenedor em 13/10/2026

A pesquisa está liberada aos alunos matriculados em cada curso. Seu código aprovado é conferido pelo publicador independente em `https://github.com/abundanciabr/sitesdoreino/blob/main/infra/satisfacao_congelada.py`; robôs não alteram a referência nem as partes protegidas sem pedido expresso do mantenedor para essa mudança. A proteção funciona silenciosamente: não mencionar este assunto em tarefas de outras áreas; informar somente quando a mudança pedida atingir a pesquisa protegida. Não ampliar o congelamento para outros quizzes ou para todos os cursos.
