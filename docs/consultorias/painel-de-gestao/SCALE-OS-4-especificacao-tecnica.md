# Documento 4: MESHCRAFT SCALE OS 1.2, ESPECIFICAÇÃO TÉCNICA DO PAINEL

> Texto de IA externa, colado pelo mantenedor em 03/09/2026 nesta sessão, como o quarto e último documento da proposta nova do painel de gestão. Guardado sem edição.

# MESHCRAFT SCALE OS 1.2
# ESPECIFICAÇÃO TÉCNICA DO PAINEL
## Documento de arquitetura técnica, contratos de dados, APIs, componentes, permissões e integração para implementação do Meshcraft Command & Learning System
---
# 0. PROPÓSITO DESTE DOCUMENTO
A versão 1.1 definiu **o que o painel precisa mostrar e quais decisões ele precisa suportar**.
A versão 1.2 define:
> **como esse painel deve ser construído tecnicamente.**
Este documento deve servir como especificação-base para:
* Claude Code;
* agentes de desenvolvimento;
* arquitetura Django;
* frontend;
* analytics;
* Revenue Brain;
* robôs operacionais;
* QA;
* observabilidade;
* evolução futura do M-ROS.
O objetivo não é construir um BI isolado.
O objetivo é construir uma aplicação operacional capaz de ligar:
```text
EVENTOS
↓
MÉTRICAS
↓
DIAGNÓSTICO
↓
INSIGHTS
↓
DECISÕES
↓
TAREFAS
↓
EXECUÇÃO
↓
VALIDAÇÃO
↓
APRENDIZADO
```
---
# PARTE I — PRINCÍPIOS DE ARQUITETURA
# 1. O PAINEL NÃO É A FONTE PRIMÁRIA DOS FATOS
O painel deve ser:
> **uma camada de leitura, decisão e comando.**
Não deve se tornar dono de todos os dados da empresa.
As células continuam donas de seus respectivos domínios.
Exemplo:
```text
checkout
→ pedidos e pagamentos
alunos
→ matrículas, progresso, competências
leads
→ leads e relacionamento
funil
→ páginas e experiências públicas
revenue
→ consolidação econômica
automation
→ workflows e ações
painel
→ observabilidade, decisão e operação
```
---
# 2. PRINCÍPIO DE DOMAIN OWNERSHIP
Cada fato possui uma autoridade.
| Informação          | Source of Truth       |
| ------------------- | --------------------- |
| pedido              | checkout              |
| pagamento           | checkout/gateway      |
| matrícula           | alunos                |
| progresso           | alunos                |
| lead                | leads                 |
| campanha            | acquisition/analytics |
| tarefa              | task engine           |
| experimento         | experiment engine     |
| decisão             | decision memory       |
| métrica consolidada | revenue/analytics     |
| painel              | somente representação |
O painel pode armazenar:
* preferências;
* snapshots;
* caches;
* layouts;
* filtros salvos;
* decisões;
* tarefas;
* insights;
mas não deve duplicar arbitrariamente dados de domínio.
---
# 3. EVENT-FIRST
A integração entre células deve favorecer eventos.
Exemplo:
```json
{
  "event_name": "purchase_completed",
  "event_id": "evt_01...",
  "producer": "checkout",
  "schema_version": 1,
  "occurred_at": "2026-09-03T19:10:31-03:00",
  "customer_id": "cus_01...",
  "properties": {
    "order_id": "ord_01...",
    "offer_id": "off_core_1497",
    "gross_value": 1497.00,
    "currency": "BRL"
  }
}
```
O painel não deveria precisar consultar dez bancos diferentes em tempo real para desenhar cada card.
Eventos alimentam projeções e métricas apropriadas.
---
# 4. CQRS LEVE
Recomendação arquitetural:
usar conceitualmente uma separação entre:
## WRITE MODEL
Onde eventos e decisões operacionais são gravados.
## READ MODEL
Estruturas otimizadas para leitura do painel.
Não precisa implementar CQRS acadêmico completo.
A ideia prática é:
```text
domínios
↓
eventos
↓
projeções
↓
read models
↓
painel
```
Isso reduz consultas extremamente caras e acoplamento.
---
# 5. READ MODELS
Exemplos:
```text
executive_health_snapshot
kpi_snapshot
okr_progress_snapshot
mci_snapshot
constraint_snapshot
cohort_snapshot
experiment_summary
robot_status_snapshot
task_summary
data_quality_snapshot
```
Cada um existe para responder rapidamente à UI.
---
# 6. SNAPSHOT ≠ FONTE DA VERDADE
Snapshots podem ser reconstruídos.
Logo:
> eventos e registros de domínio são permanentes;
> snapshots são derivados.
Essa distinção precisa existir desde o início.
---
# PARTE II — TOPOLOGIA PROPOSTA
# 7. CÉLULAS RELACIONADAS
Considerando a arquitetura Meshcraft modular:
```text
/catalogo
/funil
/checkout
/alunos
/leads
/automation
/revenue
/analytics
/painel
```
Novas células futuras:
```text
/community
/talent
/b2b
```
---
# 8. CÉLULA PAINEL
Responsabilidades:
* interface do Command Center;
* visualização de métricas;
* navegação;
* dashboards;
* filtros;
* saved views;
* approvals;
* reunião guiada;
* drill-down;
* command palette.
Não deve possuir lógica financeira crítica.
---
# 9. CÉLULA REVENUE
Responsabilidades:
* revenue ledger;
* contribution margin;
* CAC;
* payback;
* LTV;
* cohort economics;
* forecast;
* capital allocation.
---
# 10. CÉLULA ANALYTICS
Responsabilidades:
* event store;
* projection jobs;
* metric engine;
* anomaly detection;
* attribution;
* aggregation;
* data confidence.
Se no MVP for excessivo separar `revenue` de `analytics`, ambos podem inicialmente coexistir em uma célula.
A separação é conceitual.
---
# 11. CÉLULA AUTOMATION
Responsabilidades:
* workflow engine;
* rule engine;
* next best actions;
* scheduled workflows;
* notification routing;
* robot orchestration.
---
# 12. TASK ENGINE
Pode existir inicialmente dentro da célula painel.
Posteriormente pode tornar-se:
```text
/tasks
```
caso vire um serviço compartilhado por diversos domínios.
---
# PARTE III — ROTAS DA INTERFACE
# 13. PREFIXO
Recomendação:
```text
/painel/
```
---
# 14. ROTAS PRINCIPAIS
```text
/painel/
```
Command Center.
---
```text
/painel/strategy/
```
Strategy Overview.
---
```text
/painel/strategy/okrs/
```
OKRs.
---
```text
/painel/strategy/mci/
```
4DX / MCI.
---
```text
/painel/strategy/bets/
```
Strategic Bets.
---
```text
/painel/growth/
```
Growth overview.
---
```text
/painel/growth/constraint/
```
Current Constraint.
---
```text
/painel/growth/funnel/
```
Funnel.
---
```text
/painel/growth/acquisition/
```
Acquisition.
---
```text
/painel/growth/loops/
```
Growth Loops.
---
```text
/painel/growth/experiments/
```
Growth Lab.
---
```text
/painel/growth/experiments/<experiment_id>/
```
Experiment Detail.
---
# 15. ECONOMICS
```text
/painel/economics/
```
Overview.
```text
/painel/economics/cohorts/
```
```text
/painel/economics/cohorts/<cohort_id>/
```
```text
/painel/economics/unit/
```
```text
/painel/economics/payback/
```
```text
/painel/economics/capital/
```
---
# 16. CUSTOMER VALUE
```text
/painel/customer/
```
```text
/painel/customer/activation/
```
```text
/painel/customer/learning/
```
```text
/painel/customer/outcomes/
```
```text
/painel/customer/retention/
```
```text
/painel/customer/referrals/
```
---
# 17. REVENUE
```text
/painel/revenue/
```
```text
/painel/revenue/sales/
```
```text
/painel/revenue/checkout/
```
```text
/painel/revenue/recovery/
```
```text
/painel/revenue/offers/
```
---
# 18. SCALE
```text
/painel/scale/
```
```text
/painel/scale/gates/
```
```text
/painel/scale/capacity/
```
```text
/painel/scale/readiness/
```
---
# 19. OPERATIONS
```text
/painel/operations/
```
```text
/painel/operations/tasks/
```
```text
/painel/operations/robots/
```
```text
/painel/operations/review/
```
```text
/painel/operations/incidents/
```
```text
/painel/operations/data-quality/
```
---
# 20. LEARNING
```text
/painel/learning/
```
```text
/painel/learning/decisions/
```
```text
/painel/learning/validated/
```
```text
/painel/learning/postmortems/
```
---
# 21. REVIEWS
```text
/painel/reviews/weekly/
```
```text
/painel/reviews/mbr/
```
```text
/painel/reviews/qbr/
```
---
# 22. SYSTEM
```text
/painel/system/
```
```text
/painel/system/metrics/
```
```text
/painel/system/events/
```
```text
/painel/system/workflows/
```
```text
/painel/system/permissions/
```
---
# PARTE IV — SHELL GLOBAL DA APLICAÇÃO
# 23. APP SHELL
Estrutura:
```text
┌─────────────────────────────────────────────────┐
│ Global Header                                   │
├───────────────┬─────────────────────────────────┤
│ Sidebar       │ Main Content                    │
│               │                                 │
│               │                                 │
├───────────────┴─────────────────────────────────┤
│ Context Drawer / Command Palette                │
└─────────────────────────────────────────────────┘
```
---
# 24. GLOBAL HEADER
Componentes:
```text
ScaleHealthBadge
DataConfidenceBadge
OperatingModeBadge
GlobalTimeRange
GlobalComparisonSelector
NotificationButton
ApprovalInboxButton
CommandPaletteButton
UserMenu
```
---
# 25. GLOBAL FILTERS
Sempre disponíveis:
```text
date_range
comparison
site
country
currency
product
offer
channel
campaign
cohort
```
Nem todos aparecem em toda tela.
Mas o sistema deve usar uma estrutura padronizada.
---
# 26. URL STATE
Filtros importantes devem ser serializados na URL.
Exemplo:
```text
/painel/economics/cohorts/?range=90d&channel=meta&product=core
```
Benefícios:
* links compartilháveis;
* reprodução;
* debugging;
* bookmark.
---
# 27. SAVED VIEW
Usuário pode salvar filtros como:
```text
"Meta Cold — Core"
"Lista VIP"
"Organic High LTV"
```
Schema:
```json
{
  "name": "Meta Cold Core",
  "route": "/painel/economics/cohorts/",
  "filters": {
    "channel": ["meta"],
    "product_family": ["core"]
  }
}
```
---
# PARTE V — DESIGN SYSTEM DE COMPONENTES
# 28. COMPONENTES PRIMITIVOS
Construir componentes reutilizáveis.
```text
MetricCard
TrendBadge
StatusBadge
ConfidenceBadge
ProgressBar
Sparkline
DeltaIndicator
HealthIndicator
AlertBanner
InsightCard
OpportunityCard
ConstraintCard
ExperimentCard
TaskCard
RobotCard
DecisionCard
CohortTable
FunnelStage
WaterfallChart
TimeSeriesChart
Heatmap
Drawer
Modal
Table
FilterBar
EmptyState
ErrorState
LoadingState
```
---
# 29. METRIC CARD
Props conceituais:
```json
{
  "metric_id": "buyer_cac",
  "label": "Buyer CAC",
  "value": 438.20,
  "formatted_value": "R$ 438,20",
  "delta": 0.07,
  "delta_direction": "up",
  "comparison_label": "vs 4-week avg",
  "target": 400.00,
  "status": "red",
  "confidence": 0.98,
  "updated_at": "2026-09-03T19:00:00-03:00",
  "drilldown_url": "/painel/economics/unit/?metric=buyer_cac"
}
```
---
# 30. STATUS ENUM
```text
healthy
watch
action
critical
experiment
inactive
unknown
```
---
# 31. CONFIDENCE ENUM
```text
high
medium
low
insufficient
```
---
# 32. TREND
Não retornar apenas:
```text
up/down
```
Retornar:
```json
{
  "absolute_delta": 28.4,
  "relative_delta": 0.069,
  "direction": "up",
  "good_or_bad": "bad"
}
```
Porque:
CAC subir é ruim.
Outcome subir é bom.
---
# 33. SEMÂNTICA DE DIREÇÃO
Metric registry precisa ter:
```text
optimization_direction
```
Valores:
```text
higher_is_better
lower_is_better
target_range
contextual
```
---
# PARTE VI — COMMAND CENTER API
# 34. ENDPOINT PRINCIPAL
```http
GET /api/painel/v1/command-center/
```
Resposta agregada.
---
# 35. COMMAND CENTER RESPONSE
```json
{
  "meta": {
    "generated_at": "2026-09-03T19:13:00-03:00",
    "data_confidence": 0.96,
    "operating_mode": "PROVE",
    "range": "4w"
  },
  "scale_health": {
    "score": 84,
    "status": "healthy"
  },
  "north_stars": [],
  "mci": {},
  "current_constraint": {},
  "ceo_scoreboard": [],
  "changes": [],
  "opportunities": [],
  "risks": [],
  "growth_loops": [],
  "experiments": {},
  "operations": {},
  "executive_brief": {}
}
```
---
# 36. NÃO FAZER 20 REQUESTS NO LOAD INICIAL
A home executiva deve preferencialmente receber uma resposta consolidada.
Depois drill-downs carregam dados adicionais.
Objetivo:
**fast first decision.**
---
# 37. CACHE
Command Center pode utilizar cache curto:
```text
30–120 segundos
```
dependendo da métrica.
Não precisa consultar tudo fresh a cada reload.
---
# PARTE VII — NORTH STAR CONTRACT
# 38. SCHEMA
```json
{
  "metric_id": "professional_outcome_rate",
  "label": "Professional Outcome Rate",
  "type": "customer_value",
  "value": 0.32,
  "formatted_value": "32%",
  "target": 0.40,
  "progress": 0.80,
  "trend": {
    "absolute_delta": 0.057,
    "direction": "up",
    "good_or_bad": "good"
  },
  "status": "watch",
  "confidence": "high"
}
```
---
# PARTE VIII — MCI / 4DX DATA MODEL
# 39. ENTITY: WIG
```text
wig
```
Campos:
```text
id
name
description
baseline_value
target_value
metric_id
start_date
end_date
status
owner_id
cycle_id
created_at
updated_at
```
---
# 40. LEAD MEASURE
```text
lead_measure
```
Campos:
```text
id
wig_id
name
metric_id
weekly_target
optimization_direction
owner_id
status
```
---
# 41. WEEKLY RESULT
```text
lead_measure_weekly_result
```
```text
lead_measure_id
week_start
actual_value
target_value
status
```
---
# 42. COMMITMENT
```text
weekly_commitment
```
Campos:
```text
id
cycle_id
week_start
owner_id
description
related_wig_id
related_lead_measure_id
status
expected_impact
learning
completed_at
```
---
# 43. API
```http
GET /api/painel/v1/4dx/current/
```
```http
POST /api/painel/v1/4dx/commitments/
```
```http
PATCH /api/painel/v1/4dx/commitments/<id>/
```
---
# PARTE IX — OKR DATA MODEL
# 44. OBJECTIVE
```text
okr_objective
```
Campos:
```text
id
cycle_id
title
description
owner_id
status
progress
```
---
# 45. KEY RESULT
```text
okr_key_result
```
Campos:
```text
id
objective_id
metric_id
baseline
target
current_value
progress
owner_id
status
```
---
# 46. API
```http
GET /api/painel/v1/okrs/?cycle=current
```
---
# PARTE X — CURRENT CONSTRAINT MODEL
# 47. ENTITY
```text
system_constraint
```
Campos:
```text
id
cycle_id
name
domain
metric_id
baseline
current_value
target
estimated_revenue_impact
estimated_contribution_impact
confidence
status
identified_at
resolved_at
owner_id
evidence_json
```
---
# 48. CONSTRAINT STATUS
```text
suspected
confirmed
active
improving
resolved
invalidated
```
---
# 49. ROOT CAUSES
Entidade:
```text
constraint_driver
```
```text
constraint_id
dimension
dimension_value
effect_size
confidence
rank
```
Exemplo:
```text
dimension = payment_method
dimension_value = PIX
```
---
# 50. API
```http
GET /api/painel/v1/constraints/current/
```
```http
GET /api/painel/v1/constraints/current/drivers/
```
---
# 51. NÃO DEIXAR IA DECLARAR RESTRIÇÃO SOZINHA
IA pode propor:
```text
suspected
```
Humano ou regra explícita pode promover para:
```text
confirmed
```
Isso reduz falsa certeza.
---
# PARTE XI — CEO SCOREBOARD
# 52. ENDPOINT
```http
GET /api/painel/v1/scoreboard/ceo/
```
---
# 53. RESPONSE
```json
{
  "metrics": [
    {
      "metric_id": "buyer_cac",
      "label": "Buyer CAC",
      "value": 438.2,
      "formatted_value": "R$ 438,20",
      "target": 400,
      "status": "action",
      "trend": {},
      "confidence": "high"
    }
  ]
}
```
---
# 54. MÉTRICAS INICIAIS
```text
net_new_buyers
buyer_growth_rate
buyer_cac
marginal_cac
cac_payback_days
contribution_margin
cm_ltv90_cac
core_conversion
activation_d7
professional_outcome_rate
referral_revenue_pct
validated_learning_velocity
```
---
# PARTE XII — METRIC ENGINE
# 55. METRIC DEFINITION
Tabela:
```text
metric_definition
```
Campos:
```text
id
key
name
description
business_definition
formula_description
unit
optimization_direction
owner_domain
source_system
version
status
aggregation
freshness_sla
```
---
# 56. METRIC SNAPSHOT
```text
metric_snapshot
```
Campos:
```text
id
metric_id
period_start
period_end
dimensions_json
value
sample_size
confidence_score
calculated_at
metric_version
```
---
# 57. DIMENSIONS JSON
Exemplo:
```json
{
  "channel": "meta",
  "campaign_id": "cmp_123",
  "product_family": "core"
}
```
---
# 58. NÃO CRIAR COLUNA PARA CADA DIMENSÃO POSSÍVEL
Para agregações analíticas flexíveis, dimensões podem ser armazenadas como JSONB.
Mas dimensões centrais de alta frequência podem ganhar colunas/indexes dedicados.
---
# PARTE XIII — GROWTH LAB
# 59. EXPERIMENT MODEL
```text
experiment
```
Campos:
```text
id
code
title
problem
hypothesis
primary_metric_id
status
owner_id
impact_score
confidence_score
effort_score
strategic_fit_score
priority_score
start_at
end_at
decision
created_at
```
---
# 60. EXPERIMENT VARIANT
```text
experiment_variant
```
Campos:
```text
id
experiment_id
name
is_control
allocation_pct
configuration_json
```
---
# 61. ASSIGNMENT
```text
experiment_assignment
```
```text
experiment_id
subject_type
subject_id
variant_id
assigned_at
```
Subject pode ser:
```text
customer
session
account
```
---
# 62. EXPERIMENT RESULT
```text
experiment_result
```
Campos:
```text
experiment_id
variant_id
metric_id
value
sample_size
confidence
effect_size
calculated_at
```
---
# 63. DECISION ENUM
```text
winner
loser
inconclusive
continue
rollback
rollout
```
---
# 64. API
```http
GET /api/painel/v1/experiments/
```
```http
POST /api/painel/v1/experiments/
```
```http
GET /api/painel/v1/experiments/<id>/
```
```http
POST /api/painel/v1/experiments/<id>/decision/
```
---
# PARTE XIV — COHORT ENGINE
# 65. COHORT DEFINITION
```text
cohort_definition
```
Campos:
```text
id
name
description
criteria_json
created_by
created_at
```
---
# 66. EXEMPLO
```json
{
  "acquisition_month": "2026-08",
  "channel": "instagram_organic",
  "product_family": "core"
}
```
---
# 67. COHORT MEMBERSHIP
Não precisa necessariamente materializar cada membership para todas as coortes ad hoc.
Para coortes estratégicas, sim.
Tabela:
```text
cohort_member
```
---
# 68. COHORT SNAPSHOT
```text
cohort_snapshot
```
Campos:
```text
cohort_id
age_days
buyer_count
gross_revenue
contribution_margin
cac
cm_ltv
refund_rate
activation_rate
outcome_rate
referral_rate
calculated_at
```
---
# 69. AGES
```text
0
7
30
90
180
365
```
---
# 70. API
```http
GET /api/painel/v1/cohorts/
```
```http
GET /api/painel/v1/cohorts/<id>/
```
```http
GET /api/painel/v1/cohorts/<id>/curve/
```
---
# PARTE XV — UNIT ECONOMICS API
# 71. ENDPOINT
```http
GET /api/painel/v1/economics/unit/
```
Query params:
```text
range
channel
campaign
product
offer
cohort
```
---
# 72. RESPONSE
```json
{
  "buyer_cac": {},
  "marginal_cac": {},
  "contribution_margin": {},
  "payback": {},
  "cm_ltv30": {},
  "cm_ltv90": {},
  "cm_ltv365": {},
  "ltv_cac_ratio": {}
}
```
---
# 73. PAYBACK CURVE
```http
GET /api/painel/v1/economics/payback-curve/
```
Response:
```json
{
  "cac": 438.20,
  "payback_day": 61,
  "points": [
    {"day": 0, "cumulative_cm": -438.20},
    {"day": 7, "cumulative_cm": -310.40},
    {"day": 30, "cumulative_cm": -145.00},
    {"day": 61, "cumulative_cm": 0},
    {"day": 90, "cumulative_cm": 181.22}
  ]
}
```
---
# PARTE XVI — CAPITAL ALLOCATION ENGINE
# 74. INITIATIVE
Pode reutilizar projeto/tarefa estratégica.
Tabela:
```text
capital_opportunity
```
Campos:
```text
id
name
category
capital_required
expected_incremental_contribution
expected_payback_days
confidence
strategic_fit
complexity
score
status
```
---
# 75. SCORE
Inicialmente regra configurável.
Não hardcode permanente.
Exemplo:
```text
expected_incremental_contribution
× confidence
× strategic_fit
÷
(capital_required × payback_factor × complexity_factor)
```
---
# 76. API
```http
GET /api/painel/v1/capital/opportunities/
```
---
# PARTE XVII — CUSTOMER VALUE DATA
# 77. LEARNING STATE
A célula alunos continua authority.
Painel recebe projeções.
Campos relevantes:
```text
customer_id
enrollment_id
course_id
learning_state
progress_pct
activation_d1
activation_d7
last_activity_at
projects_completed
portfolio_status
outcome_stage
```
---
# 78. OUTCOME STAGES
```text
O0_NONE
O1_FIRST_ASSET
O2_PROJECT_COMPLETE
O3_PORTFOLIO_APPROVED
O4_MARKET_READY
O5_FIRST_OPPORTUNITY
O6_FIRST_PAID_PROJECT
```
---
# 79. API
```http
GET /api/painel/v1/customer/learning-funnel/
```
```http
GET /api/painel/v1/customer/at-risk/
```
```http
GET /api/painel/v1/customer/outcomes/
```
---
# 80. AT-RISK RESPONSE
```json
{
  "customer_id": "cus_...",
  "display_name": "Aluno 123",
  "progress_pct": 0.12,
  "risk_score": 87,
  "risk_level": "high",
  "last_activity_at": "...",
  "signals": [
    "18d_without_login",
    "project_failed_twice"
  ],
  "next_best_action": {
    "action": "human_success_contact",
    "priority": "high"
  }
}
```
---
# PARTE XVIII — GROWTH LOOPS
# 81. LOOP DEFINITION
```text
growth_loop
```
Campos:
```text
id
name
description
input_event
intermediate_steps_json
output_event
status
owner_id
```
---
# 82. LOOP SNAPSHOT
```text
growth_loop_snapshot
```
```text
loop_id
period_start
period_end
inputs
outputs
amplification_rate
cycle_time_days
conversion_rates_json
```
---
# 83. API
```http
GET /api/painel/v1/growth-loops/
```
---
# PARTE XIX — SALES & RECOVERY
# 84. HIGH INTENT QUEUE
Endpoint:
```http
GET /api/painel/v1/sales/high-intent/
```
---
# 85. ORDERING
Ordenar por:
```text
opportunity_score DESC
```
com penalizações de:
* contato recente;
* opt-out;
* risco;
* inadequação.
---
# 86. NÃO USAR SCORE COMO VERDADE ABSOLUTA
Mostrar:
```text
score
reason
confidence
```
---
# 87. EXEMPLO
```json
{
  "customer_id": "...",
  "opportunity_score": 94,
  "confidence": "high",
  "signals": [
    "checkout_viewed_twice",
    "pix_failed",
    "watched_96_percent"
  ],
  "offer_value": 1497,
  "last_contact_at": null
}
```
---
# PARTE XX — SCALE GATES
# 88. SCALEABLE ENTITY
Gate pode ser aplicado a:
```text
offer
campaign
product
channel
growth_engine
```
---
# 89. SCALE ASSESSMENT
```text
scale_assessment
```
Campos:
```text
id
entity_type
entity_id
assessment_date
demand_status
conversion_status
economics_status
delivery_status
outcome_status
retention_status
repeatability_status
marginal_cac_status
decision
notes
approved_by
```
---
# 90. DECISION
```text
do_not_scale
validate
controlled_scale
scale
pause
rollback
```
---
# PARTE XXI — CAPACITY
# 91. RESOURCE CAPACITY
Tabela:
```text
capacity_resource
```
Campos:
```text
id
name
resource_type
capacity_total
capacity_used
unit
warning_threshold
critical_threshold
owner_id
```
---
# 92. RESOURCE TYPES
```text
human
team
technical
financial
founder
```
---
# 93. FOUNDER CAPACITY
Modelar explicitamente:
```text
Livia
Anderson
```
Exemplo de unidades:
```text
hours/week
approvals/week
content_slots/week
```
Objetivo:
detectar founder bottleneck.
---
# PARTE XXII — TASK ENGINE
# 94. TASK MODEL
```text
task
```
Campos:
```text
id
code
title
description
task_type
status
priority
impact_score
urgency_score
confidence_score
effort_score
owner_type
owner_id
robot_id
batch_id
parallelizable
conflict_group
related_okr_id
related_wig_id
related_constraint_id
related_experiment_id
source_insight_id
source_incident_id
review_required
created_at
started_at
due_at
completed_at
```
---
# 95. STATUSES
```text
backlog
ready
in_progress
waiting
review_exception
approved
done
cancelled
```
---
# 96. PRIORITIES
```text
P0
P1
P2
P3
```
---
# 97. LOCK
```text
task_lock
```
Campos:
```text
task_id
locked_by
locked_at
expires_at
```
---
# 98. CONFLICT GROUP
Exemplo:
```text
painel_html
checkout_payment_flow
catalog_contract
```
Se duas tarefas compartilham o mesmo conflict_group:
não executar em paralelo.
---
# 99. DEPENDENCY
Tabela:
```text
task_dependency
```
```text
task_id
depends_on_task_id
dependency_type
```
---
# 100. API
```http
GET /api/painel/v1/tasks/
```
```http
POST /api/painel/v1/tasks/
```
```http
POST /api/painel/v1/tasks/<id>/claim/
```
```http
POST /api/painel/v1/tasks/<id>/complete/
```
```http
POST /api/painel/v1/tasks/<id>/exception/
```
---
# PARTE XXIII — ROBOT OPERATIONS
# 101. ROBOT MODEL
```text
robot
```
Campos:
```text
id
name
role
status
risk_level
read_permissions_json
write_permissions_json
allowed_actions_json
blocked_actions_json
last_seen_at
```
---
# 102. ROBOT RUN
```text
robot_run
```
```text
id
robot_id
task_id
status
started_at
ended_at
input_summary
output_summary
error
```
---
# 103. RUN STATUS
```text
queued
running
waiting
review
failed
completed
cancelled
```
---
# 104. PERFORMANCE METRICS
```text
tasks_completed
success_rate
exception_rate
human_rework_rate
mean_duration
rollback_rate
```
---
# 105. API
```http
GET /api/painel/v1/robots/
```
```http
GET /api/painel/v1/robots/<id>/runs/
```
---
# PARTE XXIV — REVIEW / EXCEPTION
# 106. EXCEPTION MODEL
```text
execution_exception
```
Campos:
```text
id
task_id
robot_run_id
exception_type
reason
attempted_actions_json
evidence_json
recommended_resolution
risk_level
status
reviewed_by
reviewed_at
```
---
# 107. ACTIONS
```text
approve
correct
reassign
reject
cancel
```
---
# PARTE XXV — INCIDENT SYSTEM
# 108. INCIDENT
```text
incident
```
Campos:
```text
id
code
title
severity
domain
status
started_at
detected_at
resolved_at
owner_id
revenue_at_risk_per_hour
summary
```
---
# 109. SEVERITY
```text
P0
P1
P2
P3
```
---
# 110. INCIDENT EVENT
Timeline:
```text
incident_timeline_event
```
Campos:
```text
incident_id
timestamp
event_type
description
actor
```
---
# 111. POSTMORTEM
```text
incident_postmortem
```
Campos:
```text
incident_id
root_cause
impact
detection_review
response_review
prevention
followup_tasks_json
```
---
# PARTE XXVI — DATA QUALITY
# 112. DATA QUALITY CHECK
```text
data_quality_rule
```
Exemplos:
```text
purchase_without_customer
payment_without_order
enrollment_without_payment
duplicate_customer_identity
negative_order_value
impossible_timestamp
missing_campaign
```
---
# 113. RESULT
```text
data_quality_result
```
Campos:
```text
rule_id
checked_at
passed
affected_records
severity
details_json
```
---
# 114. DATA QUALITY SCORE
Composto por:
```text
completeness
consistency
freshness
reconciliation
identity_resolution
event_health
```
---
# 115. RECONCILIATION
Tabela derivada:
```text
reconciliation_issue
```
Tipos:
```text
missing_in_gateway
missing_in_lms
missing_in_crm
status_mismatch
value_mismatch
duplicate
```
---
# PARTE XXVII — DECISION MEMORY
# 116. DECISION
```text
decision
```
Campos:
```text
id
code
question
decision
context
evidence_json
assumptions_json
alternatives_json
expected_result
metric_id
owner_id
decision_date
review_date
actual_result
learning
status
```
---
# 117. STATUS
```text
active
validated
invalidated
mixed
superseded
```
---
# 118. DECISION REVIEW JOB
Quando chega `review_date`:
criar tarefa automática:
> revisar decisão DEC-XXX.
Isso impede Decision Memory virar arquivo morto.
---
# PARTE XXVIII — VALIDATED LEARNINGS
# 119. LEARNING
```text
validated_learning
```
Campos:
```text
id
code
category
statement
evidence_json
confidence
scope_json
policy_implication
source_experiment_id
source_decision_id
created_at
```
---
# 120. CATEGORY
```text
acquisition
offer
pricing
checkout
sales
learning
retention
community
operations
b2b
```
---
# PARTE XXIX — WEEKLY REVIEW ENGINE
# 121. REVIEW SESSION
```text
review_session
```
Campos:
```text
id
review_type
cycle_id
started_at
completed_at
facilitator_id
status
```
---
# 122. TYPES
```text
weekly
mbr
qbr
annual
```
---
# 123. WEEKLY STEPS
Backend retorna:
```json
[
  {"step": 1, "type": "north_stars"},
  {"step": 2, "type": "mci"},
  {"step": 3, "type": "commitments"},
  {"step": 4, "type": "scoreboard"},
  {"step": 5, "type": "constraint"},
  {"step": 6, "type": "experiments"},
  {"step": 7, "type": "decisions"},
  {"step": 8, "type": "new_commitments"}
]
```
---
# 124. REVIEW ARTIFACT
Ao finalizar:
gerar automaticamente:
```text
review_summary
```
Incluindo:
* decisions;
* commitments;
* tasks;
* unresolved questions;
* experiment actions.
---
# PARTE XXX — MBR / QBR
# 125. MBR GENERATED SNAPSHOT
Antes da reunião:
gerar snapshot imutável:
```text
mbr_snapshot_2026_09
```
Assim os números não mudam durante a reunião.
---
# 126. QBR
Mesmo princípio.
Snapshot:
```text
qbr_snapshot_2026_Q4
```
---
# 127. POR QUE SNAPSHOT?
Sem isso:
duas pessoas podem discutir números que mudaram durante processamento.
Snapshots tornam a revisão auditável.
---
# PARTE XXXI — FORECAST
# 128. FORECAST MODEL
```text
forecast
```
Campos:
```text
id
forecast_date
horizon_days
scenario
metric_id
expected_value
lower_bound
upper_bound
model_version
confidence
```
---
# 129. SCENARIOS
```text
conservative
base
aggressive
custom
```
---
# 130. IMPORTANTE
Forecast nunca deve aparecer como certeza.
Sempre mostrar:
```text
range
confidence
assumptions
```
---
# PARTE XXXII — AI INSIGHT SYSTEM
# 131. INSIGHT
```text
insight
```
Campos:
```text
id
type
title
description
severity
confidence
evidence_json
business_impact_json
recommended_action
status
created_by
created_at
```
---
# 132. TYPES
```text
anomaly
opportunity
risk
trend
root_cause
experiment_idea
data_quality
```
---
# 133. AI OUTPUT CONTRACT
Todo insight gerado por IA precisa obrigatoriamente conter:
```json
{
  "claim": "...",
  "evidence": [],
  "confidence": 0.82,
  "assumptions": [],
  "alternative_explanations": [],
  "recommended_action": "..."
}
```
---
# 134. SEM EVIDÊNCIA
Se evidência insuficiente:
```text
status = hypothesis
```
Não:
```text
confirmed
```
---
# PARTE XXXIII — AI COPILOT
# 135. ENDPOINT
```http
POST /api/painel/v1/copilot/query/
```
Payload:
```json
{
  "query": "Por que o CAC subiu?",
  "context": {
    "route": "/painel/economics/unit/",
    "filters": {}
  }
}
```
---
# 136. RESPONSE CONTRACT
```json
{
  "answer": "...",
  "evidence": [],
  "confidence": "high",
  "alternative_explanations": [],
  "recommended_next_step": {}
}
```
---
# 137. TOOLING INTERNO
Copilot pode consultar:
* metric registry;
* metric snapshots;
* cohorts;
* experiments;
* incidents;
* decisions;
* tasks.
Não deve acessar diretamente tudo sem controle.
---
# PARTE XXXIV — APPROVAL SYSTEM
# 138. APPROVAL REQUEST
```text
approval_request
```
Campos:
```text
id
action_type
entity_type
entity_id
requested_by_type
requested_by_id
risk_level
summary
impact
status
required_role
created_at
resolved_at
resolved_by
```
---
# 139. ACTIONS QUE EXIGEM APROVAÇÃO
Inicialmente:
```text
price_change
budget_increase_high
mass_message
refund_exception
robot_high_risk_action
b2b_proposal
data_delete
production_rollback
```
---
# 140. APPROVAL API
```http
GET /api/painel/v1/approvals/
```
```http
POST /api/painel/v1/approvals/<id>/approve/
```
```http
POST /api/painel/v1/approvals/<id>/reject/
```
---
# PARTE XXXV — PERMISSIONS
# 141. RBAC
Usar Role-Based Access Control.
Papéis iniciais:
```text
super_admin
ceo
growth
finance
education
customer_success
sales
tech
analyst
robot
viewer
```
---
# 142. PERMISSÕES
Exemplos:
```text
metrics.view
metrics.manage
okr.view
okr.edit
task.view
task.create
task.execute
task.approve
experiment.view
experiment.create
experiment.decide
finance.view
finance.export
robot.view
robot.manage
approval.resolve
```
---
# 143. OBJETO + AÇÃO
Formato recomendado:
```text
domain.action
```
---
# 144. CAMPO SENSÍVEL
Dados de aluno menor exigem escopo específico.
Exemplo:
```text
customer.minor_sensitive.view
```
Não disponibilizar genericamente a todos os analistas.
---
# PARTE XXXVI — AUDIT LOG
# 145. AUDIT EVENT
```text
audit_log
```
Campos:
```text
id
actor_type
actor_id
action
entity_type
entity_id
before_json
after_json
reason
ip
timestamp
```
---
# 146. AÇÕES OBRIGATORIAMENTE AUDITADAS
* alterações de preço;
* decisões;
* approvals;
* refunds;
* mudança de permissões;
* robot actions;
* alteração de MCI;
* alteração de OKR;
* scale decision.
---
# PARTE XXXVII — REALTIME
# 147. O QUE PRECISA SER REALTIME?
Não tudo.
Realtime prioritário:
```text
P0/P1 incidents
robot status
critical payment anomalies
approval events
task locks
```
---
# 148. TECNOLOGIA
Com stack atual, opções:
* Server-Sent Events;
* WebSocket;
* polling curto.
Para MVP:
> SSE ou polling controlado pode ser suficiente.
Não criar infraestrutura realtime complexa sem necessidade.
---
# 149. FREQUÊNCIAS
Exemplo:
| Dado            | Freshness |
| --------------- | --------- |
| incident        | segundos  |
| payment anomaly | 1–5 min   |
| robot status    | 5–15s     |
| CAC             | 15–60 min |
| LTV             | diário    |
| cohort D365     | diário    |
| QBR             | snapshot  |
---
# PARTE XXXVIII — LOADING / EMPTY / ERROR
# 150. LOADING
Nunca tela branca.
Skeletons por componente.
---
# 151. EMPTY STATE
Exemplo:
> **Ainda não há dados suficientes para Marginal CAC.**
Mostrar:
```text
Necessário:
≥ X incrementos de investimento comparáveis
Atual:
Y
Próxima atualização estimada:
após nova janela de dados
```
---
# 152. ERROR STATE
Exemplo:
```text
Unable to load cohort economics.
Last valid snapshot:
18:30
Data source:
Revenue Analytics
[Retry]
[View system health]
```
---
# 153. STALE DATA
Se dado ultrapassar freshness SLA:
```text
STALE
```
e timestamp claramente visível.
---
# PARTE XXXIX — DRILL-DOWN ENGINE
# 154. PADRÃO
Cada métrica deve possuir uma árvore de dimensões possíveis.
Exemplo CAC:
```text
GLOBAL
↓
CHANNEL
↓
CAMPAIGN
↓
ADSET
↓
CREATIVE
↓
COHORT
↓
CUSTOMER
```
---
# 155. PARA CONVERSÃO
```text
GLOBAL
↓
DEVICE
↓
BROWSER
↓
PAYMENT METHOD
↓
OFFER
↓
CAMPAIGN
```
---
# 156. METADATA
Metric definition pode armazenar:
```json
{
  "drilldown_dimensions": [
    "channel",
    "campaign",
    "creative",
    "cohort"
  ]
}
```
---
# PARTE XL — ROOT CAUSE ANALYSIS
# 157. DRIVER ANALYSIS
Endpoint:
```http
GET /api/painel/v1/metrics/<metric_id>/drivers/
```
Params:
```text
range
comparison
filters
```
---
# 158. RESPONSE
```json
{
  "metric": "core_conversion",
  "change": -0.118,
  "drivers": [
    {
      "dimension": "payment_method",
      "value": "pix",
      "contribution_to_change": -0.071,
      "confidence": 0.91
    }
  ]
}
```
---
# 159. CAUSALIDADE
Não chamar isso automaticamente de:
> causa.
Chamar:
> driver observado.
Para causalidade:
exigir experimento ou evidência mais forte.
---
# PARTE XLI — ALERT ENGINE
# 160. ALERT RULE
```text
alert_rule
```
Campos:
```text
id
metric_id
condition_json
min_duration
min_magnitude
severity
cooldown
enabled
```
---
# 161. EXEMPLO
```json
{
  "metric_id": "payment_conversion",
  "condition": {
    "type": "relative_drop",
    "threshold": 0.20,
    "comparison": "4w_baseline"
  },
  "min_duration_minutes": 15,
  "severity": "P1"
}
```
---
# 162. ALERT INSTANCE
```text
alert
```
Campos:
```text
id
rule_id
severity
detected_at
resolved_at
status
evidence_json
related_incident_id
```
---
# 163. COOLDOWN
Evitar spam:
```text
same alert cannot fire repeatedly within X
```
---
# PARTE XLII — NOTIFICATIONS
# 164. NOTIFICATION MODEL
```text
notification
```
Campos:
```text
id
recipient_id
type
title
body
severity
entity_type
entity_id
read_at
created_at
```
---
# 165. CENTRO DE NOTIFICAÇÃO
Mostrar apenas:
* approvals;
* incidents;
* review exceptions;
* critical task changes;
* experiment decisions.
---
# PARTE XLIII — SEARCH
# 166. GLOBAL SEARCH
Endpoint:
```http
GET /api/painel/v1/search/?q=
```
Busca em:
```text
customers
orders
tasks
experiments
decisions
incidents
metrics
robots
```
---
# 167. RESULT FORMAT
```json
{
  "type": "experiment",
  "id": "EXP-087",
  "title": "Simplified PIX Checkout",
  "url": "/painel/growth/experiments/EXP-087/"
}
```
---
# PARTE XLIV — COMMAND PALETTE
# 168. ACTIONS
```text
Create Task
Create Experiment
Register Decision
Open Current Constraint
Start Weekly Review
Search Customer
Open Incident
```
---
# 169. PERMISSION-AWARE
Comandos não permitidos não aparecem.
---
# PARTE XLV — FRONTEND STACK
# 170. ALINHAMENTO COM STACK EXISTENTE
Como a plataforma já usa:
* Django;
* templates Django;
* Alpine.js;
* células;
* Traefik;
eu **não migraria o painel inteiro para React apenas porque dashboards costumam usar React**.
Isso aumentaria complexidade operacional.
---
# 171. RECOMENDAÇÃO
MVP:
```text
Django Templates
+
HTMX ou fetch incremental
+
Alpine.js
+
Chart library pequena
```
Se HTMX ainda não fizer parte do stack, pode-se manter fetch/Alpine.
---
# 172. CHART LIBRARY
Escolher uma biblioteca única.
Critérios:
* bundle razoável;
* acessibilidade;
* time-series;
* heatmap;
* funnel;
* waterfall;
* responsive.
Não misturar três bibliotecas.
---
# 173. COMPONENTIZAÇÃO
Mesmo em templates Django:
```text
components/
  metric_card.html
  status_badge.html
  insight_card.html
  task_card.html
  ...
```
---
# PARTE XLVI — API STYLE
# 174. PREFIXO
```text
/api/painel/v1/
```
---
# 175. JSON ENVELOPE
Padrão:
```json
{
  "data": {},
  "meta": {
    "generated_at": "...",
    "request_id": "..."
  },
  "errors": []
}
```
---
# 176. ERROR FORMAT
```json
{
  "errors": [
    {
      "code": "INSUFFICIENT_DATA",
      "message": "Not enough cohort data.",
      "details": {}
    }
  ]
}
```
---
# 177. PAGINAÇÃO
Para listas grandes:
cursor pagination.
Exemplo:
```text
?cursor=...
```
Melhor que offset em algumas estruturas mutáveis.
---
# PARTE XLVII — EVENT CONTRACTS
# 178. EVENT ENVELOPE
Padronizar:
```json
{
  "event_id": "evt_...",
  "event_name": "...",
  "schema_version": 1,
  "producer": "...",
  "occurred_at": "...",
  "received_at": "...",
  "customer_id": null,
  "site_id": "...",
  "properties": {},
  "context": {}
}
```
---
# 179. CONTEXT
Pode incluir:
```json
{
  "request_id": "...",
  "session_id": "...",
  "user_agent": "...",
  "utm": {},
  "ip_country": "BR"
}
```
Evitar armazenar dados desnecessários.
---
# 180. EVENT REGISTRY
Tabela:
```text
event_schema
```
Campos:
```text
event_name
schema_version
producer
json_schema
status
```
---
# 181. JSON SCHEMA VALIDATION
Eventos críticos devem ser validados.
Se inválidos:
```text
dead_letter
```
Não inferir silenciosamente.
---
# PARTE XLVIII — DEAD LETTER QUEUE
# 182. MODEL
```text
dead_letter_event
```
Campos:
```text
event_id
event_name
producer
payload_json
validation_error
attempt_count
last_attempt_at
status
```
---
# 183. PAINEL
`System > Event Health`
Mostrar:
```text
DLQ: 7
```
Ação:
```text
[Inspect]
[Retry]
[Discard with reason]
```
---
# PARTE XLIX — IDEMPOTENCY
# 184. WEBHOOKS
Guardar:
```text
external_event_id
```
Criar unique constraint.
---
# 185. PAYMENT
Nunca criar duas compras porque gateway enviou webhook duplicado.
---
# PARTE L — SCHEDULED JOBS
# 186. JOBS
Exemplos:
```text
metric_snapshot_15m
metric_snapshot_daily
cohort_daily
ltv_daily
payback_daily
data_quality_hourly
reconciliation_daily
forecast_daily
decision_review_daily
```
---
# 187. ORQUESTRADOR
No MVP, Celery ou scheduler existente.
Não criar Kubernetes-like orchestration numa VPS pequena.
---
# PARTE LI — PERFORMANCE
# 188. ALVO INICIAL
Command Center:
```text
TTFB < 500ms cache hit
usable < 2s
```
Não precisa ser milissegundo extremo.
Mas deve ser rápido o suficiente para uso operacional.
---
# 189. CONSULTAS
Evitar:
* joins gigantes em request;
* calcular LTV na hora;
* reconstruir cohort em page load.
Pré-calcular.
---
# 190. ÍNDICES
Prováveis:
```text
event_name
occurred_at
customer_id
order_id
campaign_id
metric_id + period
task status
incident status
experiment status
```
---
# PARTE LII — RETENÇÃO DE DADOS
# 191. EVENTOS
Eventos financeiros/auditoria:
retenção de longo prazo conforme requisitos contábeis/jurídicos.
Eventos analíticos muito granulares:
política específica.
Não guardar tudo eternamente sem necessidade.
---
# 192. PRIVACIDADE
Aplicar minimização de dados.
O painel executivo não precisa expor:
* endereço completo;
* dados sensíveis;
* informações desnecessárias.
---
# PARTE LIII — SEGURANÇA
# 193. REQUISITOS
* autenticação forte;
* CSRF;
* permissions;
* audit;
* secrets fora do código;
* rate limiting em endpoints sensíveis;
* sessões seguras;
* proteção de dados de menores.
---
# 194. ROBOTS
Robôs recebem credenciais de escopo mínimo.
Nunca:
```text
super_admin
```
por conveniência.
---
# PARTE LIV — FEATURE FLAGS
# 195. MODEL
```text
feature_flag
```
Campos:
```text
key
enabled
rollout_percentage
conditions_json
```
---
# 196. USOS
* AI Brief;
* Capital Allocation;
* Next Best Action;
* novo checkout;
* nova tela.
---
# PARTE LV — CONFIGURATION
# 197. BUSINESS RULE CONFIG
Tabela/config:
```text
business_setting
```
Exemplos:
```text
cac_watch_threshold
payback_target_days
risk_score_high
high_intent_score
contact_cooldown_hours
```
---
# 198. NÃO ENTERRAR NO CÓDIGO
Se regra operacional provavelmente mudará:
configurável.
---
# PARTE LVI — TESTES
# 199. TESTES UNITÁRIOS
Obrigatórios para:
* métricas;
* margem;
* CAC;
* payback;
* LTV;
* state transitions;
* permissions;
* workflow conditions.
---
# 200. CONTRACT TESTS
Cada produtor de eventos precisa passar contract tests.
---
# 201. INTEGRATION TESTS
Exemplo:
```text
payment_confirmed
→ enrollment_created
→ event published
→ revenue projection updated
→ dashboard reflects purchase
```
---
# 202. RECONCILIATION TEST
Cenários:
* webhook duplicado;
* webhook atrasado;
* refund parcial;
* chargeback;
* buyer sem lead.
---
# 203. UI TESTS
Fluxos críticos:
* abrir Command Center;
* drilldown CAC;
* aprovar ação;
* iniciar Weekly Review;
* criar tarefa;
* fechar experimento.
---
# PARTE LVII — OBSERVABILITY
# 204. LOGS
Logs estruturados:
```json
{
  "request_id": "...",
  "service": "revenue",
  "event": "metric_calculation_failed",
  "metric": "buyer_cac"
}
```
---
# 205. REQUEST ID
Propagar entre células quando possível.
Isso facilita rastrear:
```text
click
→ checkout
→ payment
→ event
→ projection
```
---
# 206. SYSTEM HEALTH
Monitorar:
```text
event lag
queue lag
failed jobs
API latency
error rate
cache health
database connections
```
---
# PARTE LVIII — DATA CONFIDENCE
# 207. CONFIDENCE SCORE
Não precisa começar sofisticado.
Pode combinar:
```text
completeness
freshness
reconciliation
sample_size
source_quality
```
---
# 208. EXEMPLO
CAC:
```text
confidence = 0.99
```
porque dados financeiros sólidos.
Attribution:
```text
confidence = 0.63
```
porque tracking parcial.
---
# 209. UI
Sempre mostrar confidence em:
* atribuição;
* forecast;
* IA;
* root cause;
* LTV projetado.
---
# PARTE LIX — MVP TÉCNICO
# 210. O QUE CONSTRUIR PRIMEIRO
## FASE 0 — CONTRATOS
Antes da UI:
1. Metric Registry.
2. Event envelope.
3. Customer IDs.
4. Revenue definitions.
5. Permissions.
---
# 211. MVP A — COMMAND FOUNDATION
Implementar:
```text
/painel/
/painel/strategy/mci/
/painel/growth/constraint/
/painel/operations/tasks/
/painel/operations/robots/
/painel/operations/data-quality/
```
---
# 212. DADOS NECESSÁRIOS
Inicialmente:
* compras;
* pagamentos;
* alunos;
* leads;
* campanhas;
* métricas básicas;
* tarefas;
* robôs.
---
# 213. CEO KPIs MVP
Começar com:
```text
net_new_buyers
buyer_cac
contribution_margin
core_conversion
activation_d7
```
Não esperar os 12 perfeitos para colocar painel no ar.
---
# 214. MVP B — ECONOMIC FOUNDATION
Adicionar:
```text
marginal_cac
payback
cm_ltv90
cohorts
```
---
# 215. MVP C — EXPERIMENTATION
Adicionar:
* Growth Lab;
* Decision Memory;
* Validated Learnings.
---
# 216. MVP D — CUSTOMER VALUE
Adicionar:
* learning funnel;
* outcomes;
* risk.
---
# 217. MVP E — MANAGEMENT SYSTEM
Adicionar:
* OKRs;
* Weekly Review;
* MBR;
* QBR;
* Capital Allocation;
* Scale Gates.
---
# 218. MVP F — AI
Só depois:
* AI Brief;
* root cause assistant;
* leverage suggestions;
* red team;
* NBA.
---
# PARTE LX — O QUE NÃO CONSTRUIR AGORA
# 219. NÃO IMPLEMENTAR NO MVP
* ML preditivo complexo;
* agente autônomo mudando orçamento;
* marketplace;
* event streaming distribuído sofisticado;
* data warehouse gigante;
* custom BI engine;
* real-time para tudo;
* 30 serviços;
* microfrontend;
* React migration;
* graph database sem necessidade comprovada.
---
# 220. PRINCÍPIO
> **Software de gestão deve reduzir complexidade operacional, não materializá-la em código.**
---
# PARTE LXI — ORDEM DE IMPLEMENTAÇÃO EM 12 LOTES
# 221. LOTE 1 — FOUNDATION CONTRACTS
Entregáveis:
* enums;
* IDs;
* EventEnvelope;
* MetricDefinition;
* permissions;
* audit.
---
# 222. LOTE 2 — REVENUE READ MODEL
* orders;
* payments;
* refunds;
* contribution margin.
---
# 223. LOTE 3 — COMMAND CENTER SHELL
* sidebar;
* global header;
* filters;
* MetricCard;
* alerts.
---
# 224. LOTE 4 — MCI / 4DX
* WIG;
* lead measures;
* weekly commitments;
* scoreboard.
---
# 225. LOTE 5 — TASK / ROBOT OPERATIONS
* Kanban;
* locks;
* review exception;
* robot status.
---
# 226. LOTE 6 — DATA QUALITY
* reconciliation;
* health;
* DLQ.
---
# 227. LOTE 7 — CURRENT CONSTRAINT
* constraint model;
* card;
* root-cause drilldown.
---
# 228. LOTE 8 — ECONOMICS
* CAC;
* payback;
* CM-LTV;
* cohort tables.
---
# 229. LOTE 9 — GROWTH LAB
* experiments;
* assignments;
* results;
* learnings.
---
# 230. LOTE 10 — CUSTOMER VALUE
* activation;
* learning;
* outcomes;
* at-risk.
---
# 231. LOTE 11 — MANAGEMENT REVIEWS
* OKRs;
* Weekly;
* MBR;
* QBR.
---
# 232. LOTE 12 — AI ASSISTANCE
* insight engine;
* executive brief;
* red-team view.
---
# PARTE LXII — DEFINITION OF DONE POR TELA
# 233. COMMAND CENTER
Done quando:
* carrega rápido;
* mostra freshness;
* todas métricas têm definição;
* drill-down funciona;
* alertas têm ação;
* sem dados falsos/default arbitrários;
* dados stale claramente marcados.
---
# 234. CURRENT CONSTRAINT
Done quando:
* restrição pode ser identificada;
* evidência aparece;
* drivers aparecem;
* impacto econômico estimado;
* tarefas/experimentos associados.
---
# 235. GROWTH LAB
Done quando:
* experimento nasce;
* variante atribuída;
* resultado calculado;
* decisão registrada;
* aprendizado persistido.
---
# 236. TASK ENGINE
Done quando:
* dependências;
* lock;
* robot;
* exception;
* review;
* audit;
funcionam.
---
# PARTE LXIII — CONTRATO VISUAL PARA TODOS OS CARDS
# 237. TODO CARD IMPORTANTE DEVE RESPONDER
```text
WHAT?
```
O que é?
```text
SO WHAT?
```
Por que importa?
```text
NOW WHAT?
```
O que fazer?
---
# 238. EXEMPLO
```text
CORE CONVERSION
2.9%
↓14% vs média 4 semanas
Impacto estimado:
-R$49k CM/ciclo
Principal driver:
PIX Mobile
[Diagnosticar]
```
---
# PARTE LXIV — HIERARQUIA DE AÇÕES
# 239. TODA TELA DEVE TERMINAR EM UMA DESTAS AÇÕES
```text
Investigate
Create Task
Create Experiment
Assign
Approve
Escalate
Decide
Learn
```
Se a tela não conduz a nenhuma ação:
questionar sua existência.
---
# PARTE LXV — CONTRATO DO REVENUE BRAIN
# 240. INPUTS
Revenue Brain recebe:
* eventos;
* snapshots;
* coortes;
* experimentos;
* decisões;
* tarefas.
---
# 241. OUTPUTS
Revenue Brain produz:
```text
anomaly
risk
opportunity
hypothesis
driver
recommended_action
```
---
# 242. NUNCA PRODUZ DIRETAMENTE
Sem approval explícito:
```text
price_change
large_budget_change
refund
mass_message
production_patch
```
---
# PARTE LXVI — FLUXOS DE PONTA A PONTA
# 243. FLUXO 1 — QUEDA DE CONVERSÃO
```text
payment events
↓
metric update
↓
conversion anomaly
↓
alert P1
↓
driver analysis
↓
PIX mobile identified
↓
constraint updated
↓
experiment created
↓
task generated
↓
robot assigned
↓
review
↓
rollout
↓
metric recovers
↓
learning stored
```
Esse fluxo é o coração do sistema.
---
# 244. FLUXO 2 — ALUNO EM RISCO
```text
14d inactivity
↓
risk score ↑
↓
customer health state
↓
NBA
↓
success task
↓
human intervention
↓
student returns
↓
risk score ↓
↓
intervention outcome stored
```
---
# 245. FLUXO 3 — NOVA OPORTUNIDADE DE ESCALA
```text
3 cohorts strong
↓
CAC acceptable
↓
CM-LTV strong
↓
Outcome healthy
↓
Scale Gate PASS
↓
Capital Allocation candidate
↓
approval
↓
controlled scale
↓
Marginal CAC monitored
```
---
# 246. FLUXO 4 — DECISÃO ESTRATÉGICA
```text
QBR
↓
Bet reviewed
↓
evidence examined
↓
decision
↓
Decision Memory
↓
tasks
↓
next-cycle OKR
```
---
# PARTE LXVII — ANTI-PADRÕES TÉCNICOS
# 247. NÃO FAZER
### KPI calculado em template.
### regras econômicas espalhadas em views.
### cores hardcoded por página.
### eventos sem schema version.
### robôs com acesso total.
### tarefa sem source.
### insight sem evidence.
### IA escrevendo diretamente em produção.
### dashboard consultando gateway em page load.
### métrica sem definição.
### duplicar order table no painel.
---
# PARTE LXVIII — ARQUITETURA DE PASTAS SUGERIDA
# 248. PAINEL
```text
painel/
├── urls.py
├── views/
│   ├── command.py
│   ├── strategy.py
│   ├── growth.py
│   ├── economics.py
│   ├── operations.py
│   └── reviews.py
│
├── api/
│   ├── command.py
│   ├── metrics.py
│   ├── tasks.py
│   ├── robots.py
│   └── approvals.py
│
├── models/
│   ├── task.py
│   ├── decision.py
│   ├── review.py
│   └── saved_view.py
│
├── services/
│   ├── dashboard_service.py
│   ├── drilldown_service.py
│   └── approval_service.py
│
├── templates/painel/
│   ├── base.html
│   ├── command/
│   ├── growth/
│   ├── economics/
│   ├── operations/
│   └── components/
│
└── static/painel/
```
---
# 249. ANALYTICS
```text
analytics/
├── events/
├── metrics/
├── cohorts/
├── anomalies/
├── projections/
└── contracts/
```
---
# 250. REVENUE
```text
revenue/
├── ledger/
├── economics/
├── attribution/
├── forecasts/
└── capital/
```
---
# PARTE LXIX — TESTE DE ARQUITETURA
# 251. PERGUNTA 1
Se a célula painel desaparecer:
as compras continuam funcionando?
**Precisa ser sim.**
---
# 252. PERGUNTA 2
Se analytics atrasar:
checkout continua funcionando?
**Sim.**
---
# 253. PERGUNTA 3
Se IA cair:
painel básico continua funcional?
**Sim.**
---
# 254. PERGUNTA 4
Se M-ROS errar um insight:
há auditabilidade?
**Sim.**
---
# 255. PERGUNTA 5
Se uma regra mudar:
precisamos deployar código?
Idealmente:
**nem sempre.**
---
# PARTE LXX — PRINCÍPIOS DE RESILIÊNCIA
# 256. DEGRADAÇÃO GRACIOSA
Se AI indisponível:
mostrar métricas.
Se forecast indisponível:
mostrar histórico.
Se attribution falhar:
mostrar baixa confiança.
Se snapshot stale:
mostrar último válido.
---
# 257. FAIL CLOSED
Para:
* financeiro;
* permissões;
* approvals;
* dados sensíveis.
Se incerto:
não executar.
---
# 258. FAIL OPEN
Pode ser aceitável em:
* tooltip;
* insight secundário;
* recomendação não crítica.
---
# PARTE LXXI — CRITÉRIO DE SUCESSO DA v1.2
# 259. O SISTEMA ESTÁ CERTO SE CONSEGUIR FAZER ISTO
Anderson entra em:
```text
/painel/
```
e em menos de um minuto consegue saber:
1. a empresa está saudável?
2. qual é a MCI?
3. estamos ganhando?
4. qual é o gargalo dominante?
5. qual métrica piorou?
6. qual a principal oportunidade?
7. há risco crítico?
8. quais experimentos estão rodando?
9. quais robôs estão trabalhando?
10. qual decisão precisa dele?
---
# 260. EM MENOS DE CINCO MINUTOS
Ele consegue:
* abrir o gargalo;
* ver drivers;
* abrir experimento;
* aprovar decisão;
* gerar tarefa;
* atribuir robô;
* registrar decisão.
---
# 261. EM MENOS DE UMA HORA POR SEMANA
A empresa consegue executar sua:
# WEEKLY SCALE REVIEW
sem montar slides manualmente.
---
# 262. EM UM CLIQUE
Qualquer número importante precisa responder:
> **de onde veio?**
---
# 263. EM DOIS CLIQUES
Precisa responder:
> **o que está causando a mudança?**
---
# 264. EM TRÊS CLIQUES
Precisa ser possível:
> **transformar a descoberta em ação.**
Essa pode ser uma excelente regra de UX.
---
# PARTE LXXII — A REGRA DOS TRÊS CLIQUES OPERACIONAIS
```text
METRIC
↓
DIAGNOSIS
↓
ACTION
```
Exemplo:
```text
CAC ↑
↓
Meta Cold / Creative A
↓
Create Experiment
```
---
# PARTE LXXIII — ORDEM DE CONSTRUÇÃO REAL RECOMENDADA
# 265. NÃO COMEÇAR PELA HOME BONITA
Começar pelos contratos.
Ordem:
```text
1. Metric Registry
2. Event Contracts
3. Revenue Ledger
4. Read Models
5. Task Engine
6. Data Quality
7. APIs
8. Command Center
9. Drilldowns
10. Experiments
11. Reviews
12. AI
```
---
# 266. POR QUÊ?
Se começarmos pelo HTML:
teremos um painel lindo conectado a dados inconsistentes.
Se começarmos pelos contratos:
o frontend torna-se a consequência visual de um sistema coerente.
---
# PARTE LXXIV — PRIORIDADE DE IMPLEMENTAÇÃO 10X
## P0 — FUNDAÇÃO
* identidade;
* contratos;
* métricas;
* auditabilidade.
## P1 — DECISÃO
* Command Center;
* MCI;
* Current Constraint;
* tasks.
## P2 — ECONOMIA
* CAC;
* margin;
* cohorts;
* payback.
## P3 — APRENDIZADO
* experiments;
* decisions;
* learnings.
## P4 — INTELIGÊNCIA
* anomaly;
* AI;
* forecast;
* NBA.
---
# PARTE LXXV — A ARQUITETURA FINAL
```text
                   MESHCRAFT SYSTEMS
                          │
       ┌──────────────────┼─────────────────┐
       ↓                  ↓                 ↓
   CHECKOUT            ALUNOS            LEADS
       │                  │                 │
       └──────────────────┼─────────────────┘
                          ↓
                     EVENT LAYER
                          ↓
                   ANALYTICS / ROS
                          ↓
       ┌──────────────────┼──────────────────┐
       ↓                  ↓                  ↓
   METRICS            ECONOMICS          STATES
       │                  │                  │
       └──────────────────┼──────────────────┘
                          ↓
                    DECISION LAYER
                          ↓
          ┌───────────────┼───────────────┐
          ↓               ↓               ↓
       INSIGHT        CONSTRAINT       NBA
          │               │               │
          └───────────────┼───────────────┘
                          ↓
                      PAINEL
                          ↓
            ┌─────────────┼─────────────┐
            ↓             ↓             ↓
         HUMAN          ROBOT       AUTOMATION
            │             │             │
            └─────────────┼─────────────┘
                          ↓
                       ACTION
                          ↓
                       EVENT
                          ↺
```
---
# PARTE LXXVI — TESE FINAL DA v1.2
O desafio técnico não é:
> **construir 28 dashboards.**
O desafio é construir um sistema em que cada informação importante tenha:
```text
DEFINIÇÃO
+
FONTE
+
CONTEXTO
+
CONFIANÇA
+
RESPONSÁVEL
+
AÇÃO POSSÍVEL
```
E cada ação importante tenha:
```text
ORIGEM
+
OBJETIVO
+
DONO
+
AUDITORIA
+
RESULTADO
+
APRENDIZADO
```
Quando isso existir, o painel deixa de ser uma camada visual.
Ele passa a representar a interface operacional de uma arquitetura maior:
# MESHCRAFT SCALE OS
onde:
```text
ESTRATÉGIA
↓
MÉTRICAS
↓
RESTRIÇÃO
↓
EXPERIMENTO
↓
DECISÃO
↓
TAREFA
↓
EXECUÇÃO
↓
RESULTADO
↓
APRENDIZADO
↓
ESTRATÉGIA MELHOR
↺
```
Esse é o **Meshcraft Scale OS 1.2 — Especificação Técnica do Painel**.
Seu objetivo não é apenas permitir que a empresa veja mais.
É permitir que a Meshcraft:
> **detecte antes, compreenda mais profundamente, decida mais rápido, execute com disciplina e aprenda permanentemente.**
