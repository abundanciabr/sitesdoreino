# Plano-mestre: suporte em escala com uma pessoa (11/10/2026)

- **Endereço deste documento:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\PLANO-MESTRE-SUPORTE-EM-ESCALA-20261011.md` (cópia local; documento em versionamento nesta entrega, sem publicação como página).
- **Estado:** plano escrito e **revisado em 11/10/2026 com os 9 pontos da revisão do Codex** (todos conferidos no código). Executado até agora: contexto com compras, agenda e interesse no CRM (`b72bf7ce8`). E1 e os rascunhos e a caixa de decisões da E2 foram expressamente autorizados em 11/10/2026. E3–E7 não fazem parte desta entrega.
- **Roteiro de execução (checklist vivo do robô):** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\ROTEIRO-SUPORTE-EM-ESCALA-20261011.md` (versionado no repositório; não publicado como página). Toda sessão de trabalho começa lendo o roteiro: ele diz o passo atual, a prova de cada passo, a auditoria por etapa e os testes finais. Este plano diz o quê e por quê; o roteiro diz como e em que ordem.
- **Cópia principal local:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\` e foram conferidos na main de 11/10/2026 (`b72bf7ce8` ou posterior). O trabalho do suporte acontece em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\`.

**O que a revisão do Codex mudou neste plano (11/10/2026):**

1. Troca de senha usa a **recuperação por link** que já existe (`C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\comercial\recuperacao_acesso.py`, `solicitar_recuperacao_acesso`), não `resetar_senha`, que gera senha nova. (E5.1)
2. Compra aprovada sem matrícula **recupera a matrícula da compra original**, não cria matrícula nova com `matricular_aluno`. (E5.4)
3. **Gerar Pix novo fica fora do automático.** O Mercado Pago está congelado (`C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\AGENTS.md`, "Mercado Pago congelado", 07/10/2026): checkout e pagamentos são somente leitura. O robô manda o aluno ao checkout que já existe; não cria cobrança. (tipo 6, E3.2, E5.3)
4. A **conta é calculada por tipo**, não por um 85% chutado, e a revisão por sorteio **entra na soma** do tempo da pessoa. (seção 2)
5. **Nova ordem das etapas:** números → rascunhos → prevenção → respostas → ações → canais → base. Medir antes de automatizar; cortar volume antes de responder. (seção 7)
6. **Respondido, encerrado e resolvido são três coisas diferentes**, e cada reabertura fica guardada. (E1.2, E1.3)
7. **Teto de gasto sem IA:** ao bater o teto, o robô continua com texto fixo por tipo e dados preenchidos pelo sistema. O lote da caixa de decisões usa texto fixo, não IA por aluno. (E2.2, E2.6, E4.6, seção 9)
8. **Cores separam consultar, mostrar e cobrar.** Consultar e mostrar o que é do próprio aluno pode ser verde; cobrar ou mexer em dinheiro nunca. (seção 4)
9. **Aviso público no site e tópico no fórum saem só como rascunho** para a pessoa aprovar; o robô não publica nada. (E3.5, E7.3)

---

## 1. Objetivo em uma frase

Uma pessoa dá conta de milhares de pedidos de suporte por dia porque **o robô resolve a maior parte sozinho** e ela **só decide o que o robô não pode decidir**, em lote, com tudo já pronto.

## 2. A conta que manda no plano

| | Valor |
|---|---|
| Pedidos por dia (hipótese) | 1.000 |
| Tempo útil da pessoa | 6 h = 360 min |
| Se ela tocar em todos | 21 segundos por pedido: **impossível** |

**A conta é por tipo, não por um número único. A tabela original soma 96%; os 4% restantes ainda não têm tipo nem tempo estimados e ficam explicitamente fora da parcela conhecida.** Cada tipo da seção 5 tem uma fatia estimada do volume, uma cor e um tempo da pessoa. A soma dá o dia dela. Os percentuais abaixo são hipótese inicial; a etapa E1 (números) mede os reais e esta tabela é refeita com dados.

| Tipo (seção 5) | Fatia do volume | Cor | Tempo da pessoa por pedido |
|---|---|---|---|
| 1 Data de evento | 21% | Verde | 0 (só sorteio) |
| 2 Entrar na conta | 12% | Verde | 0 (só sorteio) |
| 3 Onde está a aula | 10% | Verde | 0 (só sorteio) |
| 4 Não recebi o acesso | 8% | Verde | 0 (só sorteio) |
| 5 Situação do pagamento | 8% | Verde (consultar) | 0 (só sorteio) |
| 6 Pix vencido | 6% | Amarelo (manda ao checkout) | 1 min em lote |
| 7 Cartão recusado | 4% | Verde (explicar) | 0 (só sorteio) |
| 8 Paguei e não liberou | 5% | Amarelo | 2 min |
| 9 Faixa e conquistas | 5% | Verde | 0 (só sorteio) |
| 10 Dúvida técnica | 6% | Amarelo | 3 min |
| 11 Quer outro produto | 3% | Verde | 0 (só sorteio) |
| 12 Problema no site | 4% | Amarelo | 2 min (agrupado) |
| 13 Reembolso | 2% | Vermelho | 6 min |
| 14 Contestação, ameaça | 0,5% | Vermelho | 15 min |
| 15 Dados pessoais | 0,5% | Vermelho | 10 min |
| 16 Cumprimento | 1% | Verde | 0 |

**Soma com 1.000 pedidos por dia, antes da prevenção:**

| Parcela | Conta | Minutos |
|---|---|---|
| Verdes (72%) | 720 pedidos × 0 min | 0 |
| Revisão por sorteio dos verdes (5%) | 36 pedidos × 1 min | 36 |
| Amarelos (21%) | 60 × 1 + 50 × 2 + 60 × 3 + 40 × 2 | 420 |
| Vermelhos (3%) | 20 × 6 + 5 × 15 + 5 × 10 | 245 |
| Ainda sem estimativa (4%) | 40 pedidos × tempo ainda não medido | Pendente |
| **Total conhecido: 96%** | 36 + 420 + 245 | **701 min + os 4% pendentes: não cabe** |

**Com a prevenção (E3 na nova ordem) cortando 30% do volume, 1.000 viram 700:** a parcela conhecida cai a **490,7 min ≈ 8,2 h, mais o tempo dos 4% pendentes**. Ainda não cabe em 6 h.

**Para caber em 6 h (360 min)** precisa de mais uma das duas coisas: a redução adicional do trabalho humano nos tipos 6, 8 e 12, se os números reais e a autorização futura permitirem **ou** o volume real ser menor que a hipótese. A conta mostra que **a prevenção e a passagem de amarelo para verde valem mais que a IA respondendo**; por isso a ordem das etapas mudou (seção 7).

**O que a conta deixa claro:** o sorteio custa tempo e entra na soma; os vermelhos, mesmo sendo 3%, levam um terço do dia; e a pessoa só cabe no dia se os números medidos na E1 confirmarem ou melhorarem a hipótese.

## 3. Onde estamos (o que já existe)

| O que existe | Onde | Para que serve hoje |
|---|---|---|
| Chat do aluno no site e fila de atendimento | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento` (`views.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\models.py`) | Conversa privada entre aluno e equipe |
| Quatro modos por assunto: assistido, automático pela base, automático com encaminhamento, assistente que conversa e resolve | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\models.py` (`MODOS`) | Autonomia por assunto. Hoje o uso é "assistido" (a equipe responde) |
| Robô trabalhando em segundo plano | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py` (`processar_uma`, `rodar_para_sempre`) | Processa as conversas marcadas para processar |
| Contexto para a equipe: CRM, compras, matrículas, faixa, NPS, atendimentos anteriores, agenda e data de hoje | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py` | Entrou em 10/10/2026 (`b72bf7ce8`) |
| Produto do atendimento salvo no CRM | `contexto.salvar_interesse` e `POST /leads/{id}/interesses` em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\leads\apps\core\api.py` | Interesse vira histórico e tag `interesse:<id>` |
| Agenda dos produtos | `https://meshcraft.top/admin/atendimento/agenda/` (`AgendaDoProduto`) | Datas de início e informações de cada produto |
| Base de perguntas e respostas, com revisão | `Conhecimento`, `https://meshcraft.top/admin/atendimento/base/` | Fonte das respostas |
| Prévia para o fórum | `PreviaForum` | Dúvida vira tópico público |
| Aviso à equipe por WhatsApp | `Responsavel`, `Aviso`, `service.avisar` | Avisa quem atende |
| Triagem, alunos, desempenho, visão geral | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\gestao.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\indicadores.py` | Gestão da fila |
| Teto de gasto de IA | `apps/agentes` (`AutorizacaoDeGasto`), `service.orcamento` | Limite de gasto do robô |
| Conversas de WhatsApp e e-mail que chegam | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\mensageria\apps\conversas` (`entrada.py`, `envio.py`, `api.py`) | Hoje são do comercial, separadas do suporte |
| Jornadas e envios programados | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\mensageria\apps\jornadas`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\notificacoes` | Mensagens automáticas |
| Progresso nas aulas | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\cursos` (`Progresso`) | Onde o aluno parou |
| Pagamentos e compras | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\pagamentos` (`Intent`, `PaymentAttempt`), `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\leads` (`CompraDaOportunidade`) | Situação do pagamento |
| Recuperação de acesso por link | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\comercial\recuperacao_acesso.py` (`solicitar_recuperacao_acesso`), já usada pelo robô comercial no WhatsApp | Manda link de recuperação; o robô não escolhe destinatário, e-mail nem texto. É isto que o suporte reaproveita, **não** `IdentidadeClient.resetar_senha`, que gera senha nova |
| Matrículas | `AlunosClient.prontuario`; a matrícula nasce da compra (`CompraDaOportunidade` → aluno) | Ver e **recuperar a matrícula da compra original**. `matricular_aluno` cria matrícula nova e não é o caminho do suporte |
| Checkout e pagamentos congelados | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\AGENTS.md`, "Mercado Pago congelado" (07/10/2026): `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\checkout`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\pagamentos`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\aplicacao`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\site_errors`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\outbox-relay` são somente leitura | O suporte só **lê** e manda o aluno ao checkout que existe; nenhuma cobrança nova é criada pelo robô |
| Oportunidade com próximo passo e prazo | `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\leads` (`Oportunidade`: `passo_descricao`, `passo_executar_ate`) | Sequência comercial |
| Erros vistos no site | `site_errors` (código `ERR-...`) | Erro por página |

