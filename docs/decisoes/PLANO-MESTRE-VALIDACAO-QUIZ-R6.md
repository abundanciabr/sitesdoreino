# Plano mestre para validar o funil do quiz e a recomendação R6

## Objetivo

Transformar o parecer colado pelo mantenedor em três investigações independentes e um gate de síntese. A entrega desta etapa são evidências e uma decisão recomendada para planejamento. Não é autorização para implementar instrumentação, campanhas, integrações ou mudanças de produto.

## Decisão de organização

As três frentes investigam (1) cobertura e qualidade da medição econômica, (2) confiabilidade observável da jornada e (3) desenho e viabilidade do experimento quiz versus página direta. O cruzamento é feito somente depois das três devoluções. Separar essas perguntas permite avançar em paralelo sem duplicar auditoria nem confundir hipótese com defeito.

## Roadmap e checklist vivo

- [ ] **Preparação:** leis, plano, fila viva, dependências e bancada conferidos. A, B e C foram reutilizadas de tarefas existentes, mas não foi localizado contrato de fila R6 registrado antes dessas execuções; esse requisito não pode ser declarado cumprido retroativamente.
- [x] **Frente A, dados econômicos:** devolução existente recebida; uma amostra econômica de produção não foi reconciliada. Evidência e limites abaixo.
- [x] **Frente B, confiabilidade:** devolução existente recebida; os achados são de código/teste e registros históricos, não uma medição operacional atual.
- [x] **Frente C, experimento:** protocolo devolvido; amostra e duração não foram estimadas por falta de insumos reais.
- [x] **Síntese:** cruzamento abaixo. A recomendação é somente de planejamento de uma medição de prontidão; não libera implementação ou lançamento.
- [x] **Revisão separada:** revisão final independente em `gpt-6-luna` / `high` aprovada após duas correções; conferiu histórico do checklist e não encontrou outro achado factual.
- [ ] **Fechamento:** atualizar este checklist com evidência e estado real; publicar/acessar a versão viva no destino aprovado e registrar conclusão segundo os ritos do projeto.

### Regras de coordenação

1. As frentes A, B e C não esperam umas pelas outras; a síntese depende das três.
2. Cada executor é responsável apenas por sua pergunta. Não editar produto, código, contratos, dados ou campanhas.
3. Cada afirmação deve conter fonte consultada, data/revisão, o que prova e o que não prova. Sem acesso, escrever **NÃO MEDIDO** e apontar o meio de medição.
4. Descoberta fora do escopo não abre trabalho lateral: classificar e encaminhar pela fila. Não alterar este contrato unilateralmente.
5. Duas tentativas sem mover um critério exigem checkpoint e abordagem diferente; não repetir consultas sem hipótese nova.
6. Resultado inconclusivo é resultado válido. Não escolher vencedor por CPL, volume de leads ou métrica secundária.
7. Pagamentos/checkout/Mercado Pago permanecem fora de iniciativa. Inspeção de evidência existente é permitida; qualquer operação real, alteração ou nova instrumentação requer mandato específico.
8. Não criar agentes a partir das frentes. A sessão principal coordena e faz a síntese.

## Critérios de saída

- Cada frente entrega achados, fontes, limites, incógnitas, riscos, próxima ação e evidência reproduzível.
- A frente A demonstra uma jornada reconciliada ou nomeia precisamente o elo que impede a reconciliação; correlação não é causalidade.
- A frente B relata falhas observadas separadas de riscos hipotéticos e não causa efeitos em produção.
- A frente C não afirma duração, significância ou amostra sem dados. Se não for possível calcular, registra os insumos ausentes.
- A síntese recomenda somente planejamento ou medição já autorizados, separa decisões do mantenedor e não converte recomendação em execução.
- A revisão independente não encontra extrapolação sem evidência nem colisão entre frentes.

## Evidências recebidas e síntese de planejamento — 25/09/2026

### Rastreabilidade das devoluções

