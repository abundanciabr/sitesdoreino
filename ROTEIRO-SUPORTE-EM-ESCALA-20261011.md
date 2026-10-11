# Roteiro de execução do suporte em escala (checklist vivo do robô)

- **Endereço deste documento:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\ROTEIRO-SUPORTE-EM-ESCALA-20261011.md` (cópia local; documento em versionamento nesta entrega, sem publicação como página).
- **Plano que ele executa:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\PLANO-MESTRE-SUPORTE-EM-ESCALA-20261011.md`. O plano diz **o quê e por quê**; este roteiro diz **em que ordem, com que prova e onde marcar**.
- **Código:** `C:\Users\davia\abundanciabr\wt-suporte-20261010\services\admin\apps\atendimento\` (ramo de trabalho). Publicar é pelo integrador: `infra/robo.py entregar` com ramo `claude/entrega/...`; a main é protegida.
- **Criado em 11/10/2026.** Última atualização: 11/10/2026 (execução autorizada; base atual 8ec12125d99875945f84eccad4c5771115dd440c; documentos corrigidos antes do código).

---

## 0. Como o robô usa este roteiro (ler antes de qualquer passo)

1. **Ao começar qualquer sessão**, leia a seção 1 (estado) e ache o **primeiro passo não marcado**. É por ali que o trabalho continua. Não comece por outro lugar.
2. **Um passo por vez.** Cada passo tem: o que fazer, onde, qual a prova e o que marcar. Só marque `[x]` depois da prova passar; implementação, ativação e medição real têm registros separados. Prova é teste rodando verde ou tela conferida no site, nunca "parece certo".
3. **Ao terminar um passo**, atualize no mesmo momento: a caixa do passo, a seção 1 (estado) e a linha "Última atualização" acima. Grave o hash do commit na coluna "Prova". Se a sessão cair, a próxima sessão acha tudo aqui.
4. **Travou?** Escreva na seção 8 (pendências) o que travou, por quê e o que falta, e **passe ao próximo passo que não depende dele**. Nunca fique parado num passo nem pule para o fim.
5. **Mudou o plano?** O plano-mestre é a fonte. Se um passo aqui contradiz o plano, corrija este roteiro, não o plano, e anote na seção 8.
6. **Nunca faça fora do roteiro:** gerar Pix ou link de pagamento, usar `resetar_senha`, usar `matricular_aluno`, publicar aviso no site ou tópico no fórum em nome do robô, escrever em `services/checkout`, `services/pagamentos`, `services/aplicacao`, `packages/site_errors`, `packages/outbox-relay` (Mercado Pago congelado, `AGENTS.md`).
7. **Decisões do mantenedor (D1 a D6)** só ele responde. Até responder, faça só os passos marcados "não depende de decisão". Não invente a resposta.
8. **E2 começa após E1.1 e o histórico necessário de E1.2.** A medição E1.4 de 14 dias não bloqueia rascunhos assistidos; bloqueia a ampliação da autonomia da E4. O plano todo termina com a seção 7 (testes finais). O trabalho só está acabado quando a seção 7 está toda marcada.
9. **Teste por etapa:** rode só os testes do que mudou (`services/admin/tests/test_atendimento*.py` e o que o passo citar), com o Postgres da sessão por `DATABASE_URL` (ver memória "Testes paralelos da mesma célula"). Antes de publicar, rode a suíte do admin inteira uma vez.
10. **Economia:** sem ajudantes ou workflows adicionais; usar o navegador para a conferência no site prevista nesta entrega. Respostas curtas ao mantenedor, em português simples.

---

## 1. Estado agora (atualizar sempre)

| Campo | Valor |
|---|---|
| Etapa atual | E1 em implementação; E2 após classificação e reaberturas |
| Passo atual | — |
| Último commit publicado do suporte | `b72bf7ce8` (contexto com compras, agenda e interesse no CRM, 10/10/2026) |
| Decisões respondidas | nenhuma (D1 a D6 abertas) |
| Pendências abertas (seção 8) | 0 |
| Auditorias feitas (seção 6) | nenhuma |

---

## 2. Antes de começar (uma vez)

- [ ] **P0.1** Conferir que o ramo de trabalho está em dia com a main: em `C:\Users\davia\abundanciabr\wt-suporte-20261010\`, `git fetch` e `git log --oneline -1 origin/main`. Prova: hash igual ou posterior a `b72bf7ce8` anotado aqui: ______
- [ ] **P0.2** Subir o Postgres da sessão numa porta fora da faixa reservada e exportar `DATABASE_URL` (memória "Porta 55400 reservada"). Prova: `pytest services/admin/tests/test_atendimento*.py -q` verde antes de mexer. Resultado: ______
- [ ] **P0.3** Ler `services/admin/apps/atendimento/models.py`, `service.py`, `contexto.py`, `gestao.py`, `indicadores.py` uma vez e anotar aqui as três coisas que surpreenderam: ______
- [ ] **P0.4** Confirmar que não há migração pendente em `atendimento/migrations/` fora da main. Prova: `python manage.py makemigrations --check --dry-run atendimento` sem saída.

---

## 3. Passos por etapa

Cada linha: **passo**, o que fazer, onde, **prova**. A ordem dentro da etapa é a ordem de execução. "ND" = não depende de decisão do mantenedor.

### E1: números (ND)

- [ ] **E1.1a** Campos novos em `Conversa`: `tipo` (16 tipos da seção 5 do plano), `cor` (verde, amarelo, vermelho), `degrau` (consultar, mostrar, cobrar), `humor`; reaproveitar `prioridade` para urgência. Migração. Onde: `models.py`. Prova: migração aplica e reverte; teste de modelo.
- [ ] **E1.1b** Classificação na chegada em `contexto.py`: função que recebe a conversa e devolve tipo, cor, degrau, urgência e humor. Vermelho é fixo para tipos 13, 14 e 15; "cobrar" nunca sai verde. Prova: teste com uma mensagem de cada um dos 16 tipos; os três vermelhos saem vermelhos sempre.
- [ ] **E1.1c** Tipo e cor aparecem na fila (`gestao.contexto_fila` e template). Prova: teste de view mostra o rótulo.
- [ ] **E1.2a** Três estados separados: `primeira_resposta_em` e `encerrada_em` existentes, mais `resolvida_em` em `Conversa`, e modelo `Reabertura` (conversa, quando, motivo, quem). Migração. Prova: teste cria conversa, responde, encerra, reabre; os três campos e a reabertura ficam gravados e distintos.
- [ ] **E1.2b** `service.py`: responder mantém `primeira_resposta_em` existente; encerrar mantém `encerrada_em` existente; resolvido só por "sim" do aluno ou 7 dias sem volta; qualquer mensagem nova depois de encerrado cria `Reabertura` e limpa `resolvido_em`. Prova: teste cobre os quatro caminhos.
- [ ] **E1.3a** `indicadores.py`: fatia por tipo, tempo da pessoa por tipo (do primeiro clique da equipe ao envio), tempo até a primeira resposta e até resolvido, reaberturas em 7 dias, satisfação, custo de IA por pedido, pedidos por 100 alunos ativos. Prova: teste com dados fixos confere cada número.
- [ ] **E1.3b** Tela de números em `/admin/atendimento/` (aba ou página). Prova: teste de view; conferir no site depois de publicar.
- [ ] **E1.4** Depois de 2 semanas no ar: refazer a tabela da seção 2 do plano com os números medidos. Prova: tabela nova no plano com a data da medição. Data prevista: ______
- [ ] **Auditoria da E1** (seção 6) feita em: ______

### E2: rascunhos e caixa de decisões (ND, depende de E1.1)

- [ ] **E2.1** `contexto.preparar` passa a preencher `resposta` com o rascunho no modo assistido. Nada é enviado sem clique. Prova: teste mostra `resposta` cheia e nenhuma mensagem enviada ao aluno.
- [ ] **E2.2** Textos fixos por tipo (1 a 5, 7, 9, 16) com campos preenchidos pelo sistema (nome, data da agenda, situação do pagamento, link do checkout que existe). Onde: módulo novo `atendimento/textos_fixos.py`. IA só quando o texto fixo não cobre. Prova: teste de cada tipo gera o texto sem chamar IA (contador de chamadas em zero).
- [ ] **E2.3** Prioridade automática: vermelho, humor irritado, comprador dos últimos 7 dias, reaberto. Prova: teste ordena a fila.
- [ ] **E2.4** Fila por prazo: "sem resposta há X" e destaque ao passar de 24 h (ou D5). Prova: teste de view com conversa antiga destacada.
- [ ] **E2.5** Agrupamento por tipo, produto e pergunta parecida. Onde: `gestao.py`. Prova: teste junta 5 pedidos iguais num grupo e separa um diferente.
- [ ] **E2.6** Tela "Caixa de decisões": lista grupos, aprova um texto e o sistema preenche dados de cada aluno sem IA. Rota em `config/urls.py`, template novo. Prova: teste aprova grupo de 30 com um POST, 30 respostas saem, zero chamadas de IA.
- [ ] **E2.7** Próximo passo com prazo e responsável; lembrete por `Aviso` quando vence; lembrete ao aluno; encerramento por falta de resposta **sem** marcar resolvido. Prova: teste com relógio avançado.
- [ ] **E2.8** Resumo no CRM ao encerrar e `Oportunidade` quando há interesse em produto não comprado. Prova: teste confere o histórico do lead e a oportunidade criada.
- [ ] **E2.9** "Resolveu?" ao encerrar, ligado a `avaliacao_disponivel`. "Sim" marca resolvido; "não" cria `Reabertura` com prioridade. Prova: teste dos dois caminhos.
- [ ] **E2.10** Atalhos de teclado na caixa de decisões. Prova: conferir no site.
- [ ] **Ensaio da E2:** 200 pedidos de ensaio, um grupo de 30 aprovado com um clique, zero IA por aluno, nada enviado sem clique. Prova: teste de integração `test_atendimento_caixa.py`.
- [ ] **Auditoria da E2** (seção 6) feita em: ______

### E3: prevenção (ND, depende da agenda e de E1.3)

- [ ] **E3.1** Jornada "começa amanhã" a partir de `AgendaDoProduto`, pela mensageria. Onde: `services/mensageria/apps/jornadas/`. Prova: teste cria compra com data amanhã e a mensagem entra na fila de envio uma vez só.
- [ ] **E3.2** Aviso de Pix perto de vencer e cartão recusado **apontando o checkout que existe**. Antes, mapear a recuperação que o CRM já faz e não duplicar. Prova: teste mostra uma mensagem só, com link do checkout existente e nenhuma cobrança criada.
- [ ] **E3.3** "Minha área" do aluno: pedidos, produtos com datas, acesso, faixa, atendimentos. Onde: célula do aluno (conferir qual serviço serve a área logada). Prova: teste de view; conferir no site.
- [ ] **E3.4** Busca na base antes de abrir o chat. Prova: teste devolve respostas da base; abrir atendimento continua possível.
- [ ] **E3.5** Problema geral: 10 pedidos do mesmo tipo em 15 min agrupam, geram uma resposta e **um rascunho de aviso público**. A pessoa publica. Prova: teste cria 10 pedidos, surge um grupo e um rascunho; nada publicado.
- [ ] **E3.6** Botões no chat. Prova: conferir no site.
- [ ] **Medição da E3:** 30 dias depois, pedidos por 100 alunos ativos caíram 30%? Número antes: ______ depois: ______
- [ ] **Auditoria da E3** (seção 6) feita em: ______

### E4: robô responde os verdes (depende de D1, D2, D3, E1.4 e E2)

- [ ] **E4.0** D1, D2 e D3 respondidas e a tabela da seção 2 refeita (E1.4). Sem isso, não começar. Data: ______
- [ ] **E4.1** Cor ligada ou desligada por tipo em `Configuracao`. Prova: teste.
- [ ] **E4.2** Resposta automática só com tipo verde, fonte encontrada e confiança alta; senão amarelo com rascunho. Prova: teste dos três casos de falta.
- [ ] **E4.3** "Resolveu?" depois da resposta do robô; "não" reabre com prioridade. Prova: teste.
- [ ] **E4.4** Sorteio de 5% mais todas as mal avaliadas vão à caixa de decisões. Prova: teste com semente fixa.
- [ ] **E4.5** Botão de desligar por tipo. Prova: teste desliga tipo 1 e o robô para de responder só o tipo 1.
- [ ] **E4.6** Teto diário: ao bater, IA para e os tipos de texto fixo continuam respondidos pelo sistema; o resto vira amarelo. Prova: teste com teto zero mostra tipo 1 respondido sem IA e tipo 10 amarelo.
- [ ] **E4.7** Tela de Regras lida pelo robô. Prova: teste mostra a regra na instrução.
- [ ] **E4.8** Abertura aos poucos: só tipos 1 e 16 no primeiro dia. Os demais abrem um por vez conforme E1.3. Registro de qual abriu quando: ______
- [ ] **Ensaio da E4:** verdes respondidos em menos de 1 min, vermelhos nunca, sorteio na caixa, teto zero mantém texto fixo. Prova: `test_atendimento_automatico.py`.
- [ ] **Auditoria da E4** (seção 6) feita em: ______

### E5: ações automáticas (depende de E4 e D3)

- [ ] **E5.1** Recuperação de acesso por link reaproveitando `solicitar_recuperacao_acesso` de `services/admin/apps/comercial/recuperacao_acesso.py`, adaptada ao canal do suporte. **Proibido** `resetar_senha`. Prova: teste mostra o pedido de link ao destino cadastrado; `grep resetar_senha` em `atendimento/` vazio.
- [ ] **E5.2** Reenviar acesso e boas-vindas. Prova: teste.
- [ ] **E5.3** Pix vencido: só aponta o checkout. **Não existe ação de cobrar.** Prova: `grep -ri "pix\|cobranca\|payment_link" atendimento/` só acha leitura.
- [ ] **E5.4** Compra aprovada sem matrícula: achar a compra (`CompraDaOportunidade`, `Intent`), conferir aprovada, **recuperar a matrícula dessa compra** (mesmo produto e turma). **Proibido** `matricular_aluno`. Amarelo no começo. Prova: teste com compra aprovada e matrícula sumida; `grep matricular_aluno` em `atendimento/` vazio.
- [ ] **E5.4b** Depois de 2 semanas sem erro, E5.4 vira verde. Data: ______ erros no período: ______
- [ ] **E5.5** Reembolso: caso montado e botão para a pessoa, com `PagamentosClient.devolver` só no clique. Prova: teste mostra que nenhuma devolução acontece sem POST da pessoa.
- [ ] **E5.6** Registro de toda ação (quem, quando, resultado) e confirmação de identidade por código para WhatsApp e e-mail. Prova: teste de ação sem código recusada.
- [ ] **Auditoria da E5** (seção 6) feita em: ______

### E6: canais (depende de D4)

- [ ] **E6.0** D4 respondida. Número: ______
- [ ] **E6.1** Conversas de suporte da mensageria entram na fila do atendimento com o mesmo robô. Onde: `services/mensageria/apps/conversas/entrada.py` e `atendimento/service.py`. Prova: teste manda WhatsApp e aparece na fila com tipo e cor.
- [ ] **E6.2** Mesmo histórico por e-mail e telefone do CRM. Prova: teste.
- [ ] **E6.3** Aprovar pelo celular ("1 = aprovar" no WhatsApp da equipe). Prova: teste.
- [ ] **E6.4** Janela de 24 h e modelos aprovados fora dela. Prova: teste com conversa de 25 h usa modelo.
- [ ] **Auditoria da E6** (seção 6) feita em: ______

### E7: base (ND)

- [ ] **E7.1** Resposta aprovada vira sugestão de `Conhecimento` pendente de um clique. Prova: teste.
- [ ] **E7.2** Relatório semanal das 10 causas, com tempo e reaberturas. Prova: teste gera o relatório com dados fixos.
- [ ] **E7.3** Dúvida técnica repetida vira **rascunho** em `PreviaForum`; a pessoa publica. Prova: teste; nada publicado pelo robô.
- [ ] **Auditoria da E7** (seção 6) feita em: ______

---

## 4. Publicação de cada etapa

Repetir ao fim de cada etapa, nesta ordem:

- [ ] Suíte do admin inteira verde localmente (`pytest services/admin/tests -q`). Resultado: ______
- [ ] `makemigrations --check` sem saída.
- [ ] `grep -rn "resetar_senha\|matricular_aluno" services/admin/apps/atendimento/` vazio.
- [ ] `git diff --stat origin/main -- services/checkout services/pagamentos services/aplicacao packages/site_errors packages/outbox-relay` vazio (congelado intacto).
- [ ] Commit no ramo `claude/entrega/suporte-E<n>-<data>` e `infra/robo.py entregar`. Hash: ______
- [ ] `infra/robo.py estado` mostra a entrega aplicada e o site respondendo. Conferir a tela nova no site logado. Hora: ______
- [ ] Atualizar seção 1 deste roteiro e a seção 11 do plano-mestre.

---

## 5. Portões de decisão (o robô para e pergunta só aqui)

| Portão | Antes de | Pergunta ao mantenedor, em português simples |
|---|---|---|
| G1 | E4.0 | "D1: o robô pode responder sozinho os verdes? D2: quanto por mês e por dia? D3: quais regras escritas?" |
| G2 | E5.4b | "Duas semanas sem erro na matrícula recuperada. Pode virar verde?" |
| G3 | E6.0 | "D4: qual número de WhatsApp atende o suporte?" |
| G4 | qualquer passo que toque dinheiro, apague dado ou exponha segredo | pedir a palavra, sempre |

Fora destes portões, o robô não pergunta nada técnico; decide e segue (regra 3 do mantenedor).

---

## 6. Auditoria de etapa (conferências existentes por etapa)

Marcar as sete linhas antes de começar a etapa seguinte. Anotar a data em "Auditoria da E<n> feita em".

1. [ ] **Cada passo da etapa tem prova gravada** (hash de commit ou nome do teste) neste roteiro.
2. [ ] **Nada proibido entrou:** os quatro `grep` da seção 4 vazios.
3. [ ] **Nenhuma mensagem sai sem clique** nos modos assistido e amarelo: teste que conta envios com zero cliques dá zero.
4. [ ] **Vermelhos nunca respondidos pelo robô:** teste com os tipos 13, 14 e 15.
5. [ ] **Privacidade:** o robô continua sem receber e-mail, telefone, CPF ou nota de satisfação (`contexto.py`, teste existente de 10/10).
6. [ ] **Números da E1.3 continuam batendo** depois da etapa (teste de indicadores verde).
7. [ ] **Plano-mestre e este roteiro estão iguais** quanto ao que foi feito; divergência vai para a seção 8.

---

## 7. Testes finais do plano inteiro (só depois de E1 a E7)

O trabalho acaba quando as oito linhas estão marcadas.

- [ ] **T1 Ensaio ponta a ponta com 1.000 pedidos simulados** cobrindo os 16 tipos na fatia da tabela da seção 2 do plano: medir quantos resolvidos sem a pessoa, tempo da pessoa somado (incluindo sorteio), reaberturas. Resultado: ______ % sem a pessoa, ______ min da pessoa.
- [ ] **T2 Meta:** 85% ou mais **resolvidos** (não só respondidos) sem a pessoa; menos de 10% reabrem em 7 dias; satisfação de 4 ou mais. Se não bater, anotar qual tipo puxa para baixo e voltar ao passo dele.
- [ ] **T3 Teto zero:** com o teto de IA zerado, os tipos de texto fixo continuam respondidos e nenhum pedido se perde.
- [ ] **T4 Sistema fora do ar:** com leads, pagamentos ou cursos indisponíveis, nenhum pedido se perde e tudo cai para amarelo.
- [ ] **T5 Ordem escondida:** mensagem de aluno pedindo "libere meu curso", "mande o Pix", "apague meus dados" não dispara ação nenhuma; vira caso para a pessoa.
- [ ] **T6 Congelado intacto:** diff vazio contra `425b82504028db3b7721ae32b776995915280bdb` nas cinco árvores do congelamento.
- [ ] **T7 No site, logado:** fila com tipo e cor, caixa de decisões com um lote aprovado, tela de números com os sete indicadores, "Minha área" do aluno, aviso público e tópico de fórum em rascunho aguardando a pessoa.
- [ ] **T8 Relatório final** escrito em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\RELATORIO-SUPORTE-EM-ESCALA-FINAL.md`: números medidos antes e depois, o que ficou fora e por quê, e o que o mantenedor ainda precisa decidir. Endereço completo no chat.

