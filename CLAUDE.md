REGRA DE FERRO DO MANTENEDOR (vale antes das regras abaixo): o Claude Code só cria, altera, instala, apaga, commita ou publica alguma coisa quando a mensagem do mantenedor trouxer as palavras "PLANO DE EXECUÇÃO", assim, em letras maiúsculas. Elas querem dizer que há um plano de execução pronto e que a ordem de agir foi dada. Sem elas, a mensagem é só varredura de leitura ("nada de PR, plano, recibo ou conserto") ou um pedido de ajuda para entender: leia, explique e responda, e nada mais. Sem elas, as regras 1 e 3 não mandam agir.

## Entrada operacional — informação direta aos robôs

Ao começar trabalho na Meshcraft, o acesso já existe: consulte `ssh sitesdoreino-robo contexto`. Para prévias isoladas, consulte `ssh sitesdoreino-robo previas ajuda` e `ssh sitesdoreino-robo previas listar`; use o canal instalado nas tarefas compatíveis, sem redescobrir a infraestrutura nem abrir o console por hábito. O próprio robô executa e acompanha as ações autorizadas. Depois de desconexão, consulte o mesmo ID, sem repetir efeitos. Se a ferramenta bloquear a rede local, use o mecanismo normal de aprovação; isso não é falha de autenticação na VPS. Não contorne recusa de segurança. As autorizações e restrições do mantenedor continuam valendo.

## Prévias operacionais autorizadas e instaladas em 13/10/2026

O mantenedor autorizou ampliar o SSH restrito para atualizar código não protegido e testar prévias administrativas isoladas, com backup, ID persistente e recuperação do código, sem shell livre, segredos, restauração automática de banco ou interferência nos trabalhos em andamento. Essa capacidade foi instalada: `ssh sitesdoreino-robo previas ajuda`, `ssh sitesdoreino-robo previas listar`, `ssh sitesdoreino-robo previas aplicar NOME COMMIT BASE`, `ssh sitesdoreino-robo previas consultar ID` e `ssh sitesdoreino-robo previas retomar ID`. BASE é o ID atual ou `nova`; o mesmo pedido mantém o mesmo ID de 24 caracteres. Consulta por ID não repete a operação.

Painel exclusivo de admins: `https://meshcraft.top/admin/previas-operacionais/`. Referência operacional completa, formato do manifesto e limites: `https://github.com/abundanciabr/sitesdoreino/blob/codex/operacao-contexto-20261013/infra/previas/README.md`. Relatório privado: `https://meshcraft.top/admin/documentos/operacao-site-contexto-retomada-20261013`. As novas prévias usam cópias próprias sem rede de testes, credenciais ou bancos existentes. Não atualizam a Trilha antiga nem produção. Runtimes disponíveis: Node com node:test e Python com unittest, sem instalação de dependências pelo candidato; páginas HTML interativas ficam em iframe de origem opaca.

Comprovados na VPS: atualização final `df4c5a04968a4f96c07a47d4`; continuidade depois da conexão encerrar; reenvio sem duplicação; recusa de base antiga; recuperação na falha `bc96a2d1c4bcf9866a0d5cb5` e após interrupção do serviço próprio `b0c7582c4dcd0ee63a74f3ef`; 20 testes reais do cliente da Trilha em cópia separada e ensaios de isolamento Node/Python. As operações existentes, chaves, proteções e prévias em uso foram preservadas. O console serviu para instalar o canal; o uso das operações acima não depende dele. Esta é referência da implementação autorizada, não uma nova regra.

1. Só tem trava o que não tem volta: gastar dinheiro real, apagar dado, expor segredo. Nesses três casos, peça a palavra do mantenedor. Todo o resto, faça.
2. Antes de publicar há backup. Se a prova falhar ou o site cair, o código volta sozinho para a última versão aprovada; o banco não é restaurado sozinho.
3. Na dúvida, faça.
4. Quebrou: conserte, volte e siga. Nada vira lição nem regra.
5. Não crie nem proponha regra, portão, processo ou validação. Só o mantenedor cria regra, e para entrar uma terceira coisa uma das duas primeiras sai.
6. Todo trabalho é no site.
7. Entregue funcionando no site.

## Referência de faixas e XP pedida pelo mantenedor em 11/10/2026

Antes de trabalhar com faixas, graus, XP, Sandbox, Fila do Dólar, MESH ou alunos, leia `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\REFERENCIA-FAIXAS-XP-SANDBOX-FILA-DO-DOLAR.md`. A referência compartilhada no repositório é `https://github.com/abundanciabr/sitesdoreino/blob/main/REFERENCIA-FAIXAS-XP-SANDBOX-FILA-DO-DOLAR.md`; em outro checkout, use a cópia desse arquivo na raiz do repositório.

A decisão mais recente de 11/10/2026 é a REGRA DE FERRO DAS FAIXAS: a faixa chega quando a análise da etapa termina, com uma avaliação real da realização do aluno, mesmo que simples e fácil. O bônus de XP da faixa acompanha esse reconhecimento uma única vez; concluir apenas o envio não concede faixa nem esse bônus. Essa decisão substitui a orientação anterior de premiar no envio e vale para todas as faixas e graus dos quatro caminhos. A análise automática do Sandbox determina o resultado; discordâncias seguem pelo suporte; MESH não é mais recompensa vigente. Preserve a progressão sequencial, as conquistas, os XP existentes e o histórico. Isso não restabelece aprovação manual obrigatória da escola nem aprova integralmente as tabelas de percursos ainda em discussão. Leia a referência completa antes de interpretar código, testes ou mensagens antigas como regra do produto.
