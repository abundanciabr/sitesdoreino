# MESHCRAFT SCALE OS — Growth Execution Engine v1.0

**Quinto documento da IA externa, trazido pelo mantenedor em 04/09/2026.**
Guardado inteiro e sem edição, como os quatro anteriores. O confronto de cada
premissa com as decisões da casa está em
`CONFRONTO-growth-execution-engine.md`, nesta mesma pasta.

Playbook de Implementação para Agentes de IA.

---

# 0. MISSÃO

Implementar dentro da plataforma Meshcraft um sistema integrado de gestão estratégica, crescimento e execução capaz de transformar:

**estratégia → objetivos → métricas → gargalos → decisões → experimentos → tarefas → execução → resultados → aprendizado → nova estratégia.**

O sistema NÃO deve ser apenas um painel de indicadores.

Ele deve funcionar como um **Growth Execution Operating System**, capaz de coordenar humanos e agentes de IA em ciclos contínuos de crescimento.

O sistema deverá integrar cinco mecanismos:

**OKR → 4DX → Growth/AARRR → Sprint Semanal → Kanban operacional.**

A cadeia causal principal será:

**Visão** ↓ **Objetivos trimestrais** ↓ **Key Results** ↓ **MCI — Meta Crucialmente Importante** ↓ **Lead Measures** ↓ **Gargalo prioritário** ↓ **Hipóteses** ↓ **Experimentos** ↓ **Sprint** ↓ **Tarefas** ↓ **Execução humana/IA** ↓ **Resultados** ↓ **Aprendizado** ↓ **Decisões** ↓ **Próximo ciclo**

---

# 1. PRINCÍPIO ARQUITETURAL FUNDAMENTAL

Não implementar OKR, 4DX, métricas, tarefas e experimentos como sistemas independentes.

Eles precisam formar um **grafo causal único**.

Toda tarefa relevante deverá conseguir responder:

> "Que resultado estratégico esta tarefa pretende movimentar?"

E todo indicador estratégico deverá permitir responder:

> "Que ações estão sendo executadas para movimentá-lo?"

Uma tarefa sem relação com objetivo, gargalo, experimento ou necessidade operacional deverá ser classificada explicitamente como:

`whirlwind`

ou seja: **trabalho necessário para manter a operação funcionando, mas que não representa iniciativa de crescimento.**

Isso evitará confundir atividade com progresso.

---

# 2. HIERARQUIA TEMPORAL DO SISTEMA

## Camada 1 — Estratégia

Horizonte: **12 meses.** Contém: visão; North Star; metas anuais; prioridades estratégicas; teses de crescimento.

## Camada 2 — OKR

Horizonte padrão: **trimestre de aproximadamente 12–13 semanas.**

Cada ciclo poderá ter: 1–3 Objectives; 2–5 Key Results por Objective.

Não transformar OKRs em listas de tarefas. Objective descreve transformação desejada. Key Result descreve mudança mensurável.

## Camada 3 — 4DX

O sistema deverá permitir: **1 MCI principal e, excepcionalmente, uma segunda MCI.**

A MCI NÃO deverá ser redefinida toda semana. Ela deverá permanecer válida durante um horizonte suficientemente longo para produzir aprendizagem e execução consistente.

Exemplo:

> Aumentar o faturamento semanal médio do perpétuo de R$ 20 mil para R$ 60 mil até 30/11/2026.

O acompanhamento, entretanto, será semanal. Portanto: **MCI = horizonte estratégico/tático.** **Placar 4DX = acompanhamento semanal.**

O material-base enfatiza exatamente essa relação entre MCI, medidas de resultado e medidas de direção.

## Camada 4 — Growth

Horizonte: **contínuo.**

O Growth Engine identifica: gargalos; oportunidades; hipóteses; experimentos; aprendizados.

## Camada 5 — Sprint

Horizonte: **7 dias.**

Cada Sprint deve possuir: objetivo; gargalo prioritário; Lead Measure prioritária; experimentos; compromissos; tarefas; resultado; retrospectiva.

O documento-base coloca a Sprint semanal como unidade operacional do perpétuo.

---

# 3. REGRA MAIS IMPORTANTE DO SISTEMA

## Uma Sprint não começa pelas tarefas. Ela começa pelos dados.

Fluxo obrigatório: **Dados** → **Diagnóstico** → **Gargalo** → **Hipótese** → **Experimento** → **Tarefa.**

Nunca: **"O que vamos fazer esta semana?"**

Antes perguntar:

> "Qual é atualmente a maior restrição ao crescimento?"

---

# 4. NOVA CÉLULA DA ARQUITETURA MESHCRAFT

Criar preferencialmente uma célula independente chamada: `scale_os` ou `growth_os`

Não espalhar essa lógica por catálogo, checkout, alunos, leads etc.

As demais células continuarão sendo sistemas de execução do negócio.

A nova célula será responsável por: gestão estratégica; OKRs; MCI; Lead Measures; placar; Sprints; experimentos; decisões; tarefas estratégicas; coordenação de agentes; aprendizado operacional.

---

# 5. PRINCÍPIO DE OWNERSHIP DOS DADOS

A célula `scale_os` deve ser dona de seus próprios dados.

Não tornar arquivos Git do painel a fonte primária desses dados.

Para esse módulo: **Source of Truth = banco de dados da célula.**

O painel existente poderá consumir: endpoints JSON; snapshots; APIs read-only; eventos derivados.

Git deverá continuar sendo utilizado para: código; configuração; contratos; documentação; e NÃO como banco operacional de tarefas, métricas e execução concorrente.