**Situação após a implementação de E1 e da caixa assistida (provas abaixo):**

- O modo assistido prepara um rascunho; enviar exige clique da equipe.
- O pedido registra tipo, cor, degrau, humor e prioridade; casos sem classificação suficiente ficam em revisão individual.
- A caixa agrupa perguntas equivalentes por normalização de acentos, pontuação e espaços, tipo, curso, produto e fonte; não presume equivalência semântica entre perguntas distintas.
- O WhatsApp do suporte não cai na fila.
- Não há aviso automático antes da pergunta.
- Não há nenhuma ação automática.
- O chat oferece "Resolveu?" ao encerrar ou na conclusão já reconhecida pelo fluxo de avaliação. Respostas autônomas continuam fora desta entrega.
- Não há relatório das causas dos pedidos.
- Primeira resposta, encerramento e resolução estão separados; a rodada anterior é guardada em cada reabertura.
- O painel acrescenta fatia por tipo, soma de tempo humano por atendimento, resolução, retorno, satisfação, custo atribuído e pedidos por 100 pessoas com matrícula ativa. A janela real de medição ainda está pendente.

## 4. Como o robô e a pessoa dividem o trabalho

- **Verde, no desenho futuro da E4: o robô resolve e registra.** Nesta entrega a cor apenas classifica; a equipe continua enviando cada resposta.
- **Amarelo: o robô prepara tudo** (resposta e ação), e a pessoa aprova com um clique, em lote.
- **Vermelho: a pessoa decide.** O robô entrega o caso montado e um rascunho, e nunca responde sozinho.

