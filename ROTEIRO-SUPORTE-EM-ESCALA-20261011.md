# Roteiro de execução do suporte em escala (checklist vivo do robô)

- **Endereço deste documento:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\ROTEIRO-SUPORTE-EM-ESCALA-20261011.md` (cópia local; documento em versionamento nesta entrega, sem publicação como página).
- **Plano que ele executa:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\PLANO-MESTRE-SUPORTE-EM-ESCALA-20261011.md`. O plano diz **o quê e por quê**; este roteiro diz **em que ordem, com que prova e onde marcar**.
- **Código:** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\` (ramo de trabalho). Entregar o código é pelo integrador: `infra/robo.py entregar` com ramo `codex/entrega/suporte-escala-20261011`; a main é protegida.
- **Criado em 11/10/2026.** Última atualização: 11/10/2026 (execução autorizada; base atual 8ec12125d99875945f84eccad4c5771115dd440c; código implementado e provas locais registradas; conferência no site pendente).

---

## 0. Como o robô usa este roteiro (ler antes de qualquer passo)

1. **Ao começar qualquer sessão**, leia a seção 1 (estado) e ache o **primeiro passo não marcado**. É por ali que o trabalho continua. Não comece por outro lugar.
2. **Um passo por vez.** Cada passo tem: o que fazer, onde, qual a prova e o que marcar. Só marque `[x]` depois da prova passar; implementação, ativação e medição real têm registros separados. Prova é teste rodando verde ou tela conferida no site, nunca "parece certo".
3. **Ao terminar um passo**, atualize no mesmo momento: a caixa do passo, a seção 1 (estado) e a linha "Última atualização" acima. Grave o hash do commit na coluna "Prova". Se a sessão cair, a próxima sessão acha tudo aqui.
4. **Travou?** Escreva na seção 8 (pendências) o que travou, por quê e o que falta, e **passe ao próximo passo que não depende dele**. Nunca fique parado num passo nem pule para o fim.
5. **Mudou o plano?** O plano-mestre é a fonte. Se um passo aqui contradiz o plano, corrija este roteiro, não o plano, e anote na seção 8.
6. **Nunca faça fora do roteiro:** gerar Pix ou link de pagamento, usar `resetar_senha`, usar `matricular_aluno`, publicar aviso no site ou tópico no fórum em nome do robô, escrever em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\checkout`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\pagamentos`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\aplicacao`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\site_errors`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\packages\outbox-relay` (Mercado Pago congelado, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\AGENTS.md`).
7. **Decisões do mantenedor (D1 a D6)** só ele responde. Até responder, faça só os passos marcados "não depende de decisão". Não invente a resposta.
8. **E2 começa após E1.1 e o histórico necessário de E1.2.** A medição E1.4 de 14 dias não bloqueia rascunhos assistidos; bloqueia a ampliação da autonomia da E4. O plano todo termina com a seção 7 (testes finais). A seção 7 encerra o plano completo E1–E7; esta entrega se encerra com as provas do escopo E1 e dos rascunhos/caixa da E2. Medição e etapas futuras ficam separadas.
9. **Teste por etapa:** rode só os testes do que mudou (`C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\tests\test_atendimento*.py` e o que o passo citar), com o Postgres da sessão por `DATABASE_URL` (ver memória "Testes paralelos da mesma célula"). Antes de publicar, rode a suíte do admin inteira uma vez.
10. **Economia:** sem ajudantes ou workflows adicionais; usar o navegador para a conferência no site prevista nesta entrega. Respostas curtas ao mantenedor, em português simples.

---

## 1. Estado agora (atualizar sempre)

| Campo | Valor |
|---|---|
| Etapa atual | E1.1–E1.3 e rascunhos/caixa da E2 implementados e testados; entrega em preparação |
| Passo atual | Entrega pelo integrador e conferência autenticada no site |
| Último commit publicado do suporte | `b72bf7ce8` (contexto com compras, agenda e interesse no CRM, 10/10/2026) |
| Decisões respondidas | D5 parcial: expediente vigente, segunda a sexta, 14h–18h de Brasília; prazo humano pendente. D1–D4 e D6 abertas |
| Pendências abertas (seção 8) | Medição de 14 dias; decisões D1–D6; E2.7/E2.8 e E3–E7 fora do escopo |
| Auditorias feitas (seção 6) | nenhuma |

---

## 2. Antes de começar (uma vez)

- [x] **P0.1** Conferir que o ramo de trabalho está em dia com a main: em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\`, `git fetch` e `git log --oneline -1 origin/main`. Prova: main conferida e incorporada: `c0711d9d72c6f2e3b66b6d3c416c67b8cc402c60`; merge local `b0d9a429173ee669210cdfe46e5ca085e429b730`
- [x] **P0.2** PostgreSQL isolado da sessão em 127.0.0.1:61921, sem tocar nos bancos de produção. O teste antigo de streaming fechava a conexão da transação; foi corrigido consumindo o streaming pelo cliente Django. Prova final: 165 testes do suporte aprovados.
- [x] **P0.3** Ler `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\models.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\gestao.py`, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\indicadores.py` uma vez e anotar aqui achados: os campos de primeira resposta e encerramento já existiam; a recepção automática não é resposta de mérito; reabrir apagava o estado da rodada anterior sem histórico próprio
- [x] **P0.4** Confirmar que não há migração pendente em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\migrations` fora da main. Prova: `python manage.py makemigrations --check --dry-run atendimento` sem saída.

---

## 3. Passos por etapa

Cada linha: **passo**, o que fazer, onde, **prova**. A ordem dentro da etapa é a ordem de execução. "ND" = não depende de decisão do mantenedor.

### E1: números (ND)

- [x] **E1.1a** Campos novos em `Conversa`: `tipo` (16 tipos da seção 5 do plano), `cor` (verde, amarelo, vermelho), `degrau` (consultar, mostrar, cobrar), `humor`; reaproveitar `prioridade` para urgência. Migração. Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\models.py`. Prova: aplicação, reversão e reaplicação em banco vazio; `test_classifica_16_tipos_sem_ia`.
- [x] **E1.1b** Classificação na chegada em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py`: função que recebe a conversa e devolve tipo, cor, degrau, urgência e humor. Vermelho é fixo para tipos 13, 14 e 15; "cobrar" nunca sai verde. Prova: teste com uma mensagem de cada um dos 16 tipos; os três vermelhos saem vermelhos sempre.
- [x] **E1.1c** Tipo e cor aparecem na fila (`gestao.contexto_fila` e template). Prova: teste de view mostra o rótulo.
- [x] **E1.2a** Três estados separados: `primeira_resposta_em` e `encerrada_em` existentes, mais `resolvida_em` em `Conversa`, e modelo `Reabertura` (conversa, quando, motivo, quem). Migração. Prova: teste cria conversa, responde, encerra, reabre; os três campos e a reabertura ficam gravados e distintos.
- [x] **E1.2b** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py`: responder mantém `primeira_resposta_em` existente; encerrar mantém `encerrada_em` existente; resolvido só por "sim" do aluno ou 7 dias sem volta; qualquer mensagem nova depois de encerrado cria `Reabertura` e limpa `resolvida_em`. Prova: teste cobre os quatro caminhos.
- [x] **E1.3a** `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\indicadores.py`: fatia por tipo, tempo da pessoa por tipo (do primeiro clique da equipe ao envio), tempo até a primeira resposta e até resolvido, reaberturas em 7 dias, satisfação, custo de IA por pedido, pedidos por 100 alunos ativos. Prova: teste com dados fixos confere cada número.
- [ ] **E1.3b** Tela de números em `https://meshcraft.top/admin/atendimento/` (aba ou página). Prova: teste de view; conferir no site depois de publicar.
- [ ] **E1.4** Depois de 2 semanas no ar: refazer a tabela da seção 2 do plano com os números medidos. Prova: tabela nova no plano com a data da medição. Data prevista: ______
- [ ] **Auditoria da E1** (seção 6) feita em: ______

### E2: rascunhos e caixa de decisões (ND, depende de E1.1)

- [x] **E2.1** `contexto.preparar` passa a preencher `resposta` com o rascunho no modo assistido. Nada é enviado sem clique. Prova: teste mostra `resposta` cheia e nenhuma mensagem enviada ao aluno.
- [x] **E2.2** Textos fixos por tipo (1 a 5, 7, 9, 16) com campos preenchidos pelo sistema (nome, data da agenda, situação do pagamento, link do checkout que existe). Onde: módulo novo `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\textos_fixos.py`. IA só quando o texto fixo não cobre. Prova: teste de cada tipo gera o texto sem chamar IA (contador de chamadas em zero).
- [x] **E2.3** Prioridade automática: vermelho, humor irritado, comprador dos últimos 7 dias, reaberto. Prova: teste ordena a fila.
- [x] **E2.4** Fila por prazo: "sem resposta há X" e destaque ao passar de 24 h (ou D5). Prova: teste de view com conversa antiga destacada.
- [x] **E2.5** Agrupamento por tipo, produto e pergunta parecida. Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\gestao.py`. Prova: teste junta 5 pedidos iguais num grupo e separa um diferente.
- [x] **E2.6** Tela "Caixa de decisões": lista grupos, aprova um texto e o sistema preenche dados de cada aluno sem IA. Rota em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\config\urls.py`, template novo. Prova: teste aprova grupo de 30 com um POST, 30 respostas saem, zero chamadas de IA.
- [ ] **E2.7** Próximo passo com prazo e responsável; lembrete por `Aviso` quando vence; lembrete ao aluno; encerramento por falta de resposta **sem** marcar resolvido. Prova: teste com relógio avançado.
- [ ] **E2.8** Resumo no CRM ao encerrar e `Oportunidade` quando há interesse em produto não comprado. Prova: teste confere o histórico do lead e a oportunidade criada.
- [x] **E2.9** "Resolveu?" ao encerrar, ligado a `avaliacao_disponivel`. "Sim" marca resolvido; "não" cria `Reabertura` com prioridade. Prova: teste dos dois caminhos.
- [x] **E2.10** Atalhos de teclado na caixa de decisões. Prova: conferir no site.
- [x] **Ensaio da E2:** 200 pedidos de ensaio, um grupo de 30 aprovado com um clique, zero IA por aluno, nada enviado sem clique. Prova: `test_ensaio_200_30_em_um_clique_zero_ia_e_repeticao_idempotente` em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\tests\test_atendimento_escala.py`.
- [ ] **Auditoria da E2** (seção 6) feita em: ______

### E3: prevenção (ND, depende da agenda e de E1.3)

- [ ] **E3.1** Jornada "começa amanhã" a partir de `AgendaDoProduto`, pela mensageria. Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\mensageria\apps\jornadas`. Prova: teste cria compra com data amanhã e a mensagem entra na fila de envio uma vez só.
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

- [ ] **E5.1** Recuperação de acesso por link reaproveitando `solicitar_recuperacao_acesso` de `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\comercial\recuperacao_acesso.py`, adaptada ao canal do suporte. **Proibido** `resetar_senha`. Prova: teste mostra o pedido de link ao destino cadastrado; `grep resetar_senha` em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento` vazio.
- [ ] **E5.2** Reenviar acesso e boas-vindas. Prova: teste.
- [ ] **E5.3** Pix vencido: só aponta o checkout. **Não existe ação de cobrar.** Prova: `grep -ri "pix\|cobranca\|payment_link" atendimento/` só acha leitura.
- [ ] **E5.4** Compra aprovada sem matrícula: achar a compra (`CompraDaOportunidade`, `Intent`), conferir aprovada, **recuperar a matrícula dessa compra** (mesmo produto e turma). **Proibido** `matricular_aluno`. Amarelo no começo. Prova: teste com compra aprovada e matrícula sumida; `grep matricular_aluno` em `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento` vazio.
- [ ] **E5.4b** Depois de 2 semanas sem erro, E5.4 vira verde. Data: ______ erros no período: ______
- [ ] **E5.5** Reembolso: caso montado e botão para a pessoa, com `PagamentosClient.devolver` só no clique. Prova: teste mostra que nenhuma devolução acontece sem POST da pessoa.
- [ ] **E5.6** Registro de toda ação (quem, quando, resultado) e confirmação de identidade por código para WhatsApp e e-mail. Prova: teste de ação sem código recusada.
- [ ] **Auditoria da E5** (seção 6) feita em: ______

### E6: canais (depende de D4)

- [ ] **E6.0** D4 respondida. Número: ______
- [ ] **E6.1** Conversas de suporte da mensageria entram na fila do atendimento com o mesmo robô. Onde: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\mensageria\apps\conversas\entrada.py` e `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\service.py`. Prova: teste manda WhatsApp e aparece na fila com tipo e cor.
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
- [ ] Commit no ramo `codex/entrega/suporte-escala-20261011` e `infra/robo.py entregar`. Hash: ______
- [ ] `infra/robo.py estado` mostra a entrega aplicada e o site respondendo. Conferir a tela nova no site logado. Hora: ______
- [ ] Atualizar seção 1 deste roteiro e a seção 11 do plano-mestre.

---

## 5. Decisões do mantenedor já previstas no plano

| Referência | Antes de | Pergunta ao mantenedor, em português simples |
|---|---|---|
| G1 | E4.0 | "D1: o robô pode responder sozinho os verdes? D2: quanto por mês e por dia? D3: quais regras escritas?" |
| G2 | E5.4b | "Duas semanas sem erro na matrícula recuperada. Pode virar verde?" |
| G3 | E6.0 | "D4: qual número de WhatsApp atende o suporte?" |
| G4 | qualquer passo que toque dinheiro, apague dado ou exponha segredo | pedir a palavra, sempre |

As decisões acima não impedem o trabalho já autorizado de E1 e da caixa assistida da E2.

---

## 6. Auditoria de etapa (conferências existentes por etapa)

Marcar as sete linhas antes de começar a etapa seguinte. Anotar a data em "Auditoria da E<n> feita em".

1. [ ] **Cada passo da etapa tem prova gravada** (hash de commit ou nome do teste) neste roteiro.
2. [ ] **Nada proibido entrou:** os quatro `grep` da seção 4 vazios.
3. [ ] **Nenhuma mensagem sai sem clique** nos modos assistido e amarelo: teste que conta envios com zero cliques dá zero.
4. [ ] **Vermelhos nunca respondidos pelo robô:** teste com os tipos 13, 14 e 15.
5. [ ] **Privacidade:** o robô continua sem receber e-mail, telefone, CPF ou nota de satisfação (`C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\apps\atendimento\contexto.py`, teste existente de 10/10).
6. [ ] **Números da E1.3 continuam batendo** depois da etapa (teste de indicadores verde).
7. [ ] **Plano-mestre e este roteiro estão iguais** quanto ao que foi feito; divergência vai para a seção 8.

---

## 7. Testes finais do plano inteiro (só depois de E1 a E7)

As oito linhas encerram o plano completo E1–E7, não a entrega atual de E1 e rascunhos/caixa da E2.

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
| 11/10/2026 | E1.4 | Exige 14 dias reais após ativação | Registrar o início visto no painel e medir ao completar a janela | Pendente |
| 11/10/2026 | Suíte geral | Testes antigos de documentos falham também na main diante da publicação manual | Registro separado; proteção preservada | Confirmado na main |
| 11/10/2026 | E2.7/E2.8; E3–E7 | Fora desta entrega | Nova execução no escopo correspondente; D1–D6 quando aplicáveis | Não iniciado |

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
- Custos de execução estão autorizados; D2 é o orçamento do atendimento em produção. D1–D4 e D6 continuam sem decisão nova; em D5, falta o prazo humano, preservando o expediente vigente. Prazo de 24 h é referência interna provisória, nunca promessa ao aluno.
- Resolução por confirmação fica distinta da inferência após sete dias sem retorno; encerramento por falta de resposta não pode contar como resolvido. Registros antigos sem informação suficiente permanecem sem medição.
- E1.4: 14 dias reais a partir da ativação comprovada (data ainda pendente). E3: medição de 30 dias só depois da prevenção. E5: duas semanas sem erro só após a recuperação de matrícula. Ensaios não substituem esses períodos.
- Nenhuma mudança nas cinco árvores congeladas, nenhuma resposta autônoma ativada e nenhuma página de documentação publicada.

## Provas da implementação — 11/10/2026

- Código: `db7036d81`; main atual incorporada em `b0d9a429173ee669210cdfe46e5ca085e429b730`. A publicação pelo integrador ainda precisa ser confirmada no registro abaixo.
- Suporte: **165 testes aprovados**, incluindo 16 tipos, vermelhos sem resposta automática, preservação da rodada, sim/não, retorno em sete dias, prazo, prioridade, texto individualizado, lote idempotente de 30 entre 200 e recusa integral após mudança da fonte/destinatário. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-suporte.txt`.
- Migração nova aplicada, revertida e reaplicada em banco vazio; sem migração de atendimento faltando. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\migracao-comprovada.txt`.
- Testes antigos de documentos na main: 12 falhas e 16 aprovações, sem alterações desta tarefa. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-base-main.txt`. Suíte geral completa: 2.837 aprovados, 101 falhas, 51 erros e 1 pulado: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-admin-completo.txt`. Não é apresentada como verde.
- Diff das cinco árvores congeladas vazio tanto contra a main como contra `425b82504028db3b7721ae32b776995915280bdb`. Nenhuma configuração de autonomia foi alterada. No site, Comunidade, Cursos e Site estavam assistidos antes da entrega; o teto existente de US$ 10/mês permanece, sem presumir a decisão D2 de escala.
- Evidências locais acima existem somente neste PC; os dois documentos são versionados e não viram páginas. Teste principal: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\wt-suporte-escala-20261011\services\admin\tests\test_atendimento_escala.py`.

### Comparação final e alcance da prova

A suíte geral não ficou verde. A falha do teste de streaming do suporte foi corrigida e sua suíte passou. Os demais casos foram executados no mesmo recorte na main limpa e nesta candidata: **99 falhas, 33 aprovações e 19 erros em ambas, com as mesmas identidades de casos reprovados**. A comparação distingue falhas do conjunto antigo de regressões da entrega; não remove nem contorna a proteção de documentos. Prova local: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\comparacao-testes.json`; logs `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\falhas-comparadas-main.txt` e `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\falhas-comparadas-atual.txt`.

Após retirar o lembrete novo de prazo (E2.7 está fora desta entrega), os **47 testes da etapa** passaram novamente: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\testes-escala-final.txt`. Permanecem apenas os avisos já existentes; nenhum lembrete novo ao aluno foi ativado.

Os atalhos Alt+N, Alt+P, Alt+A e Alt+E foram exercitados no navegador com o template real e destinatários fictícios. O servidor estático recebeu o POST de ensaio sem backend de envio e a navegação individual; os testes Django comprovam o processamento real. Prova somente neste PC: `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923\output\suporte-escala-20261011\prova-teclado.json`. Nenhuma mensagem foi enviada a um aluno real durante a conferência.


### Integração do expediente vigente

A main avançou durante a preparação para `dcc01be3edb23e72e9c9722f05c412f1fa76fe5c`, incluindo o expediente do suporte e outra entrega de Sandbox. As duas foram preservadas. A entrega inicial `89d486d85206` foi sucedida pela candidata que incorpora essa main. Os três widgets existentes (admin, cursos e fórum) preservam o expediente e recebem a confirmação de resolução; nenhum conteúdo foi publicado no fórum.

Após a combinação, os **165 testes de suporte passaram**. As duas migrações 0005 foram unidas pela migração 0006; aplicação, reversão e reaplicação em banco isolado passaram, e `makemigrations --check` não encontrou mudanças. A comparação das falhas antigas foi feita contra a main `c0711d9d72c6f2e3b66b6d3c416c67b8cc402c60`; não é apresentada como uma execução integral sobre a main posterior.

A conferência autenticada em `https://meshcraft.top/admin/atendimento/configuracao/` encontrou Comunidade, Cursos e Site em modo Assistido, expediente ativo de segunda a sexta das 14h às 18h (Brasília), sábado e domingo fechado, e o orçamento existente de US$ 10/mês. Nenhuma configuração foi salva pela tarefa. D5 ainda precisa do prazo de resposta humana; 24h permanece apenas um destaque interno provisório, sem promessa e sem cálculo de horas úteis.