- **A — “Auditar medição econômica”**, tarefa Codex `01a0d9cc-0aeb-73e3-9d7c-82afcac3b993`: relatório concluído, sem alteração de arquivos. Revisou a base `7d86f43a52b4b888a03302f888ebe62b57a14428` (23/09/2026). Não acessou amostra de produção.
- **B — “Auditar confiabilidade da jornada”**, tarefa Codex `01a0d9cc-2dc8-7671-bb06-4715a1a1183e`: relatório concluído, sem alteração de arquivos. Revisou a mesma base de 23/09/2026. Evidência operacional de produção não foi inspecionada.
- **C — “Defina protocolo para comparar quiz”**, tarefa Codex `01a0d9cc-508a-7072-a98e-968cb0793c4b`: protocolo concluído sem lançamento ou alteração. Insumos atuais não permitem estimar amostra ou duração.
- A fila ao vivo não apresentou TAR R6 correspondente; as tarefas antigas com escopo próximo estavam encerradas e não foram reabertas nem tiveram contratos alterados. O evento TAR-720, encontrado na atualização mais recente, trata da recuperação de acesso do GitHub e não pertence ao plano R6.

### Fatos que as fontes sustentam

1. **Cobertura econômica, conforme o relatório A** (`01a0d9cc-0aeb-73e3-9d7c-82afcac3b993`; revisão `7d86f43a52b4b888a03302f888ebe62b57a14428`, 23/09): os contratos de [página vista](../../contracts/eventos/funil.pagina-vista.v1.json), [quiz completado](../../contracts/eventos/quiz.completado.v1.json), [lead capturado](../../contracts/eventos/funil.lead-capturado.v1.json), [pedido criado](../../contracts/eventos/pedido.criado.v1.json), [pagamento aprovado v2](../../contracts/eventos/pagamento.aprovado.v2.json), [pagamento estornado v2](../../contracts/eventos/pagamento.estornado.v2.json) e [matrícula alterada](../../contracts/eventos/matricula.situacao-alterada.v1.json) descrevem payloads, não emissão nem completude. O relatório localizou quiz e matrícula entre os streams de [consume_eventos.py](../../services/metricas/apps/fatos/management/commands/consume_eventos.py), mas não visita, lead, pagamento, estorno ou aula concluída; também registrou limite de corte na [API de fatos](../../services/metricas/apps/fatos/api.py). A afirmação vale para o código naquela revisão, não para produção ou o código posterior. Sem amostra autorizada, todos os elos ficaram `NÃO MEDIDO` em produção. Custos variáveis não foram conciliados.
2. **Confiabilidade, conforme o relatório B** (`01a0d9cc-2dc8-7671-bb06-4715a1a1183e`; mesma revisão de 23/09): os comportamentos relatados aparecem nos caminhos de [progresso](../../services/cursos/apps/cursos/progresso.py) e seu [modelo](../../services/cursos/apps/cursos/models.py), na [idempotência de intent](../../services/pagamentos/tests/test_inv_p4_intent_idempotente.py), na [matrícula por pedido](../../services/alunos/apps/matriculas/services.py), na [deduplicação de mensagens](../../services/mensageria/tests/test_dedup_entre_versoes_de_pagamento.py), no [webhook Pix](../../services/pagamentos/pagamentos/methods/pix/webhook.py) e [teste de endurecimento](../../services/pagamentos/tests/test_webhook_endurecimento.py), e no [reprocessamento de eventos mortos](../../services/mensageria/tests/test_eventos_mortos_recuperaveis.py). Esses arquivos e testes provam apenas os caminhos cobertos na revisão; não medem taxa de sucesso, duplicidade ou fila pendente em produção. O relatório classifica cancelamento de sequência promocional após compra como hipótese, sem prova de envio indevido.
3. **Comparação, conforme o relatório C** (`01a0d9cc-508a-7072-a98e-968cb0793c4b`): é uma proposta, não comportamento implantado. Recomenda atribuição persistente 1:1, separar atribuição de exposição, manter iguais produto/termos/público e analisar por intenção de tratar; define margem de contribuição líquida por visitante atribuído como métrica principal e deixa leads, CPL e conclusão do quiz como diagnósticos secundários. Sem oferta confirmada, distribuição de margem, volume, atraso de conversão/reembolso e parâmetros de decisão, não há base para tamanho de amostra, duração ou vencedor.
4. **Exemplos históricos, conforme o relatório C:** o relatório cita uma resposta pública de `/quiz/crivo/` em 20/09 e um teste de `/oferta` com produto fictício de R$ 9,90 em 22/09, sem cobrança. São registros de rota/teste narrados pelo relatório, não prova de funil comercial, comparabilidade dos braços, pagamento ou resultado econômico.