Isso reduz drasticamente problemas de: conflito; concorrência; lock; merge; atualização simultânea por agentes.

---

# 6. ENTIDADES DE DOMÍNIO

Criar, no mínimo, as seguintes entidades.

## StrategicCycle

Representa trimestre/ciclo estratégico.

Campos mínimos: `id`, `name`, `start_date`, `end_date`, `status`, `vision`, `strategic_thesis`, `created_at`, `updated_at`

Status: draft, active, closed, archived

---

# 7. OBJECTIVE

Campos: `id`, `strategic_cycle_id`, `title`, `description`, `owner`, `priority`, `status`, `confidence`, `created_at`, `updated_at`

---

# 8. KEY RESULT

Campos: `id`, `objective_id`, `title`, `metric`, `baseline`, `target`, `current_value`, `unit`, `direction`, `deadline`, `data_source`, `owner`, `status`

Direction: increase, decrease, maintain

O progresso deverá ser calculado automaticamente sempre que possível.

---

# 9. MCI / WIG

Criar entidade própria: `WildlyImportantGoal`

Campos: `id`, `strategic_cycle_id`, `objective_id`, `key_result_id`, `title`, `baseline`, `target`, `current_value`, `deadline`, `unit`, `owner`, `status`

A interface deverá mostrar:

> **De X para Y até DATA.**

Exemplo:

> De R$ 20.000/semana para R$ 60.000/semana até 30/11.

---

# 10. LEAD MEASURE

Campos: `id`, `wig_id`, `name`, `description`, `target`, `actual`, `unit`, `frequency`, `owner`, `controllable`, `predictive`, `status`

Toda Lead Measure deve responder positivamente a duas perguntas:

### Ela é influenciável?
A equipe consegue agir sobre ela?

### Ela é preditiva?
Existe boa razão para acreditar que sua melhoria tende a produzir movimento na MCI?

Se a resposta for não, provavelmente é uma Lag Measure disfarçada.

---

# 11. LAG MEASURE

Registrar separadamente métricas de resultado.

Exemplos: faturamento; vendas; CPA; lucro; ROAS; conversão; churn.

O sistema deverá diferenciar visualmente: **LEAD** de **LAG.**

Essa distinção não pode desaparecer na interface.

---

# 12. SCORECARD 4DX

Implementar placar semanal altamente visual.

O documento original pede que a equipe consiga perceber rapidamente se está ganhando ou perdendo, comparando metas e resultados das principais medidas.

Cada linha deverá mostrar: `Indicador | Meta | Realizado | Progresso | Tendência | Status`

Exemplo:

| Indicador | Meta | Atual | Situação |
| --- | ---: | ---: | --- |
| Receita | 40k | 31k | abaixo |
| Criativos testados | 7 | 8 | acima |
| Checkout recuperado | 90% | 72% | abaixo |
| Conversão VSL | 2,5% | 2,8% | acima |

O placar deverá responder em menos de cinco segundos:

> **Estamos ganhando ou perdendo?**

---

# 13. STATUS VISUAL

Criar sistema configurável. Default sugerido:

### Verde
Dentro ou acima da trajetória necessária.
### Amarelo
Risco de não atingir.
### Vermelho
Fora da trajetória.
### Cinza
Sem dados suficientes.
### Azul
Ainda em execução.

Esses thresholds NÃO devem ser hardcoded. Criar configuração administrativa.

---

# 14. FUNIL DE CRESCIMENTO

Criar representação do funil usando AARRR adaptado ao negócio.

O documento-base utiliza: Acquisition; Activation; Retention; Revenue; Referral.

Para a Meshcraft, adicionar uma camada operacional mais detalhada.

### Acquisition
impressões; alcance; CPM; CTR; CPC; visitas; CPL; leads.
### Activation
cadastro; entrada Lista VIP; play da VSL; retenção da VSL; participação em evento; clique CTA.
### Conversion
Embora não faça parte do acrônimo AARRR original, deverá aparecer como estágio explícito operacional: checkout iniciado; checkout aprovado; taxa checkout→compra; conversão da página; conversão por canal.
### Revenue
vendas; receita; AOV; CPA; CAC; ROAS; margem; receita recuperada.
### Retention
acesso; ativação do aluno; conclusão; engajamento; reembolso; churn, quando aplicável.
### Referral
indicação; afiliados; UGC; depoimentos; referrals.

---

# 15. FUNNEL NODE

Não programar todas as métricas diretamente na interface.

Criar modelo abstrato: `MetricDefinition` com: slug, label, category, formula, source, unit, aggregation, frequency

E: `MetricSnapshot` com: metric_id, timestamp, value, dimensions, source, confidence

Isso permitirá acrescentar novas métricas sem reconstruir o sistema.

---

# 16. CAMADA DE DIMENSÕES

As métricas devem futuramente permitir análise por: campanha; conjunto; anúncio; criativo; canal; origem; produto; oferta; landing page; dispositivo; coorte; período.

Evitar desde agora um schema que impeça segmentação futura.

---

# 17. GROWTH BOTTLENECK

Criar entidade: `GrowthBottleneck`

Campos: `id`, `strategic_cycle_id`, `funnel_stage`, `metric`, `description`, `evidence`, `severity`, `estimated_impact`, `confidence`, `status`, `detected_by`, `created_at`

Status: suspected, validated, active, resolved, rejected

---

# 18. O MOTOR DE GARGALOS

O sistema deverá procurar responder:

> Se pudéssemos melhorar apenas UMA coisa nesta semana, qual provavelmente produziria maior impacto?

Exemplo: Aquisição boa. CPL bom. Retenção VSL boa. Checkout alto. Compra baixa.

Então: **o gargalo não é aquisição.**

O sistema deverá investigar: **checkout → pagamento → recuperação → objeções → erro técnico.**

---

# 19. NÃO CONFUNDIR CORRELAÇÃO COM CAUSALIDADE

IA pode identificar padrões. IA não poderá declarar causalidade automaticamente.

Portanto toda conclusão deverá ter: `confidence` e `evidence_level`

Valores possíveis: observed, correlated, plausible, experimentally_supported, causal_evidence

---

# 20. HYPOTHESIS

Criar entidade: `GrowthHypothesis`

Formato:

> Se fizermos X para público Y, esperamos mudar Z porque acreditamos em M.

Campos: hypothesis, mechanism, target_metric, expected_effect, evidence, confidence, cost, effort, risk

---

# 21. EXPERIMENT

Criar entidade: `Experiment`

Campos: id, hypothesis_id, name, owner, metric_primary, metrics_secondary, baseline, expected_result, start_date, end_date, sample_requirement, implementation, status, result, interpretation, decision

Status: proposed, approved, scheduled, running, analyzing, winner, loser, inconclusive, stopped

---

# 22. REGISTRO DE APRENDIZADO

Todo experimento concluído deverá gerar: `Learning`

Estrutura:

### Hipótese
O que acreditávamos.
### Evidência
O que observamos.
### Resultado
O que aconteceu.
### Interpretação
O que provavelmente significa.
### Decisão
escalar; repetir; modificar; abandonar; investigar.
### Confidence
0–100%.

---

# 23. EXPERIMENT LIBRARY

Criar uma biblioteca pesquisável de experimentos.

Isso impedirá que agentes repitam testes já realizados simplesmente porque não conhecem o histórico.

Busca por: métrica; página; oferta; criativo; hipótese; resultado; período.

---

# 24. SPRINT

Criar entidade: `Sprint`

Campos: `id`, `number`, `start_date`, `end_date`, `goal`, `primary_bottleneck`, `primary_lead_measure`, `status`, `owner`, `review`, `retrospective`

Status: planning, active, review, closed

---

# 25. REGRA DA SPRINT

Cada Sprint deverá ter: ### ONE PRIMARY CONSTRAINT — um gargalo primário.

Podem existir tarefas operacionais paralelas. Mas o esforço estratégico deverá ficar concentrado.

O documento-base já aponta a importância de não tentar melhorar tudo simultaneamente e concentrar a pequena equipe em um foco central.

---

# 26. KANBAN

Colunas padrão:

### Backlog
Ideias e trabalho ainda não priorizado.
### Ready
Tarefa pronta para execução.
### In Progress
Em execução.
### Review
Aguardando revisão.
### Revisão / Exceção
Necessita decisão humana ou correção.
### Blocked
Impedimento externo.
### Done
Concluído e validado.
### Cancelled
Descartado.

---

# 27. TASK

O Task deverá ter schema suficiente para humanos e agentes. Exemplo conceitual:

```json
{
  "id": "TASK-2026-00481",
  "title": "Implementar teste da nova headline da VSL",
  "type": "experiment",
  "status": "ready",
  "priority": "high",
  "strategic_cycle": "2026-Q4",
  "objective_id": "OBJ-01",
  "key_result_id": "KR-02",
  "wig_id": "WIG-01",
  "lead_measure_id": "LM-03",
  "sprint_id": "SPRINT-41",
  "experiment_id": "EXP-019",
  "owner_type": "ai_agent",
  "owner": null,
  "dependencies": [],
  "blocked_by": [],
  "parallelizable": true,
  "batchable": false,
  "execution_contract": {
    "objective": "Publicar variante B da headline",
    "scope": [],
    "out_of_scope": [],
    "acceptance_criteria": [],
    "tests_required": [],
    "evidence_required": []
  },
  "lease": null,
  "created_at": "...",
  "updated_at": "..."
}
```

---

# 28. EXECUTION CONTRACT

Nenhum agente deverá executar um card complexo baseado apenas no título.

Todo card executável deverá possuir um: **Execution Contract.**

Contendo:

### Objetivo
O resultado esperado.
### Contexto
Por que isso existe.
### Escopo
O que pode ser alterado.
### Fora do escopo
O que NÃO pode ser alterado.
### Arquivos permitidos
Quando aplicável.
### Dependências
O que precisa existir antes.
### Acceptance Criteria
Como saber que terminou.
### Testes
O que precisa passar.
### Evidências
O agente deve apresentar provas.
### Rollback
Como desfazer.

---

# 29. LOCK PARA AGENTES

Ao pegar uma tarefa: o agente deverá solicitar um `lease`

```json
{
  "task_id": "TASK-481",
  "agent_id": "agent-backend-03",
  "acquired_at": "...",
  "expires_at": "...",
  "heartbeat_at": "..."
}
```

Enquanto o lease estiver ativo: outro agente não poderá assumir a mesma tarefa.

Se o agente desaparecer: o lease expira. A tarefa volta para `ready` ou `review_exception` conforme o estado encontrado.

---

# 30. IDEMPOTÊNCIA

Toda operação automatizada relevante deverá ser idempotente.

Executar duas vezes não pode: duplicar registros; duplicar pagamentos; duplicar métricas; duplicar tarefas; duplicar eventos.

Usar `idempotency_key` quando necessário.

---

# 31. AGENT RUN