Isto já vale hoje e continua valendo: o robô não inventa data, preço, prazo, regra ou link. Ele só usa a base, a agenda, o cadastro e as regras escritas pelo mantenedor.

**A cor depende do que a ação faz com o dinheiro, em três degraus:**

| Degrau | O que é | Cor máxima |
|---|---|---|
| **Consultar** | Ler a situação do próprio aluno: pagamento aprovado ou não, Pix vencido, matrícula existe | Verde |
| **Mostrar** | Apontar um caminho que já existe: "seu Pix venceu, o checkout está aqui", "o cartão foi recusado, tente Pix" | Verde (o link é o do checkout que existe, nunca gerado pelo robô) |
| **Cobrar** | Criar cobrança, Pix ou link de pagamento novo; devolver; mexer em valor | Nunca automático. Com o Mercado Pago congelado, nem a pessoa faz isso pelo suporte: o aluno paga pelo checkout |

Tudo o que mexe com dinheiro (cobrar, devolver, contestar) é vermelho ou está fora do suporte.

## 5. Tipos de pedido e cor inicial (para o mantenedor ajustar, decisão D6)

| # | Tipo | Exemplo | Cor | O que o robô faz | De onde tira |
|---|---|---|---|---|---|
| 1 | Data e horário de evento ou desafio | "Quando começa?" | Verde se a agenda tem a data; senão, amarelo | Responde com a data, quanto falta e as informações | Agenda |
| 2 | Entrar na conta ou esqueci a senha | "Não consigo entrar" | Verde | Pede a recuperação por link que já existe (`recuperacao_acesso.py`); o link vai ao destino cadastrado e o robô não vê senha nem escolhe destinatário | Identidade, pela recuperação por link |
| 3 | Onde está a aula ou continuar de onde parou | "Cadê a aula 3?" | Verde | Manda o link da aula onde ele parou | Cursos |
| 4 | Não recebi o e-mail ou o WhatsApp de acesso | "Não chegou nada" | Verde | Confere o envio e reenvia | Notificações e mensageria |
| 5 | Situação do pagamento | "Meu pagamento passou?" | Verde (consultar) | Diz a situação, só leitura | Leads e pagamentos |
| 6 | Pix vencido ou quero pagar de novo | "O Pix expirou" | Amarelo (mostrar) | Explica que venceu e aponta o checkout que já existe. **Não gera Pix nem link novo:** Mercado Pago congelado | Leitura de pagamentos; checkout existente |
| 7 | Cartão recusado | "Deu erro no cartão" | Verde (mostrar) | Explica o motivo em palavras simples e aponta o checkout para tentar Pix | Leitura de pagamentos |
| 8 | Paguei e o curso não liberou | "Paguei e não abre" | Amarelo; verde depois da E5 | Confere o pagamento e **recupera a matrícula da compra original** (não cria matrícula nova) | Pagamentos, leads e alunos |
| 9 | Faixa, conquista, certificado | "Como subo de faixa?" | Verde | Explica a faixa e o próximo degrau | Gamificação |
| 10 | Dúvida técnica de modelagem ou Roblox | "Como exporto o modelo?" | Amarelo | Responde pela base ou pelo fórum; se não houver resposta, vai à pessoa e vira **rascunho** de tópico, que ela publica | Base e fórum |
| 11 | Quer comprar outro produto | "Tem curso avançado?" | Verde | Informa e registra interesse e oportunidade | Catálogo e CRM |
| 12 | Problema no site (página com erro, vídeo não abre) | "O vídeo não carrega" | Amarelo; vira "problema geral" se forem muitos | Confere o erro registrado, orienta e agrupa. O aviso público no site sai só como rascunho para a pessoa | `site_errors` (só leitura) |
| 13 | Reembolso ou arrependimento | "Quero meu dinheiro de volta" | Vermelho | Monta o caso (data da compra, histórico e regras aplicáveis) e um rascunho | Leads, pagamentos e regras |
| 14 | Contestação no cartão, ameaça de processo, reclamação forte | "Vou no Procon" | Vermelho, prioridade máxima | Monta o caso | Tudo |
| 15 | Pedido sobre dados pessoais (LGPD) | "Apaguem meus dados" | Vermelho | Monta o caso | CRM |
| 16 | Cumprimento sem assunto | "Oi" | Verde | Pergunta como ajudar e mostra atalhos | — |