### Cruzamento, limites e recomendação

- **Convergência:** A e C identificam a ausência de uma junção econômica comprovada entre visitante atribuído, exposição, versão do quiz, oferta, pagamento, reembolso e custos. B mostra que alguns componentes têm proteção no código, mas não acrescenta telemetria de produção que feche essa lacuna.
- **Sem conflito factual resolvido por inferência:** a hipótese de mensagem após compra em B não é evidência de falha; a presença de contratos de eventos em A não contradiz a falta de entrega/reconciliação observada. São níveis de prova diferentes.
- **Evidência envelhecida:** as três devoluções usam a base de 23/09. A comparação `git diff --name-status 7d86f43a52b4b888a03302f888ebe62b57a14428..origin/main` mostra mudanças posteriores em `services/funil/apps/core/views.py`, URLs e testes de funil, além de mudanças extensas em `services/pagamentos/`. As frentes não revalidaram seus achados contra esse código, então eles são retratos da revisão de 23/09, não estado atual confirmado. Também entrou o manual público [Plataforma de Experimentação e Aprendizado de Conversão](../../documentos/plataforma-experimentacao-e-aprendizado-de-conversao.md), commit `3118c765`; ele é um documento com roadmap, não prova de que a plataforma esteja implementada. O próprio manual declara assignment, exposure e inferência experimental como não implementados e descreve como existentes apenas a base de páginas, visitante e evento inicial. Essa declaração documental não substitui validação do código.
- **Recomendação para planejamento:** antes de decidir qualquer teste quiz versus página direta, definir uma tarefa de medição de prontidão com contrato próprio, população/oferta e janela explicitadas, fontes existentes autorizadas, junções permitidas, minimização de dados e critérios de completude. Depois, medir uma amostra agregada e sem dados pessoais desnecessários somente se os acessos existentes permitirem. Se os elos não fecharem, registrar os insumos ausentes e submeter nova decisão de escopo. Não lançar variante, não adicionar instrumentação e não escolher vencedor nesta etapa.
- **Decisões ainda necessárias:** produto e oferta comparáveis; população e exclusões; janela de conversão e maturidade de reembolso; limiar econômico e guardas; acesso autorizado aos dados e responsável pela extração. Não há afirmação legal nesta síntese que exija conclusão jurídica.

### Fonte da síntese e verificação do destino

Esta síntese foi preparada na bancada isolada `wt-site-validacao-quiz-r6`, após atualizar sua base com `origin/main`. O plano original do clone principal foi preservado. O destino documental definido pelo pedido é este plano interno em `docs/decisoes/`; a cópia existe e foi conferida na bancada. Publicação pública não foi solicitada nem realizada. A entrega no destino final e o registro de conclusão não foram feitos porque não há TAR/contrato R6 que permita cumprir o rito sem criar escopo unilateralmente.

## Prompt 1 — Orquestração e síntese