Registrar toda execução automatizada. Entidade: `AgentRun`

Campos: agent, task, started_at, finished_at, status, input, output, changed_files, tests, evidence, token_usage (quando disponível), errors, rollback_status

---

# 32. AUDIT LOG

Toda alteração importante deverá gerar evento append-only: `AuditEvent`

Contendo: actor, actor_type, timestamp, entity, entity_id, action, previous_state, new_state, reason, correlation_id

Nunca depender apenas de `updated_at`.

Precisamos conseguir reconstruir:

> Quem mudou o quê, quando e por quê?

---

# 33. DECISION LOG

Criar entidade: `Decision`

Exemplo:

> Decidimos não aumentar orçamento do Meta esta semana porque o gargalo está em checkout→purchase, não aquisição.

Registrar: contexto; alternativas; decisão; racional; evidências; autor; data; revisão futura.

Isso é especialmente importante em sistemas operados por agentes de IA.

---

# 34. TELA PRINCIPAL

Criar: `/scale-os/` ou equivalente conforme padrão arquitetural encontrado no repositório.

A tela inicial deve priorizar decisão, não informação. Ordem recomendada:

## 1. Estamos ganhando?
Grande indicador: **ON TRACK / AT RISK / OFF TRACK**
## 2. MCI
Exemplo: **R$ 37.400 / R$ 45.000**. Trajetória necessária.
## 3. Lead Measures
Mostrar as 3–5 principais.
## 4. Gargalo atual
Exemplo: **Checkout → Purchase**
## 5. Sprint atual
Mostrar: objetivo; progresso; tarefas; experimentos.
## 6. Alertas
Somente exceções relevantes.

---

# 35. TELAS DO SISTEMA

Criar inicialmente:

`/scale-os/` cockpit executivo · `/scale-os/strategy/` estratégia + OKRs · `/scale-os/4dx/` MCI + Lead Measures + placar · `/scale-os/growth/` funil + gargalos · `/scale-os/experiments/` experimentos · `/scale-os/sprints/` sprints · `/scale-os/tasks/` Kanban · `/scale-os/learnings/` base de aprendizagem · `/scale-os/decisions/` Decision Log · `/scale-os/agents/` execuções dos agentes · `/scale-os/audit/` auditoria.

---

# 36. SEMANA OPERACIONAL

## Segunda-feira — Weekly Command

O sistema prepara automaticamente, da semana anterior: MCI; Lead Measures; principais Lag Measures; resultados; experimentos; tarefas; incidentes.

Depois IA produz o **Weekly Diagnostic**, respondendo:

1. O que aconteceu?
2. Onde melhoramos?
3. Onde pioramos?
4. Qual maior gargalo?
5. O que provavelmente explica o resultado?
6. Que evidências temos?
7. Que hipóteses devemos testar?
8. Qual deveria ser o foco desta Sprint?

Humano aprova ou altera.

---

# 37. DURANTE A SEMANA

Atualizar continuamente: métricas; tarefas; Lead Measures; experimentos; incidentes.

Agentes podem detectar: desvio; anomalia; bloqueio; regressão.

Mas não devem alterar automaticamente estratégia de alto nível sem autorização quando a mudança possuir impacto material.

---

# 38. SEXTA-FEIRA — SPRINT REVIEW

Gerar automaticamente:

## Score
Ganhamos ou perdemos?
## Lead Measures
Executamos o que controlávamos?
## Lag Measures
Os resultados responderam?
## Experimentos
O que aprendemos?
## Trabalho
O que terminou?
## Bloqueios
O que impediu progresso?
## Decisões
O que muda na próxima semana?

O documento-base liga a revisão semanal às métricas e à identificação de gargalos.

---

# 39. RETROSPECTIVA

Responder:

### START
O que devemos começar?
### STOP
O que devemos parar?
### CONTINUE
O que devemos continuar?
### DOUBLE DOWN
O que apresentou resultado forte suficiente para receber mais recursos?

---

# 40. CADÊNCIA 4DX

O sistema deverá suportar compromissos semanais. Entidade: `Commitment`

Exemplo:

> Publicar e testar sete novos criativos até quinta-feira.

Campos: person/agent; Lead Measure; commitment; deadline; status; evidence.

Na próxima reunião:

> Fizemos o que prometemos?

Isso preserva a disciplina de accountability prevista pelo modelo 4DX.

---

# 41. MCI E META SEMANAL

A interface deverá evitar o erro conceitual de recriar uma MCI diferente toda semana.

Exemplo. MCI trimestral:

> Aumentar receita semanal média de R$ 20k para R$ 60k.

Trajetória: Semana 1: 24k · Semana 2: 27k · Semana 3: 31k · ... · Semana 12: 60k

Portanto mostrar: ### Target final 60k. ### Target desta semana 31k. ### Atual 29k.

Isso permite velocidade semanal sem destruir continuidade estratégica.

---

# 42. AI STRATEGIST

Criar agente lógico: `StrategistAgent`

Responsabilidades: analisar scorecard; encontrar gargalos; produzir hipóteses; sugerir prioridades; apontar anomalias; questionar explicações prematuras.

Ele NÃO executa alterações de produção diretamente.

---

# 43. AI GROWTH ANALYST

Responsável por: funil; coortes; anomalias; tendências; comparações; estatística; avaliação de experimentos.

Deverá distinguir: observação; correlação; hipótese; evidência experimental.

---

# 44. AI SPRINT PLANNER

Transforma **gargalo + hipóteses + experimento** em: Sprint; tarefas; dependências; lotes; execução paralela; critérios de aceite.