## 6. Decisões do mantenedor

| # | Pergunta | Bloqueia |
|---|---|---|
| D1 | O robô pode responder sozinho aos pedidos verdes? Hoje a regra é "a equipe envia a resposta". | E4 |
| D2 | Qual o orçamento de IA por mês e o teto por dia? É gasto real. Ao bater o teto o robô segue com texto fixo (seção 9). | E4 em volume |
| D3 | Quais são as regras escritas para o robô seguir? Reembolso e garantia, troca de turma e o que nunca prometer. A equipe confere o caso; o rascunho não presume elegibilidade nem prazo. | E4; qualquer coisa ligada a dinheiro |
| D4 | Qual número de WhatsApp atende o suporte: o mesmo do comercial ou outro? | E6 |
| D5 | Qual o prazo prometido de resposta humana e qual o horário de atendimento? Até ele decidir, o plano usa 24 h. | Ajusta E2.4 e E2.7 |
| D6 | As cores da tabela da seção 5 estão certas, com os três degraus (consultar, mostrar, cobrar) da seção 4? | Ajusta E1.1 e E4 |

## 7. Etapas, na nova ordem

A ordem mudou com a revisão do Codex: **números → rascunhos → prevenção → respostas → ações → canais → base.** Primeiro medir, depois baixar o volume, e só então deixar o robô responder e agir. Nenhuma etapa publica nada em nome do robô; aviso público e tópico de fórum saem como rascunho para a pessoa.

### E1: números (saber a conta de verdade)

**Objetivo:** trocar a hipótese da seção 2 por números medidos antes de automatizar qualquer coisa. **Depende de:** nada; pode começar já.

- **E1.1 Tipo e cor na chegada.** O robô marca o tipo (seção 5), a cor pelo degrau (consultar, mostrar, cobrar), a urgência e o humor do aluno. Onde: campos de classificação em `Conversa`; reaproveitar `prioridade` para urgência; classificação em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py`.
- **E1.2 Três estados separados: respondido, encerrado e resolvido.** Respondido é "alguém escreveu". Encerrado é "a conversa fechou". Resolvido é "o aluno confirmou ou não voltou em 7 dias". Cada reabertura fica guardada com data e motivo (`Reabertura` ligada à `Conversa`). Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\models.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py`.
- **E1.3 Painel de números** (`C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\indicadores.py`): fatia por tipo, tempo da pessoa por tipo, tempo até a primeira resposta e até resolver, quem volta a pedir em 7 dias, reaberturas, satisfação, custo de IA por pedido, pedidos por 100 alunos ativos.
- **E1.4 Tabela da seção 2 refeita com os números medidos** depois de 2 semanas. Essa tabela decide quais tipos vão para a E4 e a E5.

**Como saber que ficou pronto:** cada pedido mostra tipo e cor; a tela de números mostra fatia e tempo por tipo com dados reais; um pedido reaberto aparece como reaberto, não como novo.

### E2: rascunhos e caixa de decisões (a pessoa rende de 3 a 5 vezes mais)

**Objetivo:** a pessoa para de abrir conversa por conversa e passa a aprovar respostas prontas, em grupos. **Depende de:** classificação E1.1 e histórico de reaberturas E1.2. A janela de 14 dias da E1.4 não impede os rascunhos assistidos.