---

## 8. Pendências e desvios (anotar sempre que travar ou mudar)

| Data | Passo | O que aconteceu | O que falta | Resolvido em |
|---|---|---|---|---|
| | | | | |

---

## 9. Histórico de sessões (uma linha por sessão de trabalho)

| Data | Começou em | Terminou em | Commits | Observação |
|---|---|---|---|---|
| 11/10/2026 | — | — | — | Plano revisado com o Codex e roteiro escrito; nenhum código |


## Execução autorizada em 11/10/2026 — correções e alcance

- Cópia isolada: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011`. Ramo `codex/entrega/suporte-escala-20261011`, criado pela entrada existente; base `8ec12125d99875945f84eccad4c5771115dd440c`. Alterações locais da pasta principal preservadas.
- Entrega atual: E1.1–E1.3 e E2.1–E2.6/E2.10 (rascunhos, prioridade, prazo e caixa de decisões). E2.9 aproveita a confirmação de resolução. E2.7/E2.8 não são necessários à caixa: permanecem explicitamente pendentes, sem ligar lembretes ao aluno, encerramento por silêncio nem oportunidades automáticas.
- Classificação sem chamada de IA. Sem evidência suficiente, amarelo e revisão individual. Vermelhos não entram em envio em lote. A cor não concede autonomia.
- O lote mostra o texto que será enviado; mensagens novas, troca de responsável, produto, agenda ou base exigem rever o grupo. Não há geração de IA depois do clique.
- Custos de execução estão autorizados; D2 é o orçamento do atendimento em produção. D1–D6 continuam sem decisão nova. Prazo de 24 h é referência interna provisória, nunca promessa ao aluno.
- Resolução por confirmação fica distinta da inferência após sete dias sem retorno; encerramento por falta de resposta não pode contar como resolvido. Registros antigos sem informação suficiente permanecem sem medição.
- E1.4: 14 dias reais a partir da ativação comprovada (data ainda pendente). E3: medição de 30 dias só depois da prevenção. E5: duas semanas sem erro só após a recuperação de matrícula. Ensaios não substituem esses períodos.
- Nenhuma mudança nas cinco árvores congeladas, nenhuma resposta autônoma ativada e nenhuma página de documentação publicada.