---

# 45. AI TASK ORCHESTRATOR

Responsável por: identificar tarefas disponíveis; verificar dependências; atribuir tarefas; adquirir lease; acompanhar heartbeat; mover estados; detectar bloqueios.

---

# 46. AI IMPLEMENTATION AGENTS

Agentes especializados: backend; frontend; analytics; copy; tráfego; automação; QA; DevOps.

Não criar um agente universal para tudo quando a tarefa possuir especialização clara.

---

# 47. AI REVIEWER

Nenhum agente deve, como regra geral, ser o único avaliador da própria tarefa de risco relevante.

Workflow ideal: **Implementation Agent** ↓ **tests** ↓ **Reviewer Agent** ↓ **human exception only when necessary**

---

# 48. AI RED TEAM

Criar papel específico para questionar decisões de maior impacto. Perguntas:

> Que outra explicação existe?
> Estamos tratando correlação como causalidade?
> O problema pode estar no tracking?
> A amostra é suficiente?
> Houve mudança simultânea?
> Há variável confundidora?
> Estamos escalando um falso positivo?

---

# 49. HUMAN-IN-THE-LOOP

Exigir aprovação humana para: mudança de MCI; mudança de OKR; aumento material de orçamento; alteração de preço; publicação de oferta; alteração de pagamento; mudança de política; deleção de dados; migrations destrutivas; rollback de produção; ação jurídica/compliance; alterações de alta irreversibilidade.

---

# 50. REVISÃO / EXCEÇÃO

Toda exceção deverá dizer claramente:

### O que aconteceu?
### Por que o robô parou?
### O que ele tentou?
### Que evidências coletou?
### Qual decisão humana precisa?
### Opções disponíveis
Aprovar. Corrigir. Reexecutar. Reatribuir. Cancelar.

Nunca mostrar apenas:

> "Erro."

---

# 51. EVIDENCE-FIRST COMPLETION

Um agente não poderá dizer apenas:

> "Concluído."

Ele deverá entregar evidências. Exemplo: arquivos alterados; diff; testes executados; resultado; screenshot quando aplicável; endpoint; logs; comparação before/after.

Status `done` somente depois do acceptance gate.

---

# 52. DATA INGESTION

Implementar adapters. Versão inicial poderá aceitar: ### Manual Entry — para começar rápido. Depois: ### Import CSV. Depois: ### APIs/webhooks.

Possíveis fontes futuras: Meta; Google; checkout; CRM; WhatsApp; e-mail; analytics; plataforma de alunos.

Não bloquear o MVP esperando todas as integrações.

---

# 53. DATA QUALITY

Cada métrica deverá possuir: source; freshness; completeness; confidence; last_updated.

Exemplo. **Receita** — Source: checkout · Freshness: 5 min · Confidence: HIGH. **Instagram attribution** — Source: self reported · Confidence: MEDIUM.

Isso impedirá o painel de transmitir falsa precisão.

---

# 54. DETECTOR DE ANOMALIAS

Criar arquitetura preparada para `AlertRule`. Exemplo:

> Checkout cai >30% vs média móvel.
> Pixel e backend divergem >10%.
> CPA sobe >25%.
> conversão cai abaixo de limite.
> erro 5xx aumenta.

O sistema deve primeiro gerar alerta. Não executar automaticamente ações perigosas.

---

# 55. ALERT FATIGUE

Não transformar todo desvio em alerta.

Alertas devem possuir: severity; confidence; business_impact; owner; resolution_status.

Classificação: INFO, WARNING, HIGH, CRITICAL

---

# 56. PAINEL EXISTENTE DA MESHCRAFT

Não reconstruir imediatamente o painel inteiro. Integrar incrementalmente.

O painel principal poderá receber uma nova aba: **ESCALA** ou **GROWTH OS**

Esta aba consome os dados read-only da nova célula. Para ações completas: linkar para `/scale-os/`.

Assim: ### Painel — visão executiva. ### Scale OS — operação profunda.

---

# 57. API

Criar namespace versionado: `/api/scale-os/v1/`

Recursos iniciais: strategic-cycles, objectives, key-results, wigs, lead-measures, metrics, scorecards, bottlenecks, hypotheses, experiments, sprints, tasks, commitments, learnings, decisions, agent-runs, alerts

---

# 58. CONCURRENCY

Toda atualização feita por agentes deverá tratar concorrência.

Usar conforme arquitetura encontrada: optimistic locking; version field; atomic transaction; lease; unique constraint.

Nunca assumir que apenas um agente estará operando.

---

# 59. EVENTOS

Preparar eventos internos como: `metric.updated`, `bottleneck.detected`, `experiment.started`, `experiment.completed`, `sprint.started`, `task.created`, `task.claimed`, `task.blocked`, `task.completed`, `lead_measure.off_track`, `wig.at_risk`

Isso permitirá automações futuras sem acoplamento forte.

---

# 60. SECURITY

Agentes devem operar segundo princípio de **least privilege.**

Um agente analítico não precisa escrever em produção. Um agente frontend não precisa acessar pagamentos. Um agente de copy não precisa acessar PII.

Nunca registrar: senha; secret; access token; dados desnecessários de clientes.

---

# 61. FEATURE FLAG

Implementar o módulo inicialmente atrás de feature flag. Exemplo: `SCALE_OS_ENABLED=true`

Permitir ativação progressiva.

---

# 62. FASE 0 — RECONHECIMENTO DO REPOSITÓRIO

