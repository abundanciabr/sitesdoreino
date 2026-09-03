# Documento 3: MESHCRAFT SCALE OS 1.1, ARQUITETURA DO PAINEL

> Texto de IA externa, colado pelo mantenedor em 03/09/2026 nesta sessão, como o terceiro documento da proposta nova do painel de gestão. Guardado sem edição.

# MESHCRAFT SCALE OS 1.1
# ARQUITETURA DO PAINEL
## Centro de Comando Executivo, Operacional e de Aprendizado da Meshcraft
---
# 1. OBJETIVO DO PAINEL
O Painel do Meshcraft Scale OS não deve ser:
* um BI bonito;
* um repositório de KPIs;
* um mural de tarefas;
* um dashboard de marketing;
* uma tela de "faturamento do dia".
Ele deve funcionar como:
# SISTEMA DE DECISÃO DA EMPRESA
Sua função é transformar continuamente:
```text
DADOS
↓
SINAL
↓
DIAGNÓSTICO
↓
PRIORIDADE
↓
DECISÃO
↓
AÇÃO
↓
RESULTADO
↓
APRENDIZADO
```
Portanto, cada tela deve responder pelo menos uma destas perguntas:
1. Estamos vencendo?
2. O que mudou?
3. Por que mudou?
4. Onde está o gargalo?
5. Qual é a maior alavanca?
6. O que precisa ser feito?
7. Quem deve fazer?
8. Está funcionando?
9. O que aprendemos?
10. O sistema está ficando melhor?
---
# 2. PRINCÍPIO CENTRAL DE UX
# ACTIONABLE BY DEFAULT
Nenhum KPI deve existir sem caminho para ação.
Exemplo ruim:
> CAC = R$ 487.
Exemplo correto:
```text
CAC
R$487
↑ 18% vs média 4 semanas
Principal causa provável:
Meta Cold / Creative Family C
Impacto estimado:
-R$32.400 / mês
Confiança:
Alta
[Abrir diagnóstico]
[Ver coortes]
[Criar experimento]
```
O usuário não termina olhando um número.
Ele termina:
> tomando uma decisão.
---
# 3. HIERARQUIA DO PAINEL
A arquitetura terá quatro níveis.
## NÍVEL 1 — COMMAND
O que o CEO precisa saber em 60 segundos.
## NÍVEL 2 — DIAGNOSE
Por que algo está acontecendo.
## NÍVEL 3 — OPERATE
O que precisa ser executado.
## NÍVEL 4 — LEARN
O que a empresa aprendeu e deve incorporar.
---
# 4. MAPA PRINCIPAL DE NAVEGAÇÃO
Menu lateral:
```text
00  COMMAND CENTER
01  STRATEGY
    ├── North Stars
    ├── OKRs
    ├── MCI / 4DX
    └── Strategic Bets
02  GROWTH
    ├── Current Constraint
    ├── Funnel
    ├── Acquisition
    ├── Growth Loops
    └── Growth Lab
03  ECONOMICS
    ├── Unit Economics
    ├── Cohorts
    ├── LTV / CAC
    ├── Payback
    └── Capital Allocation
04  CUSTOMER VALUE
    ├── Activation
    ├── Learning
    ├── Outcomes
    ├── Retention
    └── Referrals
05  REVENUE
    ├── Sales
    ├── Offers
    ├── Checkout
    ├── Recovery
    └── Revenue Events
06  SCALE
    ├── Scale Gates
    ├── Capacity
    ├── Portfolio of Bets
    └── Scale Readiness
07  OPERATIONS
    ├── Tasks
    ├── Robots
    ├── Review / Exception
    ├── Incidents
    └── Data Quality
08  LEARNING
    ├── Experiments
    ├── Validated Learnings
    ├── Decision Memory
    └── Post-Mortems
09  REVIEWS
    ├── Weekly Scale Review
    ├── MBR
    ├── QBR
    └── Annual Review
10  SYSTEM
    ├── Metrics Registry
    ├── Event Health
    ├── Automations
    ├── Permissions
    └── Configuration
```
---
# 5. TELA 00 — COMMAND CENTER
É a tela mais importante.
Ela responde:
> **Qual é a situação da Meshcraft agora?**
O CEO deve entendê-la em aproximadamente 60 segundos.
---
# 6. CABEÇALHO GLOBAL
Sempre visível.
```text
MESHCRAFT SCALE OS
03 SET 2026 • 19:13
SCALE HEALTH   84/100
STATUS         HEALTHY
DATA CONF.     96%
CURRENT MODE   PROVE
[Últimas 24h] [7d] [4 semanas] [Trimestre]
```
Modo da empresa:
```text
FIND
PROVE
SCALE
COMPOUND
```
---
# 7. BLOCO 1 — NORTH STARS
Primeira linha.
## CUSTOMER VALUE
```text
Professional Outcome Rate
Atual:
32%
Meta:
40%
∆ trimestre:
+5,7 pp
```
## ECONOMIC VALUE
```text
Monthly Contribution Margin
Atual:
R$ 247.400
Meta:
R$ 300.000
∆:
+14%
```
O objetivo é evitar crescimento financeiro sem resultado ao cliente.
---
# 8. BLOCO 2 — MCI / 4DX
Card grande e impossível de ignorar.
```text
MCI — CICLO Q4
Reduzir CAC Payback
de 74 → 50 dias
até 30/11/2026
ATUAL
61 dias
PROGRESSO
56%
TEMPO RESTANTE
8 semanas
```
Abaixo:
```text
LEAD MEASURE 1
Paid Entry Activation ≥ 72%
Meta: 72%
Atual: 76%  🟢
LEAD MEASURE 2
Recovery high-intent ≤ 15 min
Meta: 85%
Atual: 68%  🔴
```
Pergunta visual:
# ESTAMOS GANHANDO?
Resposta:
```text
🟡 PARCIALMENTE
```
---
# 9. BLOCO 3 — CURRENT CONSTRAINT
Card de altíssima prioridade.
```text
🔴 CURRENT CONSTRAINT
CHECKOUT → PAYMENT CONFIRMED
Conversão:
18,9%
Baseline:
24,8%
Gap:
-5,9 pp
Impacto econômico estimado:
R$ 94.200 / ciclo
Confidence:
HIGH
```
Ações:
```text
[Investigar causa]
[Ver experimentos]
[Ver tarefas]
[Exploit Constraint]
```
Esse deve ser um dos cards mais visualmente fortes do painel.
---
# 10. BLOCO 4 — CEO SCOREBOARD 12 KPIs
Formato compacto.
| KPI                  |  Atual | Tendência |   Meta | Status |
| -------------------- | -----: | --------: | -----: | ------ |
| Net New Buyers       |    218 |      +12% |    240 | 🟡     |
| Buyer Growth         |   9,4% |         ↑ |    12% | 🟡     |
| Buyer CAC            |  R$438 |       +7% |  R$400 | 🔴     |
| Marginal CAC         |  R$561 |      +15% |  R$500 | 🔴     |
| CAC Payback          |    61d |         ↓ |    50d | 🟡     |
| Contribution Margin  | R$247k |      +14% | R$300k | 🟡     |
| CM-LTV90/CAC         |    2,7 |      +0,3 |    3,0 | 🟡     |
| Core Conversion      |   2,9% |         ↓ |   3,4% | 🔴     |
| Activation D7        |    71% |         ↑ |    70% | 🟢     |
| Professional Outcome |    32% |         ↑ |    40% | 🟡     |
| Referral Revenue     |    11% |         ↑ |    15% | 🟡     |
| VLV                  |      7 |         ↑ |     10 | 🟡     |
Clicar em qualquer linha abre diagnóstico.
---
# 11. BLOCO 5 — WHAT CHANGED?
O Revenue Brain apresenta apenas mudanças materialmente relevantes.
Exemplo:
```text
O QUE MUDOU DESDE A ÚLTIMA SEMANA?
🔴 Core Conversion -14%
   Principal contribuição: PIX mobile
🟢 Activation D7 +9%
   Cohort Challenge-B puxou alta
🟡 Marginal CAC +15%
   Meta Cold saturando Creative Family A
🟢 Referral Revenue +23%
   Cohort Jun/26 gerando maior advocacy
```
Nada de 50 notificações irrelevantes.
---
# 12. BLOCO 6 — TOP LEVERAGE OPPORTUNITIES
A IA classifica oportunidades.
```text
TOP 5 ALAVANCAS
1. Checkout PIX
   Impacto potencial: +R$94k/ciclo
   Confidence: 88%
   Effort: Medium
2. Checkout Recovery High Intent
   +R$41k/ciclo
   Confidence: 82%
3. Paid Entry Variant C
   +R$31k CM90 estimado
4. Activation D1
   provável impacto em refund/outcome
5. Referral trigger pós-portfólio
   potencial CAC reduction
```
---
# 13. BLOCO 7 — RISKS
```text
RISCOS EMERGENTES
P1
Payment failures +31%
P2
Support load +22%
P2
Meta frequency rising rapidly
P3
Guild cohort July engagement declining
```
---
# 14. BLOCO 8 — GROWTH LOOPS
Mini-scorecards.
```text
OUTCOME LOOP        0.18x amplification
REFERRAL LOOP       0.12x
ORGANIC LOOP        0.43x
TALENT LOOP         Discovery
```
O objetivo futuro:
> elevar progressivamente a aquisição gerada pelo próprio sistema.
---
# 15. BLOCO 9 — EXPERIMENTS
```text
EXPERIMENTOS
Running        8
Analyzing      3
Winner         2
Loser          4
Inconclusive   1
Potential winner:
EXP-087 Checkout Pix Simplified
+18,4% conversion
Confidence 91%
```
---
# 16. BLOCO 10 — OPERATIONAL EXECUTION
```text
TAREFAS
P0             0
P1             4
Blocked        3
Robot Running  6
Review         5
Overdue        2
```
---
# 17. BLOCO 11 — AI EXECUTIVE BRIEF
Texto curto.
Exemplo:
> **Situação geral:** crescimento saudável, porém com deterioração de aquisição e conversão de checkout. Activation e referrals melhoraram. A maior alavanca continua no pagamento PIX mobile. Não recomendo escalar mídia até validar EXP-087 e resolver failures acima do baseline.
A IA deve diferenciar:
* fato;
* hipótese;
* recomendação;
* confiança.
---
# 18. TELA 01 — STRATEGY
Objetivo:
> lembrar à organização onde estamos indo e evitar deriva.
---
# 19. NORTH STAR VIEW
Visual:
```text
VISION
↓
STRATEGIC THESIS
↓
ANNUAL BETS
↓
NORTH STARS
↓
QUARTERLY OKRs
↓
MCI
```
Clicar em qualquer elemento abre seu detalhe.
---
# 20. OKR BOARD
Exemplo:
```text
Q4 2026
O1 — Provar aquisição escalável
71% 🟡
KR1 CAC X→Y                  62%
KR2 Payback X→Y              78%
KR3 CM-LTV90/CAC X→Y         73%
O2 — Outcome previsível
81% 🟢
O3 — Provar LTV pós-core
44% 🔴
```
Cada KR precisa ter:
* baseline;
* meta;
* atual;
* owner;
* tendência;
* confidence;
* linked metrics;
* linked experiments.
---
# 21. STRATEGIC BETS BOARD
Formato portfólio:
| Bet            | Horizonte | Stage     | Capital | Evidence  | Status |
| -------------- | --------- | --------- | ------: | --------- | ------ |
| Core Launch    | Core      | Scale     |    alto | forte     | 🟢     |
| Paid Entry     | Adjacent  | Prove     |   médio | crescente | 🟡     |
| Guild          | Adjacent  | Find      |   baixo | inicial   | 🔵     |
| Talent Network | Explore   | Find      |   baixo | baixa     | ⚪      |
| B2B            | Explore   | Discovery |   baixo | inicial   | 🔵     |
---
# 22. TELA 02 — MCI / 4DX
Tela dedicada.
---
# 23. SCOREBOARD PRINCIPAL
Mostrar:
```text
X -------------------- ATUAL --------------- Y
74                     61                    50 dias
```
E:
```text
SEM 1
SEM 2
SEM 3
...
SEM 12
```
Com trajetória necessária versus real.
---
# 24. LEAD MEASURES
Cada uma com:
* meta;
* real;
* streak;
* owner;
* ações desta semana.
Exemplo:
```text
LM1 Paid Entry Activation
Meta semanal:
72%
Atual:
76%
Streak:
4 semanas
Owner:
Growth
```
---
# 25. COMMITMENT LOG
Tabela:
| Owner    | Compromisso      | Status      | Impacto | Aprendizado |
| -------- | ---------------- | ----------- | ------- | ----------- |
| Growth   | testar variant C | Done        | alto    | positivo    |
| Checkout | corrigir PIX     | In progress | alto    | —           |
| CS       | onboarding pilot | Done        | médio   | positivo    |
Isso torna accountability explícito.
---
# 26. TELA 03 — CURRENT CONSTRAINT
Uma tela inteira só para o gargalo dominante.
---
# 27. CONSTRAINT MAP
Visualizar sistema inteiro:
```text
TRAFFIC
100%
  ↓
LEAD
14%
  ↓
QUALIFIED
38%
  ↓
PAID ENTRY
11%
  ↓
CORE OFFER
65%
  ↓
CHECKOUT
24%
  ↓
PURCHASE
18,9% ← CONSTRAINT
```
---
# 28. THROUGHPUT IMPACT
Mostrar:
```text
Se checkout voltar a 24,8%:
+63 buyers
+R$81k net revenue
+R$49k contribution
-9 dias payback
```
É importante mostrar impacto sistêmico, não apenas percentual.
---
# 29. ROOT CAUSE TREE
```text
Checkout Conversion ↓
│
├── Device
│   ├── Mobile Android 🔴
│   └── Desktop 🟢
│
├── Payment
│   ├── PIX 🔴
│   ├── Card 🟡
│   └── Other 🟢
│
├── Browser
│
├── Campaign
│
├── Offer
│
└── Technical Events
```
---
# 30. CONSTRAINT ACTION BOARD
Separar ações segundo TOC:
```text
EXPLOIT
SUBORDINATE
ELEVATE
```
Exemplo:
### EXPLOIT
Corrigir erro PIX.
### SUBORDINATE
Não aumentar tráfego high-intent.
### ELEVATE
Rearquitetar payment flow.
---
# 31. TELA 04 — GROWTH LAB
Laboratório de experimentos.
---
# 32. EXPERIMENT PIPELINE
Kanban:
```text
IDEAS
↓
PRIORITIZED
↓
DESIGNED
↓
RUNNING
↓
ANALYZING
↓
DECISION
↓
ROLLED OUT
```
---
# 33. EXPERIMENT CARD
Visual:
```text
EXP-087
Simplified PIX Checkout
Hypothesis:
remover etapa intermediária aumentará confirmed payment.
Impact:
High
Confidence:
82%
Effort:
Low
ICE+:
8.7
Primary:
Checkout → Payment
Guardrails:
Refund / Error / Support
Status:
RUNNING
```
---
# 34. EXPERIMENT DETAIL
Gráficos:
* control vs variant;
* sample;
* confidence;
* effect size;
* guardrails.
Além disso:
```text
DECISION
[Roll out]
[Continue]
[Stop]
[Inconclusive]
```
---
# 35. LEARNING EXTRACTION
Ao encerrar:
```text
WHAT DID WE LEARN?
Finding:
...
Applicability:
...
Confidence:
...
Business impact:
...
Should become policy?
YES / NO
```
Isso alimenta Decision Memory.
---
# 36. TELA 05 — ACQUISITION
Mostrar aquisição com visão econômica.
Não apenas Ads Manager.
---
# 37. ACQUISITION TABLE
| Canal       | Spend | Buyers | CAC | Marginal CAC | CM30 | CM90 | Payback |
| ----------- | ----: | -----: | --: | -----------: | ---: | ---: | ------: |
| Organic     |     — |        |     |              |      |      |         |
| Meta Cold   |       |        |     |              |      |      |         |
| Retargeting |       |        |     |              |      |      |         |
| Referral    |       |        |     |              |      |      |         |
| Dream 100   |       |        |     |              |      |      |         |
---
# 38. CHANNEL QUALITY
Para cada canal:
```text
BUYER QUALITY
Activation
Outcome
Refund
Repeat Purchase
Referral
LTV90
```
Essa tela impede a empresa de adorar CPL baixo.
---
# 39. MARGINAL CAC CURVE
Gráfico:
```text
Spend
↓
CAC
```
Mostrar pontos onde eficiência começa a deteriorar.
Exemplo:
```text
R$30k → R$340
R$60k → R$390
R$100k → R$470
R$150k → R$590
```
A pergunta:
> Quanto o próximo R$1 está custando?
---
# 40. TELA 06 — FUNNEL
Visual completo:
```text
Visitors
↓
Leads
↓
Qualified Leads
↓
Paid Entry
↓
Core Offer
↓
Checkout
↓
Payment
↓
Activation
↓
Outcome
```
Diferencial:
não terminar em compra.
O funnel vai até valor ao cliente.
---
# 41. CADA ETAPA MOSTRA
* volume;
* conversion;
* delta;
* benchmark interno;
* tempo entre etapas;
* confidence;
* principal drop-off.
---
# 42. TELA 07 — COHORTS
Uma das telas mais importantes.
---
# 43. COHORT MATRIX
| Coorte           | CAC | CM30 | CM90 | CM365 | Payback | Activation | Outcome | Referral |
| ---------------- | --: | ---: | ---: | ----: | ------: | ---------: | ------: | -------: |
| Ago Organic      |     |      |      |       |         |            |         |          |
| Ago Meta         |     |      |      |       |         |            |         |          |
| Ago VIP          |     |      |      |       |         |            |         |          |
| Sep Paid Entry A |     |      |      |       |         |            |         |          |
---
# 44. HEATMAP
Células visualmente indicam:
* excelente;
* saudável;
* atenção;
* ruim.
Não usar cor sem número e contexto.
---
# 45. COHORT DETAIL
Selecionar:
```text
Meta Cold — Agosto/2026
```
Mostrar:
```text
D0
D7
D30
D90
D180
D365
```
Para:
* revenue;
* contribution;
* repeat purchases;
* outcome;
* referral.
---
# 46. TELA 08 — UNIT ECONOMICS
Painel econômico puro.
---
# 47. ECONOMIC WATERFALL
```text
Gross Revenue
R$ 500.000
    ↓
Refund
-R$ 18.000
    ↓
Taxes
-R$ X
    ↓
Gateway
-R$ X
    ↓
Commission
-R$ X
    ↓
Variable Delivery
-R$ X
    ↓
Contribution Margin
R$ XXX.XXX
```
---
# 48. LTV CURVE
```text
D0
D7
D30
D90
D180
D365
```
Mostrar:
* Revenue LTV;
* CM-LTV.
Nunca misturar os dois.
---
# 49. PAYBACK CURVE
Visual:
```text
-R$ CAC
↓
recuperação gradual
↓
ZERO
↓
contribution positiva
```
Mostrar:
```text
Payback day = 61
```
---
# 50. LTV:CAC
Mostrar por canal e coorte.
Não usar apenas média geral.
---
# 51. TELA 09 — CAPITAL ALLOCATION
Pergunta:
> Onde colocar o próximo real?
---
# 52. CAPITAL OPPORTUNITY TABLE
| Iniciativa   | Capital | Impacto CM | Confidence | Payback | Strategic Fit | Rank |
| ------------ | ------: | ---------: | ---------: | ------: | ------------: | ---: |
| Checkout Fix |   R$20k |    +R$150k |        90% |     14d |          alta |    1 |
| Paid Entry   |   R$40k |    +R$120k |        70% |     45d |          alta |    2 |
| Guild        |   R$60k |     +R$90k |        55% |    120d |         média |    4 |
| New Course   |   R$70k |     +R$80k |        40% |    180d |         média |    6 |
---
# 53. PORTFOLIO VIEW
Pie ou barras conceituais:
```text
CORE         65%
ADJACENT     25%
EXPLORATION  10%
```
Mostrar se estamos fora da política desejada.
---
# 54. TELA 10 — CUSTOMER VALUE
Pergunta:
> nossos alunos estão avançando?
---
# 55. LEARNING FUNNEL
```text
Purchased
↓ 88%
Onboarded
↓ 76%
Activated D7
↓ 61%
First Project
↓ 48%
Portfolio
↓ 35%
Market Ready
↓ 21%
Professional Outcome
```
---
# 56. TIME TO VALUE
Cards:
```text
Median Time to First Asset
3,2 dias
Time to First Project
11 dias
Time to Portfolio
68 dias
```
---
# 57. AT-RISK STUDENTS
Tabela:
| Aluno | Progress | Risk | Último evento  | Próxima ação |
| ----- | -------: | ---- | -------------- | ------------ |
| ...   |      12% | 🔴   | 18d sem login  | intervenção  |
| ...   |      31% | 🟡   | projeto falhou | feedback     |
---
# 58. OUTCOME COHORTS
Comparar outcome por:
* aquisição;
* produto;
* onboarding;
* versão curricular;
* instructor;
* challenge.
---
# 59. TELA 11 — RETENTION
Separar:
### Learning Retention
### Relationship Retention
### Revenue Retention
---
# 60. RETENTION CURVES
Por coorte.
Mostrar:
```text
D7
D30
D90
D180
D365
```
---
# 61. GUILD
Quando existir:
```text
MRR
New MRR
Expansion
Churn
Reactivation
NRR
Engagement
```
---
# 62. TELA 12 — GROWTH LOOPS
Tela pouco comum em infoprodutos e muito importante.
---
# 63. LOOP CARD
Exemplo:
```text
OUTCOME → CASE → CONTENT → LEAD → BUYER
Input:
100 outcomes
Cases:
32
Leads generated:
410
Buyers:
21
Amplification:
0.21 buyer per outcome
Cycle Time:
43 days
```
---
# 64. LOOP TREND
Mostrar:
```text
0.08x
0.11x
0.14x
0.18x
0.21x
```
Se cresce:
o negócio está criando aquisição endógena.
---
# 65. TELA 13 — SALES & RECOVERY
---
# 66. SALES SCOREBOARD
| Owner | Leads | Contact | Conversation | Checkout Recovery | Close | Contribution |
| ----- | ----: | ------: | -----------: | ----------------: | ----: | -----------: |
---
# 67. HIGH INTENT QUEUE
Lista ordenada por oportunidade:
```text
1. Lead A — Score 94
   2 checkout visits
   PIX failed
   R$1.497 offer
2. Lead B — Score 88
   workshop 96%
   checkout started
```
Ação:
```text
[Assumir]
[Enviar]
[Descartar]
```
---
# 68. OBJECTION MAP
Mostrar objeções:
```text
PRICE          31%
TIME           22%
PARENT         14%
TRUST          11%
EQUIPMENT       8%
OTHER          14%
```
E:
> resolução por objeção.
---
# 69. TELA 14 — SCALE GATES
Cada motor/produto passa por gates.
---
# 70. SCALE READINESS CARD
```text
PAID ENTRY B
Demand          PASS
Conversion      PASS
Economics       PASS
Delivery        PASS
Outcome         WATCH
Retention       PASS
Repeatability   PASS
Marginal CAC    WATCH
Decision:
CONTROLLED SCALE
```
---
# 71. ESTADOS DE DECISÃO
```text
DO NOT SCALE
VALIDATE
CONTROLLED SCALE
SCALE
PAUSE
ROLL BACK
```
---
# 72. TELA 15 — CAPACITY
Evitar vender mais do que a empresa consegue entregar.
---
# 73. CAPACITY MAP
```text
Sales           71%
Support         84% 🟡
Reviewers       96% 🔴
Servers         42%
Community       68%
Lívia           91% 🔴
```
Um dos cards mais importantes:
# FOUNDER CAPACITY
Porque tempo da Lívia pode virar restrição.
---
# 74. TELA 16 — TASK COMMAND CENTER
Integra o Kanban anterior.
---
# 75. VISÕES
### Kanban
### Lista
### Batches
### Dependencies
### Robots
### Review / Exception
---
# 76. CARTÃO
```text
P1
Corrigir timeout PIX mobile
Impact:
R$94k/ciclo
Related Constraint:
Checkout
Owner:
Robot Checkout-02
Status:
IN PROGRESS
Dependencies:
none
Parallelizable:
no
Lock:
active
Definition of Done:
...
```
---
# 77. BADGES
```text
P0
P1
P2
P3
ROBOT
HUMAN
BATCH
BLOCKED
REVIEW
EXPERIMENT
```
---
# 78. TELA 17 — ROBOT OPERATIONS
Um NOC para agentes.
---
# 79. ROBOT CARDS
```text
CHECKOUT AUDITOR
Status: RUNNING
Task: TSK-884
Started: 4m ago
Permissions: READ + PATCH staging
Risk: LOW
DATA AUDITOR
Status: WAITING REVIEW
```
---
# 80. FILA DE ROBÔS
```text
Running
Queued
Waiting
Review
Failed
Completed
```
---
# 81. AGENT PERFORMANCE
Para cada robô:
* tasks completed;
* success rate;
* exceptions;
* revisions;
* mean execution;
* human rework.
---
# 82. TELA 18 — REVIEW / EXCEPTION
Essa tela merece destaque.
---
# 83. EXCEPTION CARD
```text
TSK-884
Robot:
Checkout Auditor
Problem:
Could not validate gateway callback
Tried:
1...
2...
3...
Reason:
missing credential
Evidence:
...
Risk:
HIGH
Recommended human action:
...
[Approve]
[Correct]
[Reassign]
[Reject]
```
O humano não precisa investigar do zero.
---
# 84. TELA 19 — INCIDENT CENTER
Para P0/P1.
---
# 85. INCIDENT CARD
```text
INC-2026-031
PAYMENT CALLBACK FAILURE
Severity:
P0
Started:
19:02
Revenue at risk:
R$3.400/hour
Affected:
PIX
Owner:
...
Status:
MITIGATING
```
---
# 86. INCIDENT TIMELINE
```text
19:02 detected
19:03 P0 created
19:05 checkout robot assigned
19:09 rollback initiated
19:13 conversion recovering
```
---
# 87. POST-INCIDENT
Após resolver:
```text
Root Cause
Impact
Detection
Response
Prevention
Tasks
```
---
# 88. TELA 20 — DATA QUALITY
Sem confiança nos dados, todo o resto degrada.
---
# 89. DATA QUALITY SCORE
```text
DATA RELIABILITY
96/100
```
Componentes:
* completeness;
* consistency;
* reconciliation;
* event health;
* identity match.
---
# 90. RECONCILIATION
```text
Gateway purchases        203
Enrollments              202
CRM buyers               202
Analytics purchase       197
Exceptions:
6
```
Ações:
```text
[Investigar]
[Gerar tarefas]
```
---
# 91. TELA 21 — DECISION MEMORY
Um dos ativos mais valiosos.
---
# 92. DECISION LOG
| Data  | Decisão     | Evidência | Esperado | Real | Status    |
| ----- | ----------- | --------- | -------- | ---- | --------- |
| 12/08 | preço 1297  | teste     | +CM      | ...  | validated |
| 19/08 | remove bump | cohort    | -refund  | ...  | mixed     |
---
# 93. DECISION DETAIL
Mostrar:
```text
Context
Alternatives
Assumptions
Evidence
Decision
Expected outcome
Review date
Actual outcome
Learning
```
---
# 94. TELA 22 — VALIDATED LEARNINGS
Biblioteca de aprendizado.
Categorias:
```text
Acquisition
Offer
Pricing
Checkout
Sales
Learning
Retention
Community
B2B
```
---
# 95. LEARNING CARD
```text
LEARNING-092
Paid Entry buyers from Variant C
produce 41% higher CM-LTV90.
Confidence:
High
Evidence:
3 cohorts
Applies to:
Brazil / cold traffic
Policy:
Increase allocation gradually.
```
---
# 96. TELA 23 — WEEKLY SCALE REVIEW
A própria reunião acontece dentro do painel.
---
# 97. MODO REUNIÃO
Botão:
# START WEEKLY REVIEW
O sistema entra em sequência guiada.
---
# 98. PASSO 1
North Stars.
30–60 segundos.
---
# 99. PASSO 2
MCI + Lead Measures.
---
# 100. PASSO 3
Commitments anteriores.
Cada owner marca:
```text
DONE
PARTIAL
NOT DONE
```
---
# 101. PASSO 4
12 KPIs.
Só desvios.
---
# 102. PASSO 5
Current Constraint.
---
# 103. PASSO 6
Experiments.
---
# 104. PASSO 7
Decisions.
---
# 105. PASSO 8
New Commitments.
Ao final:
o sistema automaticamente cria:
* tarefas;
* owners;
* datas;
* decisão registrada.
---
# 106. TELA 24 — MBR
Modo de reunião mensal.
---
# 107. MBR SECTIONS
```text
01 Financial
02 Growth
03 Acquisition
04 Cohorts
05 Customer Value
06 Retention
07 Experiments
08 Operations
09 Capacity
10 Forecast
11 Capital Allocation
```
---
# 108. MBR AUTO-BRIEF
Antes da reunião:
IA gera:
```text
TOP 5 positive changes
TOP 5 negative changes
3 structural risks
3 leverage opportunities
major cohort changes
forecast variance
```
---
# 109. TELA 25 — QBR
Trimestral.
---
# 110. QBR FLOW
```text
Score OKRs
↓
Review MCI
↓
Review Economics
↓
Review Outcomes
↓
Review Strategic Bets
↓
Review Constraints
↓
Review Learnings
↓
Kill / Continue / Scale
↓
Capital Allocation
↓
New OKRs
↓
New MCI
```
---
# 111. STOP DOING SECTION
Obrigatória.
```text
WHAT WILL WE STOP?
[ ] Campaign
[ ] Feature
[ ] Meeting
[ ] Product
[ ] Experiment line
[ ] Tool
```
Scale exige remoção.
---
# 112. TELA 26 — FORECAST & SCENARIOS
---
# 113. FORECAST
Mostrar:
```text
30d
60d
90d
```
Com:
```text
Expected
Lower Bound
Upper Bound
```
Para:
* buyers;
* revenue;
* contribution;
* cash;
* CAC;
* payback.
---
# 114. SCENARIO SLIDERS
Exemplo:
```text
Ad Spend      +30%
Conversion    +10%
CAC           +15%
Price         +5%
Refund        -1pp
```
Painel recalcula cenário.
---
# 115. TELA 27 — METRICS REGISTRY
Governança.
---
# 116. METRIC DETAIL
```text
Buyer CAC
Definition:
...
Formula:
...
Numerator:
...
Denominator:
...
Source:
...
Owner:
...
Version:
v2
Confidence:
98%
```
---
# 117. TELA 28 — SYSTEM HEALTH
Para engenharia/robôs.
---
# 118. EVENT PIPELINE
```text
Events/min
Failed events
Queue lag
Webhook failures
DLQ
Processing delay
```
---
# 119. DOMAIN HEALTH
```text
Checkout        🟢
Students        🟢
Leads           🟢
Revenue         🟢
Analytics       🟡
Automation      🟢
```
---
# 120. GLOBAL SEARCH
Busca universal.
Exemplos:
```text
buscar cliente
buscar pedido
buscar experimento
buscar decisão
buscar métrica
buscar tarefa
buscar incidente
```
---
# 121. COMMAND PALETTE
Atalho:
```text
CTRL + K
```
Comandos:
```text
Criar tarefa
Criar experimento
Abrir Current Constraint
Abrir cliente
Registrar decisão
Iniciar Weekly Review
```
---
# 122. CONTEXT DRAWER
Ao clicar em qualquer elemento:
painel lateral abre.
Sem perder contexto.
Exemplo:
clicar no CAC abre:
```text
Definition
Trend
Drivers
Cohorts
Experiments
Tasks
Owner
```
---
# 123. DRILL-DOWN RULE
Todo KPI precisa permitir:
```text
GLOBAL
↓
CHANNEL
↓
CAMPAIGN
↓
CREATIVE
↓
COHORT
↓
CUSTOMER
```
Ou equivalente por domínio.
---
# 124. TIME COMPARISON
Permitir:
```text
vs last week
vs 4-week average
vs previous launch
vs same cohort age
vs target
```
"Ontem versus hoje" pode ser enganoso.
---
# 125. CONFIDENCE BADGES
Mostrar:
```text
HIGH
MEDIUM
LOW
```
Especialmente em:
* atribuição;
* forecasts;
* IA;
* causalidade;
* LTV projetado.
---
# 126. FACT / HYPOTHESIS DISTINCTION
Nunca misturar.
Exemplo:
```text
FACT
PIX failures +31%.
HYPOTHESIS
Callback latency may be causing failures.
CONFIDENCE
68%.
```
---
# 127. ALERT PHILOSOPHY
Alertas só aparecem quando:
```text
Magnitude
×
Persistence
×
Business Impact
×
Confidence
```
superam threshold.
---
# 128. ALERT CATEGORIES
```text
ECONOMIC
GROWTH
PRODUCT
CUSTOMER
TECHNICAL
DATA
CAPACITY
```
---
# 129. ALERT ACTIONS
Cada alerta oferece:
```text
[Acknowledge]
[Investigate]
[Create Task]
[Assign Robot]
[Dismiss]
```
---
# 130. VISUAL LANGUAGE
Não usar cores apenas decorativas.
Sugestão conceitual:
```text
GREEN   healthy
YELLOW  watch
RED     action
BLUE    experiment
GRAY    inactive/not started
PURPLE  AI insight
```
Mas usar simultaneamente:
* ícone;
* texto;
* número.
Nunca depender apenas da cor.
---
# 131. CARD PRIORITY
Cards devem refletir importância.
Maior:
* MCI;
* Current Constraint;
* North Stars.
Menor:
* métricas secundárias.
Hierarquia visual é hierarquia estratégica.
---
# 132. NOISE REDUCTION
Não mostrar métricas que não alterem decisão.
Pergunta para cada card:
> Se este número mudar, alguém fará algo diferente?
Se não:
mover para drill-down.
---
# 133. PERSONALIZATION POR FUNÇÃO
CEO vê:
* estratégia;
* economics;
* constraint;
* capital.
Growth vê:
* funnel;
* campaigns;
* experiments.
Education vê:
* activation;
* competencies;
* outcomes.
Tech vê:
* incidents;
* data;
* robots.
Mesmo banco.
Diferentes lentes.
---
# 134. ROLE-BASED DEFAULT HOME
```text
CEO → Command Center
Growth → Growth Cockpit
Finance → Economics
Education → Customer Value
Tech → Operations
```
---
# 135. MOBILE VIEW
Mobile não tenta replicar painel inteiro.
Mostrar:
```text
Health
MCI
Current Constraint
Critical Alerts
Approvals
```
Mobile serve para decisão rápida.
Desktop para análise.
---
# 136. NOTIFICATION CENTER
Somente:
* approvals;
* P0/P1;
* broken commitments;
* review exceptions;
* completed critical experiments.
Não gerar notificações para tudo.
---
# 137. APPROVAL INBOX
Fila única:
```text
Price Change
Experiment Rollout
Robot Action
Budget Increase
Refund Exception
B2B Proposal
```
---
# 138. EXECUTIVE INBOX
Outra visualização importante:
# WHAT NEEDS MY DECISION?
Exemplo:
```text
3 decisions pending
1. Roll out EXP-087?
   Estimated +R$31k/cycle
2. Increase Meta budget 20%?
   Current gate: Marginal CAC WATCH
3. Approve robot patch?
   Risk: Low
```
Excelente para Anderson não virar gargalo.
---
# 139. BOTTLENECK: FOUNDER
O sistema deve monitorar também:
```text
Founder approvals waiting
Founder tasks overdue
Decisions waiting
Lívia capacity
```
Porque fundador frequentemente vira a própria restrição.
---
# 140. FOUNDER LOAD
Exemplo:
```text
LÍVIA
Content commitments:
82%
Teaching:
71%
Approvals:
94% 🔴
Strategic tasks:
56%
Recommendation:
delegate approval category X
```
---
# 141. AI COPILOT LATERAL
Em qualquer tela:
```text
Pergunte ao Revenue Brain
```
Exemplos:
> Por que CAC subiu?
> Compare lançamento 3 e 4.
> Qual experimento deveria vir primeiro?
> Qual coorte produz melhores outcomes?
---
# 142. AI RESPONSE FORMAT
Sempre:
```text
ANSWER
EVIDENCE
CONFIDENCE
ALTERNATIVE EXPLANATIONS
RECOMMENDED NEXT STEP
```
Isso reduz falsa autoridade.
---
# 143. AI "WHAT AM I MISSING?"
Botão especial:
# RED TEAM THIS VIEW
A IA procura:
* variável omitida;
* confounder;
* métrica enganosa;
* evidência contrária;
* risco de segunda ordem.
Particularmente útil em QBR e Capital Allocation.
---
# 144. AI LEVERAGE MODE
Botão:
# FIND 10X LEVERAGE
Não significa produzir ideias fantasiosas.
Significa procurar:
* gargalo;
* nonlinearity;
* underused asset;
* high-LTV cohort;
* low-effort/high-impact change;
* loop potencial.
---
# 145. DECISION TO TASK PIPELINE
Quando decisão é aprovada:
```text
Decision
↓
Task(s)
↓
Dependencies
↓
Owner/Robot
↓
Execution
↓
Validation
↓
Learning
```
Nenhuma decisão fica órfã.
---
# 146. INSIGHT TO EXPERIMENT PIPELINE
```text
Insight
↓
Hypothesis
↓
Experiment
↓
Result
↓
Learning
↓
Policy
```
---
# 147. INCIDENT TO PREVENTION PIPELINE
```text
Incident
↓
Mitigation
↓
Root Cause
↓
Post-Mortem
↓
Prevention Task
↓
System Improvement
```
---
# 148. CUSTOMER SIGNAL TO ACTION PIPELINE
```text
Signal
↓
Risk/Opportunity Score
↓
Next Best Action
↓
Automation/Human
↓
Outcome
```
---
# 149. DASHBOARD STATES
Cada painel possui:
```text
NORMAL
WATCH
ACTION
INCIDENT
```
A UI muda prioridade conforme estado.
---
# 150. EMPTY STATE
Quando ainda não houver dados:
não inventar precisão.
Mostrar:
```text
INSUFFICIENT DATA
Required:
X
Current:
Y
Next valid read:
after N observations
```
---
# 151. DATA FRESHNESS
Cada KPI mostra:
```text
Updated 4m ago
```
ou:
```text
Delayed 3h ⚠
```
---
# 152. SOURCE LINEAGE
Tooltip:
```text
Source:
Revenue Ledger
Derived from:
Gateway + Orders + Refunds
Definition:
CM v2
```
---
# 153. AUDITABILITY
Qualquer decisão automática precisa permitir:
> Por que o sistema fez isso?
Exemplo:
```text
Task generated because:
checkout_abandoned
+
intent_score 84
+
offer_value > R$997
+
no human contact in 45m
```
---
# 154. PANEL AS OPERATING SYSTEM, NOT REPORT
A distinção final:
Um relatório diz:
> aconteceu isso.
O Scale OS pergunta:
> então o que fazemos?
---
# 155. ARQUITETURA DA HOME FINAL
Proposta visual:
```text
┌───────────────────────────────────────────────────────┐
│ SCALE HEALTH 84 | DATA 96% | MODE: PROVE            │
├───────────────────────────┬───────────────────────────┤
│ NORTH STAR: OUTCOME       │ NORTH STAR: CM           │
├───────────────────────────┴───────────────────────────┤
│               MCI / 4DX SCOREBOARD                   │
├───────────────────────────────────────────────────────┤
│ 🔴 CURRENT CONSTRAINT                                │
│ Checkout → Payment                                   │
├───────────────────────────────────────────────────────┤
│               CEO 12 KPI SCOREBOARD                  │
├───────────────────────────┬───────────────────────────┤
│ WHAT CHANGED              │ TOP LEVERAGE             │
├───────────────────────────┼───────────────────────────┤
│ RISKS                     │ GROWTH LOOPS              │
├───────────────────────────┼───────────────────────────┤
│ EXPERIMENTS               │ OPERATIONS / ROBOTS       │
├───────────────────────────┴───────────────────────────┤
│ AI EXECUTIVE BRIEF                                    │
└───────────────────────────────────────────────────────┘
```
---
# 156. ARQUITETURA DE INFORMAÇÃO EM UMA FRASE
A navegação inteira deve seguir:
# STRATEGY → PERFORMANCE → DIAGNOSIS → EXECUTION → LEARNING
Não organizar telas por departamentos simplesmente porque a empresa possui departamentos.
Organizar pela:
> **lógica de gestão.**
---
# 157. O QUE O CEO NÃO DEVERIA PRECISAR FAZER
Não deveria:
* abrir Meta Ads;
* abrir gateway;
* comparar planilhas;
* perguntar quantas vendas ocorreram;
* procurar tarefas;
* perguntar qual experimento terminou;
* perguntar qual robô está executando;
* perguntar qual é o gargalo.
Tudo isso deve chegar consolidado.
---
# 158. O QUE O CEO DEVE FAZER
Usar atenção em:
* trade-offs;
* prioridades;
* capital;
* restrições;
* strategic bets;
* decisões irreversíveis;
* cultura;
* direção.
O painel deve liberar o CEO da coleta manual de informações.
---
# 159. MVP DO PAINEL
Não construir 28 telas imediatamente.
## FASE 1 — COMMAND FOUNDATION
Construir primeiro:
### 1. Command Center
### 2. MCI / 4DX
### 3. Current Constraint
### 4. CEO Scoreboard
### 5. Tasks / Robots
### 6. Data Quality
---
# 160. FASE 2 — GROWTH
Adicionar:
* funnel;
* acquisition;
* experiments;
* sales;
* checkout.
---
# 161. FASE 3 — ECONOMICS
Adicionar:
* cohorts;
* unit economics;
* payback;
* capital allocation.
---
# 162. FASE 4 — CUSTOMER VALUE
Adicionar:
* activation;
* learning;
* outcomes;
* retention.
---
# 163. FASE 5 — STRATEGIC MANAGEMENT
Adicionar:
* OKRs;
* strategic bets;
* scale gates;
* MBR;
* QBR.
---
# 164. FASE 6 — INTELLIGENCE
Adicionar:
* AI brief;
* leverage detection;
* red team;
* forecasts;
* Next Best Action.
---
# 165. FASE 7 — ADAPTIVE SYSTEM
No estágio avançado:
o sistema aprende:
* quais alertas importam;
* quais experimentos têm maior valor;
* quais lead measures predizem MCI;
* quais sinais predizem churn;
* quais clientes respondem a qual intervenção.
---
# 166. CRITÉRIO DE SUCESSO DO PAINEL
O painel será bem-sucedido quando reduzir:
```text
TIME TO SIGNAL
↓
TIME TO DIAGNOSIS
↓
TIME TO DECISION
↓
TIME TO ACTION
↓
TIME TO LEARNING
↓
```
Esses cinco tempos são talvez mais importantes que "quantos dashboards existem".
---
# 167. NOVA MÉTRICA ORGANIZACIONAL
Criaria:
# DECISION LATENCY
Tempo entre:
> sinal relevante
e
> decisão tomada.
---
# 168. OUTRA
# EXECUTION LATENCY
Tempo entre:
> decisão
e
> início da execução.
---
# 169. OUTRA
# LEARNING LATENCY
Tempo entre:
> experimento encerrado
e
> aprendizado incorporado ao sistema.
Uma empresa que reduz esses três tempos:
> aprende e se adapta mais rápido.
---
# 170. MESHCRAFT MANAGEMENT FLYWHEEL
```text
DADOS
↓
VISIBILIDADE
↓
FOCO
↓
DECISÃO
↓
EXECUÇÃO
↓
EXPERIMENTO
↓
APRENDIZADO
↓
MELHOR SISTEMA
↓
DADOS MELHORES
↺
```
---
# 171. A TESE FINAL
O painel não deve responder apenas:
> **"Como está a empresa?"**
Ele deve responder:
> **"Qual é a próxima decisão mais importante da empresa?"**
Depois:
> **"Qual é a evidência?"**
Depois:
> **"Quem deve agir?"**
Depois:
> **"Funcionou?"**
E finalmente:
> **"O que aprendemos?"**
Quando essas cinco respostas estiverem conectadas no mesmo sistema, o Painel deixa de ser dashboard.
Torna-se:
# MESHCRAFT COMMAND & LEARNING SYSTEM
Um centro nervoso capaz de coordenar:
**estratégia + execução + growth + economics + customer outcomes + experimentação + robôs + aprendizado organizacional.**
---
# 172. RESUMO EXECUTIVO DA ARQUITETURA
A tela principal mostra:
### ONDE ESTAMOS
North Stars.
### O QUE PRECISA MUDAR
MCI.
### O QUE NOS LIMITA
Current Constraint.
### SE A ECONOMIA ESTÁ SAUDÁVEL
12 KPIs.
### O QUE MUDOU
Anomaly Engine.
### ONDE ESTÁ A MAIOR ALAVANCA
Leverage Engine.
### O QUE ESTÁ SENDO TESTADO
Growth Lab.
### O QUE PRECISA SER FEITO
Task Engine.
### QUEM ESTÁ EXECUTANDO
Humans + Robots.
### O QUE APRENDEMOS
Decision Memory.
### O QUE FAZER AGORA
Executive Decision Inbox.
Essa é a arquitetura do **Meshcraft Scale OS 1.1 — Painel**.