Você coordena o plano mestre em `docs/decisoes/PLANO-MESTRE-VALIDACAO-QUIZ-R6.md`. Execute somente a preparação, acompanhe as devoluções das frentes A, B e C e faça a síntese após receber evidências das três. Não reimplemente nada. Reconcilie fila e trabalho existente, abra/retome a bancada e registre um contrato por frente conforme `docs/decisoes/ROTEIRO-EXECUCAO-DOS-AGENTES.md`. Só delegue se a ferramenta permitir configurar explicitamente `gpt-6-luna` com esforço `high`; se não permitir, não crie agente nem altere o modelo, e reporte o bloqueio. Proíba os executores de criar agentes. Preserve este escopo, os gates e a revisão separada. Não declare concluído antes da revisão independente, atualização do checklist com evidência e verificação do destino de publicação.

## Prompt 2 — Frente A: cobertura e qualidade dos dados

Investigue somente a cobertura e qualidade da medição econômica já existente. Compare o plano anteriormente citado e os relatórios/telemetria disponíveis com a cadeia campanha/criativo → quiz/versão/variante → oferta → lead → pagamento aprovado → reembolso → custos variáveis → ativação. Para cada elo, registre estado (disponível, ausente, ou qualidade não conhecida), fonte exata, data/revisão, o que a fonte prova e o que não prova. Tente reconciliar uma amostra apenas com acesso autorizado e sem expor dados pessoais. Não construa dashboard, eventos, CAPI, queries persistentes ou instrumentação; não altere dados nem operação comercial. Não trate receita como margem nem associação como causalidade. Devolva incógnitas e o menor próximo passo de medição. Não crie agentes.

## Prompt 3 — Frente B: confiabilidade da jornada

Investigue somente evidências existentes de confiabilidade: salvamento e retomada, idempotência/deduplicação, confirmação de pagamento, integração e reprocessamento de falhas e interrupção de mensagens após compra/descadastro. Inspecione código, testes, logs ou registros somente pelos acessos autorizados. Para cada caso, classifique como falha observada, comportamento comprovado, não medido ou cenário hipotético, com fonte e limite. Não simule pagamento real, não toque checkout/Mercado Pago em produção, não altere integrações, dados, campanhas ou código. Não transforme risco em defeito. Devolva achados e evidência reproduzível. Não crie agentes.

## Prompt 4 — Frente C: desenho do experimento

Especifique em papel o experimento quiz versus página direta para mesma oferta e público. Defina hipótese, elegibilidade, atribuição persistente, evento de exposição, métrica principal econômica, proteções, janela de conversão e regra de inconclusão. Liste insumos realmente disponíveis e ausentes para estimar amostra/duração; não invente tráfego, baseline, significância ou prazo. Distinga requisito de decisão de produto e requisito de implementação. Não lance variante, não altere páginas, tracking, ofertas ou orçamento, e não declare o quiz vencedor por CPL ou leads. Devolva o protocolo mínimo, dependências, limites e caminho de medição. Não crie agentes.

## Prompt 5 — Revisão independente

Revise o plano e a síntese final sem editá-los. Você não pode ser autor de nenhuma frente nem da síntese. Tente reprovar: rastreabilidade das fontes, inferências causais, hipóteses apresentadas como falhas, dados pessoais, restrição de pagamentos, colisões/duplicação entre frentes, decisões exclusivas do mantenedor, conclusão prematura e fidelidade do checklist ao estado evidenciado. Cite seção/linha, problema e correção objetiva. Só aprove se as três frentes tiverem evidência e cada afirmação decisória tiver limite explícito. Não crie agentes. Se não houver agente compatível com modelo gpt-6-luna e esforço high, declare a revisão pendente e não declare o plano concluído.

## Estado desta preparação

A, B e C foram retomadas de tarefas independentes já concluídas, evitando duplicar investigações. As devoluções chegaram antes da síntese. O requisito de contrato da fila anterior ao início não foi atendido pelas execuções existentes e permanece uma lacuna registrada; não será simulado com registro retroativo. A revisão independente final foi aprovada em `gpt-6-luna` / `high`, depois de corrigir as fontes, a descrição do manual e o histórico do checklist. Preparação continua não atendida por falta do contrato prévio. Fechamento ainda depende do rito de entrega e da conferência/registro do destino aprovado.