Antes de escrever código, o primeiro agente deverá documentar: arquitetura real; apps/células; bancos; Docker; Traefik; autenticação; painel; design system; testes; CI; conventions; migrations; APIs existentes.

Regra:

> Não assumir arquitetura pelo playbook quando o repositório puder mostrar a realidade.

---

# 63. FASE 1 — ADR

Criar: `ADR — Scale OS Architecture`

Deve explicar: por que nova célula; fonte da verdade; integração com painel; autenticação; banco; APIs; isolamento; concorrência; auditoria.

Somente depois congelar contrato arquitetural.

---

# 64. FASE 2 — DOMAIN MODEL

Implementar primeiro: StrategicCycle; Objective; KeyResult; WIG; LeadMeasure; Sprint; Task; Experiment.

Depois: Learnings; Decisions; AgentRun; Audit; Alerts.

---

# 65. FASE 3 — API CONTRACT

Antes de UI e automações trabalharem em paralelo: congelar **API v1 Contract.**

A partir daí, em paralelo: ### Backend ### Frontend ### Agent Orchestrator ### Analytics

---

# 66. FASE 4 — MVP VISUAL

Construir somente: ### Cockpit ### OKR ### 4DX Scoreboard ### Sprint ### Kanban ### Experiment Board

Não construir vinte telas sofisticadas antes de validar o fluxo principal.

---

# 67. FASE 5 — WEEKLY LOOP

Implementar processo completo:

**Close Sprint** → **Snapshot metrics** → **Generate Weekly Review** → **Detect bottleneck** → **Propose experiments** → **Human approval** → **Generate Sprint** → **Generate tasks** → **Execute** → **Review**

Esse é o verdadeiro MVP do Scale OS. Não o dashboard.

---

# 68. FASE 6 — AGENT EXECUTION

Somente depois de Tasks + Execution Contract + Lock + Audit estarem confiáveis: habilitar agentes executores.

Não colocar agentes autônomos sobre infraestrutura sem contratos e trilha de auditoria.

---

# 69. FASE 7 — AUTOMAÇÃO DE DADOS

Prioridade: 1. dados internos da Meshcraft; 2. checkout; 3. campanhas; 4. analytics; 5. CRM/WhatsApp; 6. outras integrações.

Não começar pelas integrações mais difíceis.

---

# 70. FASE 8 — INTELIGÊNCIA

Adicionar posteriormente: bottleneck ranking; anomaly detection; forecast; experiment recommender; causal analysis assistida; scenario simulator.

Nunca colocar "IA sofisticada" antes de dados confiáveis.

---

# 71. PRIORIDADE MATEMÁTICA

Criar score configurável para hipóteses. Exemplo: `Priority = Impact × Confidence ÷ Effort` ou ICE/RICE.

Mas não tratar o score como decisão automática. Ele serve como **decision support.**

---

# 72. FORECAST

Preparar arquitetura para mostrar: ### Se mantivermos trajetória atual: resultado estimado. ### Se melhorarmos Lead Measure X: cenário estimado. ### Se aumentarmos tráfego sem melhorar conversão: impacto esperado.

Sempre marcar: **projection**, não fato.

---

# 73. META-INFORMAÇÃO

Toda recomendação de IA deverá preferencialmente informar: ### Recomendação ### Evidência ### Confiança ### Impacto esperado ### Risco ### Próxima ação

---

# 74. CRITÉRIO DE SUCESSO DO SISTEMA

Não medir sucesso pelo número de funcionalidades. Medir por:

### Decision Latency
Tempo entre problema → diagnóstico → decisão.
### Execution Latency
Tempo entre decisão → implementação.
### Learning Velocity
Quantos aprendizados úteis produzimos por período.
### Experiment Throughput
Experimentos concluídos.
### Lead Measure Compliance
Execução das ações controláveis.
### MCI Progress
Resultado estratégico.

---

# 75. PRINCÍPIO DE VELOCIDADE DE APRENDIZAGEM

A meta maior do sistema não é simplesmente "fazer mais tarefas". É "aumentar a velocidade com que a Meshcraft descobre o que realmente produz crescimento".

Portanto: **Tasks ≠ Progress** e **Experiments ≠ Learning**

Um teste só gera aprendizagem quando: foi bem definido; teve dados suficientes; foi interpretado; produziu decisão.

---

# 76. REGRAS PARA OS AGENTES

Todos os agentes deverão seguir:

1. **Inspect before change** — leia o sistema antes de modificar.
2. **Contract before implementation** — não invente contratos silenciosamente.
3. **Smallest safe change** — faça a menor mudança que resolva corretamente o problema.
4. **Preserve backward compatibility** — exceto quando explicitamente autorizado.
5. **Tests before done** — sem teste, não declarar finalização.
6. **Evidence before done** — sem evidência, não declarar finalização.
7. **No silent architecture changes** — mudança arquitetural exige ADR.
8. **No destructive migration without approval** — obrigatório.
9. **No secret exposure** — obrigatório.
10. **Fail closed** — diante de ambiguidade crítica, não executar ação perigosa.

---

# 77. DEFINITION OF READY

Uma tarefa está pronta quando possui: contexto suficiente; objetivo claro; acceptance criteria; dependências resolvidas; scope definido; acesso necessário; risco conhecido.

Caso contrário: `needs_definition`

---

# 78. DEFINITION OF DONE

Uma tarefa só está Done quando: código implementado; lint passou; testes passaram; regressões relevantes testadas; acceptance criteria atendidos; documentação atualizada quando necessário; observabilidade adicionada quando necessária; evidências registradas; reviewer aprovou; audit event criado.

