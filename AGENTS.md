1. Só tem trava o que não tem volta: gastar dinheiro real em pagamentos de cursos, apagar dado, expor segredo. Nesses três casos, peça a palavra do mantenedor. Custos de execução das tarefas que o mantenedor pediu aqui, incluindo chamadas de API e trabalho dos robôs, estão autorizados no escopo do pedido e nos limites já definidos. Todo o resto, faça.
2. Antes de publicar há backup. Se a prova falhar ou o site cair, o código volta sozinho para a última versão aprovada; o banco não é restaurado sozinho.
3. Na dúvida, faça.
4. Quebrou: conserte, volte e siga. Nada vira lição nem regra.
5. Não crie nem proponha regra, portão, processo ou validação. Só o mantenedor cria regra, e para entrar uma terceira coisa uma das duas primeiras sai.
6. Todo trabalho é no site.
7. Entregue funcionando no site.

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