- **E2.1 Resposta pronta em todo pedido.** No modo assistido, o robô passa a escrever o rascunho no espaço da resposta, e a equipe só confere e envia. Ele não envia nada sozinho. Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py` (`preparar`, campo `resposta`).
- **E2.2 Rascunho sem IA quando dá.** Para os tipos de consultar e mostrar (1 a 5, 7, 9, 16) o rascunho é **texto fixo por tipo com os dados preenchidos pelo sistema** (nome, data, situação, link do checkout que existe). A IA só escreve quando o texto fixo não cobre. Isso baixa o custo e é o mesmo caminho usado quando o teto de gasto bate (E4.6).
- **E2.3 Prioridade automática.** Vermelho, aluno muito irritado, comprador dos últimos 7 dias e pedido reaberto sobem para prioridade alta.
- **E2.4 Fila por prazo.** Cada pedido mostra "sem resposta há X" e fica destacado quando passa do prazo (D5). Onde: `gestao.contexto_fila`.
- **E2.5 Agrupamento.** Pedidos abertos com o mesmo tipo, o mesmo produto e a mesma pergunta viram um grupo.
- **E2.6 Tela "Caixa de decisões".** Mostra cada grupo, por exemplo "38 rascunhos sobre a data do desafio: aprovar todos ou revisar". **O lote usa texto fixo:** a pessoa aprova um texto, e o sistema preenche nome e dados de cada aluno sem chamar a IA por aluno.
- **E2.7 Sequência do atendimento:** próximo passo com prazo e responsável, lembrete quando vence (o `Aviso` já existe), lembrete gentil ao aluno que não responde e encerramento por falta de resposta (D5). Encerrar por falta de resposta **não** marca como resolvido.
- **E2.8 Resumo no encerramento e oportunidade comercial.** O robô grava no histórico do CRM o que foi pedido, feito e pendente. Interesse em produto não comprado vira `Oportunidade` para o comercial.
- **E2.9 "Resolveu?" ao encerrar,** ligado à avaliação que já existe (`avaliacao_disponivel`). "Sim" marca resolvido; "não" reabre com prioridade.
- **E2.10 Atalhos de teclado:** aprovar, editar, próximo, pular.

**Como saber que ficou pronto:** com 200 pedidos de ensaio, a pessoa aprova um grupo de 30 com um clique e nenhuma chamada de IA por aluno. Nada sai sem o clique. Um atendimento vencido aparece no topo e gera aviso.

**Meta:** menos de 1 minuto da pessoa por pedido agrupado.

### E3: prevenção (o pedido não nasce)

**Objetivo:** cortar o volume antes de ensinar o robô a responder. **Depende de:** agenda dos produtos (existe) e E1.3 para medir a queda.

- **E3.1 Aviso antes da pergunta.** A partir da agenda, o comprador recebe uma mensagem automática algumas horas antes do início ("seu desafio começa amanhã às 20h"), por WhatsApp ou e-mail, pelas jornadas da mensageria.
- **E3.2 Pix perto de vencer e cartão recusado: aviso que aponta o checkout que existe.** Nenhum Pix ou link novo é gerado (Mercado Pago congelado). Antes, conferir a recuperação que o CRM já faz, para não mandar em dobro.
- **E3.3 "Minha área" do aluno:** meus pedidos, meus produtos com datas, meu acesso, minha faixa, meus atendimentos.
- **E3.4 Busca antes do chat.** O aluno digita a dúvida e vê as respostas da base; só abre atendimento se quiser.
- **E3.5 Problema geral.** Quando chegam muitos pedidos do mesmo tipo em pouco tempo (por exemplo, 10 em 15 minutos), o robô agrupa, prepara uma única resposta e **um rascunho de aviso público para o site**. A pessoa aprova a resposta em lote e publica o aviso com um clique; o robô não publica.
- **E3.6 Botões no próprio chat:** "Quando começa meu desafio?", "Meu pagamento", "Meu acesso".

**Meta:** 30% menos pedidos por aluno ativo em 30 dias, medido na E1.3.

### E4: o robô responde os verdes sozinho, com controle

**Depende de:** D1, D2, D3, E1.4 (números reais) e E2.

- **E4.1 Cor por tipo, não só por assunto.** Cada tipo da seção 5 pode ser ligado ou desligado na Configuração.
- **E4.2 Quando o robô responde sozinho:** só se o tipo for verde pelo degrau (consultar ou mostrar), a fonte foi encontrada (base, agenda ou cadastro) e a confiança for alta. Se faltar qualquer uma, o pedido vira amarelo com rascunho.
- **E4.3 "Resolveu?" logo depois da resposta do robô.** "Não" reabre e vai à pessoa com prioridade; a reabertura fica guardada.
- **E4.4 Sorteio.** 5% das respostas automáticas vão para a pessoa revisar, mais todas as mal avaliadas. **Esse tempo entra na conta da seção 2.**
- **E4.5 Botão de desligar** por tipo e geral (`Configuracao.ia_ativa` já é o geral).
- **E4.6 Teto de gasto por dia, sem parar o suporte.** Ao bater o teto, a IA para, mas o robô **continua respondendo os tipos de texto fixo** com dados preenchidos pelo sistema (E2.2), e o resto vira amarelo com rascunho fixo. Nenhum pedido se perde e nenhuma chamada de IA acontece acima do teto.
- **E4.7 Tela de Regras.** As regras escritas do mantenedor (D3) ficam numa tela que o robô sempre lê.
- **E4.8 Abertura aos poucos.** No primeiro dia o robô responde só os tipos 1 (datas) e 16 (cumprimento). Os outros abrem conforme os números da E1.3.

**Como saber que ficou pronto:** nas conversas de ensaio, os verdes são respondidos em menos de 1 minuto, os vermelhos nunca, o sorteio aparece na caixa de decisões e, com o teto zerado, os tipos de texto fixo continuam sendo respondidos.

**Meta:** 60% ou mais dos pedidos resolvidos (não só respondidos) sem a pessoa.

### E5: ações automáticas (resolver, não só responder)

**Depende de:** E4 e D3. Toda ação aqui usa o que já existe; nada é criado no checkout ou nos pagamentos.

- **E5.1 Recuperação de acesso por link.** Reaproveita `solicitar_recuperacao_acesso` de `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\comercial\recuperacao_acesso.py`: o robô pede a recuperação, o link vai ao destino cadastrado, e o robô não escolhe destinatário, e-mail, senha nem texto. **Não usa `resetar_senha`.** Verde (mostrar).
- **E5.2 Reenviar o acesso ou o e-mail de boas-vindas:** verde.
- **E5.3 Pix vencido:** o robô só aponta o checkout que existe (já feito na E3.2 e no tipo 6). **Não há ação de gerar cobrança**; o Mercado Pago está congelado e isso é "cobrar" (seção 4).
- **E5.4 Compra aprovada sem matrícula: recuperar a matrícula da compra original.** O robô acha a compra (`CompraDaOportunidade`, `Intent`), confere que está aprovada e refaz a matrícula ligada a essa compra, com o mesmo produto e turma. **Não usa `matricular_aluno`** para criar matrícula nova. Amarelo no começo; verde depois de 2 semanas sem erro.
- **E5.5 Reembolso:** o robô só monta o caso e mostra um botão para a pessoa. A devolução usa o que já existe (`PagamentosClient.devolver`), sempre com o clique de uma pessoa e dentro do que o congelamento permite.
- Toda ação fica registrada: quem fez (pessoa ou robô), quando e o resultado. Quando der, pode ser desfeita.
- Toda ação confere o dono pelo acesso do aluno. Pedido que chega por WhatsApp ou e-mail confirma a identidade antes, com um código enviado ao e-mail cadastrado.

**Meta:** 75% ou mais dos pedidos resolvidos sem a pessoa.

### E6: canais (caixa única e celular)

**Depende de:** D4.

- **E6.1 Tudo na mesma fila.** Mensagens de suporte por WhatsApp e e-mail (conversas da mensageria) entram na fila do suporte, com o mesmo robô e as mesmas cores. O comercial continua onde está.
- **E6.2 Mesma pessoa, mesmo histórico,** pelo e-mail e telefone do CRM.
- **E6.3 Aprovar pelo celular:** pela caixa de decisões na tela do celular, ou respondendo no WhatsApp da equipe ("1 = aprovar").
- **E6.4 Regras do WhatsApp:** respeitar a janela de 24 h e usar modelos aprovados fora dela. O descadastro (PARAR) a mensageria já trata.

### E7: base (o atendimento ensina o site)

- **E7.1 A base aprende.** Cada resposta aprovada da pessoa vira sugestão de pergunta e resposta, e um clique aprova.
- **E7.2 Relatório semanal das 10 maiores causas de pedido,** com exemplos, tempo gasto e reaberturas em cada uma. Cada causa vira tarefa de correção no site.
- **E7.3 Fórum só como rascunho.** Dúvidas técnicas repetidas viram **rascunho** de tópico (`PreviaForum` já existe); a pessoa revisa e publica. O robô não publica no fórum.

## 8. Metas por etapa

| Depois de | Meta |
|---|---|
| E1 | Tabela da seção 2 refeita com números reais; respondido, encerrado e resolvido separados |
| E2 | A pessoa rende de 3 a 5 vezes mais; nenhum pedido esquecido |
| E3 | 30% menos pedidos por aluno ativo |
| E4 | 60% ou mais resolvidos sem a pessoa |
| E5 | 75% ou mais resolvidos sem a pessoa |
| E6 | Todos os canais na mesma fila |
| E7 | 85% ou mais resolvidos sem a pessoa; menos de 10% reabrem em 7 dias; satisfação de 4 ou mais (em 5) |

"Resolvido" nas metas é o estado da E1.2, nunca "respondido" nem "encerrado".

## 9. Custo de IA (para a decisão D2)

- **Custo por mês** ≈ pedidos no mês que **precisam de IA** × chamadas por pedido × preço por chamada do modelo rápido. Os tipos de texto fixo (E2.2) não entram: a classificação e o texto fixo usam zero chamadas de IA.
- **Medir antes de abrir volume:** o custo real por pedido é medido na E1.3 e aparece no painel.
- **Teto diário (E4.6): o suporte não para quando a IA para.** Ao bater o teto, o robô segue com texto fixo e dados preenchidos pelo sistema para os tipos de consultar e mostrar; o resto vira amarelo com rascunho fixo. Nenhum pedido se perde e nenhuma chamada passa do teto.
- **Lote sem IA por aluno:** na caixa de decisões a pessoa aprova um texto e o sistema preenche os dados de cada aluno. Um lote de 38 custa 0 chamadas, não 38.
- **Conferir qual autorização de gasto o suporte usa hoje** (`service.orcamento` usa a do suporte ou a ativa dos robôs). O limite de US$ 10/mês dos robôs pessoais não comporta milhares de pedidos.

## 10. Riscos e cuidados

- **Robô errando em escala:** o "resolveu?" (E4.3), o sorteio (E4.4), o botão de desligar por tipo e a abertura aos poucos (E4.8).
- **Mexer no congelado por engano:** nenhuma etapa escreve em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\checkout`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\pagamentos`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\aplicacao`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\site_errors` ou `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\outbox-relay`. O suporte só lê e aponta o checkout que existe. Gerar Pix ou link novo está fora do plano até o mantenedor descongelar.
- **Ordens escondidas nas mensagens dos alunos:** mensagem é dado, nunca ordem; isso já está nas instruções do robô. Nenhuma ação acontece só porque o texto pediu.
- **Privacidade:** o robô não recebe e-mail, telefone, CPF nem nota de satisfação. Já é assim desde 10/10. A recuperação por link mantém isso: o robô não escolhe destinatário nem vê senha.
- **Ação no aluno errado:** a ação confere o dono pelo acesso, e o código de confirmação vale para WhatsApp e e-mail (E5). Matrícula recuperada sempre nasce de uma compra aprovada do próprio aluno.
- **Publicar sem querer:** aviso no site e tópico de fórum nunca saem do robô; são rascunhos para a pessoa.
- **Parte do sistema fora do ar:** nenhum pedido se perde; o robô cai para amarelo.
- **Custo disparado:** teto diário com texto fixo (E4.6).
- **Contar "respondido" como "resolvido":** os três estados são separados desde a E1.2, e a reabertura fica guardada.
- **WhatsApp:** janela de 24 h, modelos aprovados e descadastro.
- **Casos para decisão humana:** reembolso, contestação e pedidos sobre dados pessoais são sempre vermelhos; nenhuma decisão jurídica é presumida pelo rascunho.

## 11. Checklist vivo

O detalhe passo a passo, com prova e auditoria, está no roteiro `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\ROTEIRO-SUPORTE-EM-ESCALA-20261011.md`. Esta lista é o resumo por item do plano.

**Feito**
- [x] Contexto com compras, agenda e interesse no CRM (`b72bf7ce8`, 10/10/2026)
- [x] Plano escrito (11/10/2026)
- [x] Revisão do Codex, 9 pontos conferidos no código e aplicados ao plano (11/10/2026)

**Decisões**
- [ ] D1 robô responde sozinho aos verdes
- [ ] D2 orçamento de IA por mês e teto por dia
- [ ] D3 regras escritas (reembolso, garantia, troca de turma, o que nunca prometer)
- [ ] D4 número de WhatsApp do suporte
- [ ] D5 prazo de resposta humana e horário
- [ ] D6 cores da seção 5 com os três degraus

**E1: números**
- [x] E1.1 tipo, cor por degrau, urgência e humor na chegada
- [x] E1.2 respondido, encerrado e resolvido separados; reabertura guardada
- [x] E1.3 painel de números
- [ ] E1.4 tabela da seção 2 refeita com números reais

**E2: rascunhos e caixa de decisões**
- [x] E2.1 resposta pronta em todo pedido
- [x] E2.2 rascunho de texto fixo com dados do sistema
- [x] E2.3 prioridade automática
- [x] E2.4 fila por prazo
- [x] E2.5 agrupamento
- [x] E2.6 caixa de decisões com lote sem IA por aluno
- [ ] E2.7 próximo passo, lembretes e encerramento por falta de resposta
- [ ] E2.8 resumo no CRM e oportunidade comercial
- [x] E2.9 "resolveu?" ao encerrar
- [x] E2.10 atalhos de teclado (ensaio no navegador local; tela publicada conferida após a entrega)

**E3: prevenção**
- [ ] E3.1 aviso antes do início pela agenda
- [ ] E3.2 aviso de Pix e cartão apontando o checkout que existe, sem duplicar a recuperação do CRM
- [ ] E3.3 "Minha área"
- [ ] E3.4 busca antes do chat
- [ ] E3.5 problema geral com aviso público só como rascunho
- [ ] E3.6 botões no chat

**E4: robô responde os verdes**
- [ ] E4.1 cor por tipo na Configuração
- [ ] E4.2 resposta automática só com fonte e confiança
- [ ] E4.3 "resolveu?" depois da resposta do robô
- [ ] E4.4 sorteio de 5% e revisão das mal avaliadas, somados na conta
- [ ] E4.5 botão de desligar por tipo
- [ ] E4.6 teto de gasto por dia com texto fixo
- [ ] E4.7 tela de Regras
- [ ] E4.8 abertura aos poucos (tipos 1 e 16 primeiro)

**E5: ações automáticas**
- [ ] E5.1 recuperação de acesso por link (`recuperacao_acesso.py`)
- [ ] E5.2 reenviar acesso
- [ ] E5.3 Pix vencido: só apontar o checkout (nenhuma cobrança nova)
- [ ] E5.4 compra aprovada sem matrícula: recuperar a matrícula da compra original
- [ ] E5.5 caso de reembolso montado, com botão humano
- [ ] registro e confirmação de identidade em toda ação

**E6: canais**
- [ ] E6.1 WhatsApp e e-mail de suporte na fila
- [ ] E6.2 mesmo histórico por pessoa
- [ ] E6.3 aprovar pelo celular
- [ ] E6.4 janela de 24 h e modelos

**E7: base**
- [ ] E7.1 base aprende com as respostas aprovadas
- [ ] E7.2 relatório semanal das causas, com reaberturas
- [ ] E7.3 dúvidas técnicas viram rascunho de tópico

## 12. Continuação do plano

E1.1–E1.3 e os rascunhos e a caixa de decisões da E2 estão autorizados e são executados nesta entrega. A tabela de hipóteses só será substituída depois de 14 dias reais de coleta. D1–D6 continuam abertas; nenhuma delas é presumida pelo código. E2.7/E2.8 e E3–E7 permanecem fora desta entrega. Novas respostas autônomas, novos canais e ações financeiras não são ativados.

## Execução autorizada em 11/10/2026 — correções e alcance

- Cópia isolada: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011`. Ramo `codex/entrega/suporte-escala-20261011`, criado pela entrada existente; base `8ec12125d99875945f84eccad4c5771115dd440c`. Alterações locais da pasta principal preservadas.
- Entrega atual: E1.1–E1.3 e E2.1–E2.6/E2.10 (rascunhos, prioridade, prazo e caixa de decisões). E2.9 aproveita a confirmação de resolução. E2.7/E2.8 não são necessários à caixa: permanecem explicitamente pendentes, sem ligar lembretes ao aluno, encerramento por silêncio nem oportunidades automáticas.
- Classificação sem chamada de IA. Sem evidência suficiente, amarelo e revisão individual. Vermelhos não entram em envio em lote. A cor não concede autonomia.
- O lote mostra o texto que será enviado; mensagens novas, troca de responsável, produto, agenda ou base exigem rever o grupo. Não há geração de IA depois do clique.
- Custos de execução estão autorizados; D2 é o orçamento do atendimento em produção. D1–D6 continuam sem decisão nova. Prazo de 24 h é referência interna provisória, nunca promessa ao aluno.
- Resolução por confirmação fica distinta da inferência após sete dias sem retorno; encerramento por falta de resposta não pode contar como resolvido. Registros antigos sem informação suficiente permanecem sem medição.
- E1.4: 14 dias reais a partir da ativação comprovada (data ainda pendente). E3: medição de 30 dias só depois da prevenção. E5: duas semanas sem erro só após a recuperação de matrícula. Ensaios não substituem esses períodos.
- Nenhuma mudança nas cinco árvores congeladas, nenhuma resposta autônoma ativada e nenhuma página de documentação publicada.