---

# 79. QUALIDADE DO CÓDIGO

Não sacrificar arquitetura por velocidade artificial.

Exigir: typing quando apropriado; nomes claros; funções pequenas; separation of concerns; transações; constraints; validação; testes; logs estruturados.

Evitar abstração excessiva sem necessidade.

---

# 80. TESTES MÍNIMOS

## Unit
Regras de domínio.
## Integration
Banco + API.
## Permission
Acesso.
## State Machine
Transições.
## Concurrency
Locks.
## E2E
Fluxo principal.
## Regression
Funcionalidades existentes afetadas.

---

# 81. TESTE CRÍTICO DO WEEKLY LOOP

Criar cenário automatizado:

1. ciclo estratégico ativo;
2. MCI ativa;
3. três Lead Measures;
4. métricas registradas;
5. gargalo detectado;
6. hipótese criada;
7. experimento aprovado;
8. Sprint aberta;
9. tarefas geradas;
10. agente pega card;
11. lease criado;
12. tarefa executada;
13. reviewer aprova;
14. Sprint encerrada;
15. aprendizado registrado;
16. placar atualizado.

Esse será um dos testes de integração mais importantes.

---

# 82. NÃO FAZER NO MVP

Não construir inicialmente: machine learning próprio; previsão financeira sofisticada; otimização automática de orçamento; dezenas de integrações; sistema completo de BI; agente autônomo capaz de alterar tudo; visualizações 3D; gamificação da equipe; microserviços desnecessários.

Primeiro provar o loop: **Measure → Decide → Execute → Learn.**

---

# 83. PRIMEIRO MILESTONE

## SCALE OS FOUNDATION

Pronto quando existirem: célula; banco; autenticação; StrategicCycle; Objective; KR; MCI; LeadMeasure; Sprint; Task; API; Audit Log.

---

# 84. SEGUNDO MILESTONE

## EXECUTION ENGINE

Adicionar: Kanban; Execution Contract; dependências; locks; agent runs; review; exceptions.

---

# 85. TERCEIRO MILESTONE

## GROWTH ENGINE

Adicionar: métricas; funil; gargalos; hipóteses; experimentos; learnings.

---

# 86. QUARTO MILESTONE

## WEEKLY INTELLIGENCE

Adicionar: Weekly Review; Sprint Planning assistido; bottleneck suggestions; Red Team; recomendações.

---

# 87. QUINTO MILESTONE

## AUTONOMOUS EXECUTION

Somente então permitir maior autonomia dos agentes. Autonomia deverá possuir níveis.

### LEVEL 0 — Observe
Somente leitura.
### LEVEL 1 — Recommend
Recomenda.
### LEVEL 2 — Draft
Cria tarefa/configuração, mas requer aprovação.
### LEVEL 3 — Execute reversible
Executa ações reversíveis dentro de limites.
### LEVEL 4 — Execute bounded
Executa autonomamente sob políticas explícitas.
### LEVEL 5 — Full autonomy
Não habilitar por padrão.

---

# 88. COMMAND CENTER

Quando amadurecer, a página principal deverá funcionar como **MESHCRAFT COMMAND CENTER**, mostrando:

### NORTH STAR
Para onde estamos indo?
### MCI
Estamos chegando?
### LEAD MEASURES
Estamos fazendo o que deveria nos levar até lá?
### CONSTRAINT
O que mais limita crescimento?
### EXPERIMENT
O que estamos aprendendo?
### SPRINT
O que estamos executando?
### AGENTS
Quem está trabalhando em quê?
### EXCEPTIONS
Onde Anderson precisa decidir?

---

# 89. UX PARA O DONO

A interface deverá ser projetada para que uma pessoa não técnica consiga administrar uma operação tecnicamente sofisticada.

Não mostrar inicialmente: IDs internos; payloads; traces; JSON; nomes técnicos.

Mostrar:

> "Precisamos de você."
> "O checkout caiu 18%."
> "O agente encontrou duas possíveis causas."
> "Recomendação: investigar erro no PIX primeiro."

E oferecer **Ver detalhes técnicos** para drill-down.

---

# 90. PRINCÍPIO DA COMPRESSÃO GERENCIAL

O sistema deve transformar centenas ou milhares de eventos operacionais em poucas decisões humanas de alto valor.

O objetivo não é fazer Anderson acompanhar mais coisas. É fazer com que ele precise acompanhar **menos coisas, porém as certas**.

---

# 91. PROMPT-MÃE PARA CADA AGENTE

Ao receber uma tarefa, o agente deverá receber automaticamente algo semelhante a:

> Você está atuando como agente de implementação da plataforma Meshcraft.
>
> Sua responsabilidade é executar exclusivamente a tarefa descrita abaixo.
>
> Antes de alterar qualquer coisa: 1. inspecione o código afetado; 2. identifique contratos existentes; 3. identifique testes relacionados; 4. identifique risco de regressão; 5. confirme dependências.
>
> Não faça refatorações não solicitadas. Não altere arquitetura silenciosamente. Não altere contratos públicos sem necessidade. Não execute operação destrutiva. Não exponha secrets.
>
> Utilize a menor mudança segura capaz de atender ao objetivo.
>
> Ao terminar: 1. execute os testes apropriados; 2. apresente arquivos alterados; 3. apresente testes executados; 4. apresente evidências; 5. relate qualquer risco residual; 6. atualize o status da tarefa conforme o contrato.
>
> Se houver impedimento real que exija decisão humana, mova a tarefa para Revisão/Exceção e explique precisamente a decisão necessária.
>
> TASK: {{task}} · EXECUTION CONTRACT: {{execution_contract}} · DEPENDENCIES: {{dependencies}} · ARCHITECTURAL RULES: {{architecture_contract}}

---

# 92. ORDEM DE IMPLEMENTAÇÃO OBRIGATÓRIA

### LOTE A — Descoberta
A1. Mapear arquitetura atual. A2. Mapear autenticação. A3. Mapear painel. A4. Mapear bancos. A5. Mapear CI/testes. Podem ocorrer parcialmente em paralelo.

### LOTE B — Contratos
B1. ADR. B2. Domain Model. B3. State Machines. B4. API Contract. B5. Permission Model. Congelar antes de grande paralelização.

### LOTE C — Foundation
C1. Criar célula. C2. Models. C3. Migrations. C4. Services. C5. API. C6. Audit.

### LOTE D — UI
D1. Layout. D2. Cockpit. D3. OKRs. D4. 4DX. D5. Sprint. D6. Kanban. Pode ocorrer paralelamente ao backend depois do contrato da API.

### LOTE E — Growth
E1. MetricDefinitions. E2. MetricSnapshots. E3. Funnel. E4. Bottleneck. E5. Hypothesis. E6. Experiment. E7. Learning.

### LOTE F — Agent Engine
F1. Execution Contract. F2. Leasing. F3. Agent Runs. F4. Review. F5. Exception workflow.

### LOTE G — Weekly Loop
G1. Weekly snapshot. G2. Weekly review. G3. Sprint close. G4. Sprint planning. G5. Commitment engine.

### LOTE H — Integração
H1. Aba Scale no painel. H2. API read-only. H3. Alertas. H4. Sininho.

### LOTE I — QA
I1. Unit. I2. Integration. I3. E2E. I4. Concurrency. I5. Security. I6. Regression.

### LOTE J — Rollout
J1. Feature flag. J2. Staging. J3. Seed demo. J4. Teste humano. J5. Production rollout.

---

# 93. DEPENDÊNCIAS ENTRE LOTES

Fluxo: **A** ↓ **B** ↓ **C**

Depois de B: **C + D preparatório + E preparatório** podem ocorrer em paralelo.

Depois de C: **D + E + F** podem avançar fortemente em paralelo.

Depois: **G**. Depois: **H + I**. Finalmente: **J**.

---

# 94. REGRA DE MERGE

Não deixar vários agentes modificarem simultaneamente grandes arquivos derivados compartilhados.

Preferir: arquivos pequenos; componentes separados; modules; additive migrations; contratos estáveis; integração final controlada.

Arquivos gerados devem preferencialmente ser reconstruíveis deterministicamente.

---

# 95. DOCUMENTAÇÃO GERADA

Ao terminar, manter documentação em `docs/scale-os/` com: README.md, ARCHITECTURE.md, DOMAIN-MODEL.md, API.md, STATE-MACHINES.md, AGENT-PROTOCOL.md, WEEKLY-LOOP.md, OPERATIONS.md, RUNBOOK.md, ADR/

---

# 96. SEED DE DEMONSTRAÇÃO

Criar dados fake capazes de mostrar:

### Objective
Escalar o perpétuo.
### KR
Aumentar faturamento.
### MCI
20k → 60k.
### Lead Measure
7 novos criativos/semana.
### Gargalo
Checkout→Purchase.
### Experimento
Nova recuperação WhatsApp.
### Sprint
Melhorar recuperação.
### Tasks
3–5 cards.

Isso permitirá validar UX antes de ligar dados reais.

---

# 97. TESTE DO PRINCÍPIO CENTRAL

Antes de considerar o sistema pronto, selecionar qualquer tarefa do Kanban.

Devemos conseguir navegar: **TASK** → Sprint → Experiment → Hypothesis → Bottleneck → Lead Measure → MCI → Key Result → Objective.

E também fazer o caminho contrário.

Se isso não for possível: o sistema virou novamente um conjunto de ferramentas desconectadas.

---

# 98. RESULTADO FINAL ESPERADO

Depois da implementação, a Meshcraft deverá possuir três cérebros integrados:

## SYSTEM OBSERVABILITY
> O que está acontecendo? — Painel atual.
## BUSINESS OBSERVABILITY
> Como o negócio está performando? — Scale OS Metrics.
## EXECUTION INTELLIGENCE
> O que devemos fazer agora para melhorar? — Growth Execution Engine.

---

# 99. O LOOP 10X

A versão madura deverá operar continuamente:

**OBSERVAR** ↓ **MEDIR** ↓ **DIAGNOSTICAR** ↓ **PRIORIZAR** ↓ **FORMULAR HIPÓTESE** ↓ **TESTAR** ↓ **EXECUTAR** ↓ **VALIDAR** ↓ **APRENDER** ↓ **PADRONIZAR OU DESCARTAR** ↓ **ESCALAR** ↓ **OBSERVAR NOVAMENTE**

---

# 100. NORTH STAR ARQUITETURAL

O sucesso deste projeto não será "Temos OKR no site", nem "Temos Scrum no site", nem "Temos um Kanban", nem "Temos IA".

O objetivo é criar uma infraestrutura na qual:

**a estratégia gera execução, a execução gera dados, os dados geram aprendizado, o aprendizado modifica a estratégia, e humanos e agentes de IA conseguem percorrer esse ciclo cada vez mais rapidamente.**

Esse é o **Meshcraft Scale OS — Growth Execution Engine**.