## Provas da implementação — 11/10/2026

- Código: `db7036d81`; main atual incorporada em `b0d9a429173ee669210cdfe46e5ca085e429b730`. A publicação pelo integrador ainda precisa ser confirmada no registro abaixo.
- Suporte: **150 testes aprovados**, incluindo 16 tipos, vermelhos sem resposta automática, preservação da rodada, sim/não, retorno em sete dias, prazo, prioridade, texto individualizado, lote idempotente de 30 entre 200 e recusa integral após mudança da fonte/destinatário. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-suporte.txt`.
- Migração nova aplicada, revertida e reaplicada em banco vazio; sem migração de atendimento faltando. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\migracao-comprovada.txt`.
- Testes antigos de documentos na main: 12 falhas e 16 aprovações, sem alterações desta tarefa. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-base-main.txt`. Suíte geral completa: 2.837 aprovados, 101 falhas, 51 erros e 1 pulado: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-admin-completo.txt`. Não é apresentada como verde.
- Diff das cinco árvores congeladas vazio tanto contra a main como contra `425b82504028db3b7721ae32b776995915280bdb`. Nenhuma configuração de autonomia foi alterada. No site, Comunidade, Cursos e Site estavam assistidos antes da entrega; o teto existente de US$ 10/mês permanece, sem presumir a decisão D2 de escala.
- Evidências locais acima existem somente neste PC; os dois documentos são versionados e não viram páginas. Teste principal: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\tests\test_atendimento_escala.py`.

### Comparação final e alcance da prova

A suíte geral não ficou verde. A falha do teste de streaming do suporte foi corrigida e sua suíte passou. Os demais casos foram executados no mesmo recorte na main limpa e nesta candidata: **99 falhas, 33 aprovações e 19 erros em ambas, com as mesmas identidades de casos reprovados**. A comparação distingue falhas do conjunto antigo de regressões da entrega; não remove nem contorna a proteção de documentos. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\comparacao-testes.json`; logs `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\falhas-comparadas-main.txt` e `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\falhas-comparadas-atual.txt`.

Após retirar o lembrete novo de prazo (E2.7 está fora desta entrega), os **47 testes da etapa** passaram novamente: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-escala-final.txt`. Permanecem apenas os avisos já existentes; nenhum lembrete novo ao aluno foi ativado.

Os atalhos Alt+N, Alt+P, Alt+A e Alt+E foram exercitados no navegador com o template real e destinatários fictícios. O servidor estático recebeu o POST de ensaio sem backend de envio e a navegação individual; os testes Django comprovam o processamento real. Prova somente neste PC: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\prova-teclado.json`. Nenhuma mensagem foi enviada a um aluno real durante a conferência.
