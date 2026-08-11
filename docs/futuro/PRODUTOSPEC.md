> **Proposto em:** 11 de agosto de 2026, por um agente de IA analisando o
> repositório sitesdoreino já com a Fase 0 completa.
> **Depende de:** contratos reais e implementados (não 501-stub) em catalogo,
> funil, quiz, checkout, alunos e mensageria — ou seja, da Fase D concluída.
> **Decisão de sequência:** arquitetura sólida, alinhada à Lei 3 e à Lei 9 —
> generaliza "site é dado" para "produto/curso é dado". Adiado
> deliberadamente, não descartado. Revisar como Portão 0 de um brief formal
> ("Fase F — ProdutoSpec") depois que a Fase D produzir um curso real
> construído à mão — o formato exato do spec deve ser desenhado olhando para
> um sistema que já funciona, não para um que ainda não existe.

---

# PROMPT MESTRE — Implementar formalmente a camada ProdutoSpec / CourseSpec

Quero que você atue como **arquiteto principal e engenheiro sênior deste repositório** e implemente formalmente uma nova camada arquitetural chamada:

# ProdutoSpec / CourseSpec

Ela será o **DNA declarativo de cada produto da plataforma**.

O objetivo não é simplesmente criar algumas tabelas ou um JSON.

O objetivo é permitir que, no futuro, uma pessoa ou agente de IA possa dizer:

> “Crie um novo curso chamado Fundamentos do Reino, com 10 módulos, certificado, quiz, página de vendas, preço de R$197 e fluxo de boas-vindas.”

e a plataforma consiga transformar essa intenção em um **ProdutoSpec/CourseSpec validado, versionado, auditável, idempotente e publicável**, sem que o agente precise editar código-fonte de catálogo, funil, quiz, checkout, pagamentos, alunos ou mensageria.

---

# 0. PRINCÍPIO CENTRAL

A arquitetura deve fazer uma separação absoluta entre:

## A. CAPACIDADES DA PLATAFORMA

São implementadas em código:

* catalogo
* funil
* quiz
* leads
* mensageria
* alunos
* checkout
* pagamentos

Essas capacidades são permanentes.

## B. INSTÂNCIAS DO NEGÓCIO

São dados/configurações:

* Curso de Formação Pastoral
* Curso de Psicanálise
* Curso de Teologia
* Curso de Liderança
* Curso X
* Curso Y
* Produto digital Z

Criar um novo produto ou curso **NÃO deve exigir**:

* nova célula;
* nova branch;
* novo código;
* migration específica daquele curso;
* editar settings;
* editar URLs;
* editar checkout;
* editar pagamentos.

Depois que essa camada estiver pronta, o sistema deve ser capaz de cadastrar centenas ou milhares de produtos usando a mesma arquitetura.

---

# 1. ANTES DE ESCREVER QUALQUER CÓDIGO

Leia integralmente e respeite, no mínimo:

* `CONSTITUICAO.md`
* `RITOS.md`
* `INVARIANTES.md`, se existir
* `CAMINHO-DOURADO.md`
* `constituicoes/AGENTS.*`
* contratos OpenAPI relevantes
* contratos de eventos relevantes
* estrutura atual de `services/`
* testes arquiteturais existentes
* regras de imports/dependências
* CODEOWNERS
* CI existente

Antes de alterar arquivos, apresente um diagnóstico curto contendo:

1. onde essa camada deve viver;
2. por que esse local respeita as fronteiras atuais;
3. quais células serão consumidoras dela;
4. quais arquivos pretende alterar;
5. quais contratos precisam ser criados ou evoluídos;
6. quais invariantes arquiteturais serão preservadas.

IMPORTANTE:

**Não invente uma nona célula automaticamente.**

Primeiro determine se ProdutoSpec/CourseSpec deve ser uma camada de control plane, biblioteca arquitetural, módulo de aplicação, conjunto de contratos ou combinação dessas coisas.

Uma nova célula só pode ser proposta se for realmente necessária e compatível com a Constituição do projeto.

---

# 2. MODELO CONCEITUAL

Quero uma hierarquia conceitual semelhante a:

```text
ProdutoSpec
    │
    ├── CursoSpec
    ├── AssinaturaSpec          futuro
    ├── EventoSpec              futuro
    ├── MentoriaSpec            futuro
    └── ProdutoDigitalSpec      futuro
```

`ProdutoSpec` deve representar características comuns a qualquer produto.

`CourseSpec` deve ser uma especialização/composição de `ProdutoSpec`, acrescentando características educacionais.

NÃO crie duplicação desnecessária.

Preferir composição clara e schemas discriminados/versionados.

Exemplo conceitual:

```json
{
  "spec_version": "1.0",
  "kind": "course",
  "product_id": "curso_fundamentos_reino",
  "slug": "fundamentos-do-reino",
  "status": "draft",

  "identity": {},
  "catalog": {},
  "offer": {},
  "funnel": {},
  "course": {},
  "quiz": {},
  "certificate": {},
  "enrollment": {},
  "messaging": {},
  "checkout": {}
}
```

Esse exemplo é conceitual.

Não copie cegamente se houver uma representação melhor dentro da arquitetura existente.

---

# 3. PRODUTOSPEC NÃO É UM SEGUNDO BANCO DE DADOS

Esta regra é fundamental.

ProdutoSpec deve representar:

> **estado desejado e configuração declarativa**

e não duplicar indiscriminadamente todo o estado operacional das células.

Exemplo:

ProdutoSpec pode declarar:

```text
preço desejado = R$197
```

Mas não deve armazenar:

```text
pagamento #38271 = aprovado
```

ProdutoSpec pode declarar:

```text
métodos permitidos = pix + cartão
```

Mas nunca deve armazenar:

```text
access_token do Mercado Pago
secret webhook
credenciais
chaves privadas
```

ProdutoSpec pode declarar:

```text
fluxo de boas-vindas = boas_vindas_curso_v1
```

Mas não deve armazenar:

```text
email X entregue às 17:04
WhatsApp Y falhou
```

ProdutoSpec descreve a configuração.

Cada célula continua proprietária de seu estado operacional.

---

# 4. SINGLE SOURCE OF TRUTH

Defina formalmente a seguinte distinção:

## ProdutoSpec

É a fonte de verdade para a **configuração declarativa desejada do produto**.

## Células

São as fontes de verdade para o **estado operacional de seus próprios domínios**.

Não criar duas autoridades concorrentes para o mesmo estado.

Documente explicitamente essa decisão arquitetural.

---

# 5. ESTRUTURA MÍNIMA DE PRODUTOSPEC

Projete um schema formal, tipado e versionado.

Ele deve suportar pelo menos:

## Identidade

```text
spec_version
kind
product_id
slug
name
short_name opcional
status
```

O `product_id` deve ser estável.

Alterar o nome ou slug não deve mudar a identidade interna do produto.

---

## Metadados

Exemplos:

```text
title
subtitle
description
short_description
category
tags
language
image/reference
```

Não armazenar binários dentro do spec.

Usar referências/URLs/IDs conforme padrão arquitetural do projeto.

---

# 6. DINHEIRO

Nunca usar floating point para dinheiro.

Exemplo:

ERRADO:

```json
{
  "price": 197.00
}
```

PREFERIDO:

```json
{
  "amount": 19700,
  "currency": "BRL"
}
```

ou estrutura equivalente já adotada pelo projeto.

Valores monetários devem ser expressos em unidade mínima da moeda.

---

# 7. OFFER / OFERTA

ProdutoSpec deve poder declarar ofertas como:

```text
offer_id
price
currency
original_price opcional
installments opcional
order_bumps
upsells futuramente
active_from
active_until
status
```

Evitar incorporar lógica complexa de checkout dentro do ProdutoSpec.

O spec declara a configuração comercial desejada.

Checkout continua sendo responsável pela execução do pedido.

Pagamentos continua sendo responsável pela cobrança.

---

# 8. COURSESPEC

Para `kind = course`, adicionar uma seção educacional.

Exemplo conceitual:

```text
course:
    course_id
    title
    description
    instructor_refs
    estimated_duration
    access_duration
    modules
```

Cada módulo poderá conter:

```text
module_id
title
position
description
lessons
```

Cada aula poderá conter:

```text
lesson_id
title
position
type
content_ref
duration
preview
```

Tipos futuros podem incluir:

```text
video
text
audio
pdf
quiz
live
assignment
external
```

IMPORTANTE:

Não armazenar vídeos, PDFs ou grandes conteúdos diretamente dentro do ProdutoSpec.

Utilizar referências.

---

# 9. IDs ESTÁVEIS

Não depender do título como identidade.

Exemplo:

```text
course_id = crs_01...
module_id = mod_01...
lesson_id = les_01...
offer_id = off_01...
```

ou padrão equivalente consistente com o sistema.

Renomear:

```text
“Módulo 1”
```

para:

```text
“Fundamentos do Reino”
```

não pode criar um módulo novo acidentalmente.

---

# 10. QUIZ

CourseSpec deve poder declarar:

```text
quiz:
    enabled
    quiz_ref
    required
    passing_score
```

ou, se arquiteturalmente apropriado, um sub-spec declarativo capaz de pedir a criação de um quiz.

NÃO permita que ProdutoSpec escreva diretamente no banco da célula quiz.

Toda interação precisa respeitar contratos.

---

# 11. CERTIFICADO

CourseSpec deve prever formalmente:

```text
certificate:
    enabled
    template_ref
    title
    eligibility_rules
```

Não implemente um sistema completo de certificados se isso ainda não fizer parte do escopo atual.

Mas faça o schema nascer preparado para isso.

Evitar campos vagos como:

```text
certificate_data: {}
```

Prefira estrutura tipada e extensível.

---

# 12. MATRÍCULA / ACESSO

CourseSpec deve poder declarar regras como:

```text
enrollment:
    access_duration_days
    start_policy
    expiration_policy
```

A célula alunos continua sendo proprietária das matrículas reais.

CourseSpec descreve apenas a política/configuração.

---

# 13. MENSAGERIA

O spec deve permitir referenciar fluxos:

```text
messaging:
    welcome_flow_ref
    purchase_approved_flow_ref
    course_completed_flow_ref
```

Não copiar templates inteiros de email/WhatsApp se eles pertencerem ao domínio de mensageria.

Usar referências estáveis.

---

# 14. FUNIL

O ProdutoSpec deve conseguir associar o produto a uma configuração de funil:

```text
funnel:
    template_ref
    landing_page_slug
    content/config
```

Como `funil` é stateless na arquitetura atual, respeite rigorosamente essa decisão.

Não introduza banco nessa célula apenas para implementar ProdutoSpec.

Se for necessário armazenar configuração de páginas, determine o local correto sem violar essa propriedade.

---

# 15. CHECKOUT

ProdutoSpec pode declarar parâmetros permitidos do produto/oferta.

Por exemplo:

```text
checkout:
    offer_ref
    allowed_payment_methods
    success_destination
```

Mas:

**ProdutoSpec não implementa pedido.**

**ProdutoSpec não implementa cobrança.**

**ProdutoSpec não conhece internals de Mercado Pago.**

**ProdutoSpec nunca recebe credenciais.**

---

# 16. PAGAMENTOS É UMA FORTALEZA

Nenhuma implementação de ProdutoSpec pode:

* importar internals de `services/pagamentos`;
* escrever diretamente em suas tabelas;
* inserir credenciais;
* manipular webhooks;
* alterar estados financeiros;
* criar payment intents diretamente por acesso interno;
* contornar seu contrato público.

ProdutoSpec só pode expressar configurações permitidas pelo contrato.

Qualquer ação operacional de pagamento continua dentro da célula pagamentos.

---

# 17. COMPILADOR / PROVISIONADOR DE SPECS

Quero que você avalie e implemente uma abstração formal que podemos chamar conceitualmente de:

```text
ProductSpec Compiler
```

ou:

```text
Product Provisioner
```

A nomenclatura pode ser adaptada ao padrão do projeto.

Sua responsabilidade é transformar:

```text
ProdutoSpec
```

em:

```text
plano de alterações desejadas
```

e posteriormente aplicar esse plano utilizando SOMENTE os contratos permitidos.

Fluxo conceitual:

```text
ProdutoSpec
     ↓
parse
     ↓
schema validation
     ↓
semantic validation
     ↓
PLAN
     ↓
adapters por capacidade
     ↓
APPLY
     ↓
VERIFY
     ↓
PUBLISH
```

---

# 18. IMPLEMENTAR MODO VALIDATE

Preciso conseguir executar algo equivalente a:

```text
product-spec validate arquivo.json
```

ou API/comando equivalente.

Deve verificar:

* schema;
* versão;
* tipos;
* campos obrigatórios;
* IDs;
* slugs;
* moeda;
* referências;
* incompatibilidades;
* regras semânticas;
* campos proibidos;
* segredos;
* dependências ausentes.

Resultado:

```text
VALID ✅
```

ou erros claros e apontando os campos específicos.

---

# 19. IMPLEMENTAR MODO PLAN

Antes de realizar mudanças, devo conseguir perguntar:

```text
O que este spec fará?
```

Exemplo:

```text
PLAN

CATALOGO
+ criar produto curso_fundamentos_reino
+ criar oferta oferta_principal

FUNIL
+ configurar landing page fundamentos-do-reino

QUIZ
+ associar quiz certificacao_reino

ALUNOS
+ configurar acesso de 365 dias

MENSAGERIA
+ associar fluxo boas_vindas_v1

CHECKOUT
+ disponibilizar oferta principal

PAGAMENTOS
= nenhuma mudança estrutural
```

O PLAN não pode produzir efeitos colaterais.

---

# 20. IMPLEMENTAR DRY-RUN

Quero suporte formal a:

```text
--dry-run
```

Dry-run deve:

* validar;
* gerar plano;
* mostrar diferenças;
* não persistir alterações;
* não publicar nada;
* não enviar mensagens;
* não cobrar;
* não matricular.

---

# 21. IDEMPOTÊNCIA

Esta é uma exigência crítica.

Aplicar o mesmo ProdutoSpec duas vezes:

```text
apply(spec)
apply(spec)
```

deve resultar no mesmo estado que:

```text
apply(spec)
```

Nunca:

```text
2 produtos
2 cursos
2 ofertas
2 quizzes
2 matrículas
```

Implementar e testar idempotência.

Sempre preferir operações do tipo:

```text
ensure desired state
```

em vez de:

```text
create blindly
```

---

# 22. VERSIONAMENTO

ProdutoSpec deve nascer versionado.

Separar claramente:

## versão do schema

Exemplo:

```text
spec_version: "1.0"
```

de:

## revisão daquele produto

Exemplo:

```text
revision: 7
```

ou equivalente.

Isso permitirá futuramente:

```text
ProdutoSpec schema 1.0
ProdutoSpec schema 2.0
```

sem quebrar produtos antigos.

---

# 23. HISTÓRICO E AUDITORIA

Toda alteração importante deve poder responder:

```text
quem?
quando?
qual versão anterior?
qual versão nova?
o que mudou?
```

Implementar histórico/auditoria segundo os padrões já existentes no projeto.

Não inventar infraestrutura pesada se já houver solução equivalente.

---

# 24. ESTADOS

Adotar lifecycle explícito.

No mínimo avaliar:

```text
draft
validated
published
archived
```

ou nomenclatura equivalente.

Regra:

**produto inválido nunca pode virar published.**

---

# 25. PUBLICAÇÃO SEGURA

Não quero um cenário assim:

```text
catalogo criado ✅
funil criado ✅
quiz falhou ❌
checkout já publicou produto 😱
```

Projete um mecanismo seguro de publicação.

Preferência conceitual:

```text
PREPARE
↓
todas as capacidades configuradas em estado não público
↓
VERIFY
↓
tudo válido?
↓
ACTIVATE/PUBLISH
```

Se uma etapa intermediária falhar, o produto não deve ficar parcialmente publicado ao usuário.

Não implemente uma transação distribuída ingênua através de bancos independentes.

Use estratégia apropriada à arquitetura, como:

* staged activation;
* saga;
* compensating actions;
* desired-state reconciliation;

conforme fizer mais sentido.

Documente a escolha.

---

# 26. RECONCILIAÇÃO

Quero preparar a arquitetura para o seguinte comportamento:

```text
Estado desejado:
preço = 19700

Estado atual:
preço = 9700

Resultado:
DRIFT DETECTED
```

E permitir futuramente:

```text
reconcile
```

para aproximar o estado atual do estado desejado.

Para V1, implemente pelo menos a abstração ou foundation necessária para comparação:

```text
desired state
vs
actual state
```

---

# 27. DIFF

Ao atualizar um produto existente, gerar diferença legível.

Exemplo:

```text
Course: fundamentos-do-reino

~ price:
    19700 → 29700

+ module:
    escatologia

~ certificate.template:
    ministerial-v1 → ministerial-v2

= quiz:
    unchanged
```

Não exigir que um humano examine um JSON gigante para saber o que mudará.

---

# 28. SEGURANÇA

ProdutoSpec deve rejeitar campos ou conteúdo que pareçam conter:

* passwords;
* API keys;
* tokens;
* private keys;
* Mercado Pago access tokens;
* webhook secrets;
* database URLs;
* secrets equivalentes.

Não confiar apenas em documentação.

Adicionar validação/testes para impedir que secrets conhecidos sejam incluídos na estrutura.

---

# 29. SCHEMAS FORMAIS

Quero schemas machine-readable e versionados.

Avalie o padrão já usado no projeto.

Pode ser, conforme arquitetura:

* JSON Schema;
* Pydantic;
* OpenAPI component;
* dataclasses tipadas;
* combinação apropriada.

Preferência:

um schema canônico deve poder alimentar:

```text
validação
documentação
API
geração de formulário
agentes de IA
testes
```

Evite manter cinco definições manuais diferentes do mesmo ProdutoSpec.

---

# 30. JSON SCHEMA PARA AGENTES DE IA

Uma meta importante é permitir futuramente que agentes produzam ProdutoSpecs usando structured output.

Portanto o schema deve ser:

* explícito;
* determinístico;
* fortemente tipado;
* com enums;
* com descrições;
* com limites;
* com required fields;
* com `additionalProperties: false` quando apropriado;
* sem estruturas genéricas excessivas.

Evitar:

```json
{
  "config": {}
}
```

quando pudermos dizer exatamente quais propriedades existem.

---

# 31. EXTENSIBILIDADE

O V1 deve suportar cursos.

Mas não quero codificar o mundo inteiro assumindo:

```text
produto == curso
```

Preparar para:

```text
course
digital_product
subscription
mentoring
event
```

futuramente.

Não implementar todos agora.

Apenas tornar a arquitetura extensível.

---

# 32. NÃO CRIAR UMA “GOD CLASS”

Não quero:

```text
ProductSpecService.py
5000 linhas
```

que conheça tudo.

Criar abstrações coesas.

Conceitualmente:

```text
ProductSpec
      │
      ├── validator
      ├── planner
      ├── differ
      ├── compiler
      └── adapters
               ├── catalogo
               ├── funil
               ├── quiz
               ├── alunos
               ├── mensageria
               └── checkout
```

Mas adapte ao desenho arquitetural vigente.

---

# 33. ADAPTERS NÃO PODEM FURAR AS MURALHAS

Se existir algo semelhante a:

```text
CatalogoAdapter
QuizAdapter
CheckoutAdapter
```

eles NÃO podem fazer:

```python
from services.catalogo.models import Produto
```

a partir de uma camada externa, se isso violar as regras arquiteturais.

Use:

```text
HTTP/API
eventos
contratos
interfaces públicas
```

conforme estabelecido pela Constituição.

Nunca transforme adapters em atalhos para acesso direto aos internals.

---

# 34. ATUALIZAÇÃO DE CURSO EXISTENTE

Esta funcionalidade é fundamental.

Exemplo:

Já existe:

```text
Curso Formação Pastoral
revision = 4
```

Quero aplicar:

```text
revision = 5
```

alterando:

```text
preço
imagem
módulo 7
certificado
```

Resultado correto:

```text
MESMO produto
MESMO course_id

oferta atualizada
módulo atualizado
certificado atualizado
```

Resultado ERRADO:

```text
novo curso duplicado
nova oferta duplicada
novo slug aleatório
```

Criar testes específicos para atualização.

---

# 35. CONCORRÊNCIA

Evitar que dois agentes atualizem simultaneamente o mesmo produto e o último silenciosamente destrua o trabalho do primeiro.

Implementar mecanismo apropriado, por exemplo:

```text
expected_revision
```

ou optimistic locking equivalente.

Exemplo:

```text
atual = revision 7
agente tenta aplicar revision baseada na 6
→ CONFLICT
```

Nunca sobrescrever silenciosamente.

---

# 36. EXEMPLOS REAIS

Criar fixtures/exemplos válidos.

No mínimo:

### Produto mínimo

Curso simples, sem quiz nem certificado.

### Curso completo

Exemplo:

```text
Fundamentos do Reino
10 módulos
40 aulas
R$197
quiz final
certificado
funil
mensageria
365 dias de acesso
```

### Atualização

Revision 2 alterando preço e adicionando módulo.

### Spec inválido

Contendo erro estrutural.

### Spec contendo secret

Deve ser rejeitado.

---

# 37. API / INTERFACE ADMINISTRATIVA

Preparar uma interface segura para que, futuramente, agentes autorizados possam operar:

```text
validate
plan
apply
get
diff
publish
archive
```

Não exponha endpoints administrativos sem autenticação/autorização apropriada.

Se a camada administrativa ainda não existir, implemente a foundation sem inventar um sistema de autenticação improvisado.

Documente o que ficará para uma fase futura.

---

# 38. PRINCÍPIO DE MENOR PRIVILÉGIO PARA AGENTES

No futuro teremos dois tipos de agentes:

## ENGINEERING AGENTS

Podem alterar código via:

```text
worktree
branch
CI
PR
```

## OPERATIONAL AGENTS

Podem criar produtos usando ProdutoSpec.

Eles NÃO devem ter permissão de editar:

```text
services/**
infra
settings
pagamentos internals
contracts críticos
```

ProdutoSpec deve permitir que esses agentes operem a plataforma sem acesso ao código-fonte.

Leve isso em consideração na API e no desenho da camada.

---

# 39. FLUXO FUTURO QUE A ARQUITETURA PRECISA POSSIBILITAR

Quero chegar posteriormente a:

```text
HUMANO
  │
  │ "Crie um curso de Teologia do Reino"
  ↓
AGENTE IA
  │
  ↓
gera CourseSpec
  │
  ↓
VALIDATE
  │
  ↓
PLAN
  │
  ↓
HUMANO APROVA
  │
  ↓
APPLY
  │
  ↓
VERIFY
  │
  ↓
PUBLISH
  │
  ├──── catálogo
  ├──── funil
  ├──── quiz
  ├──── checkout
  ├──── alunos
  └──── mensageria
```

Nenhum agente operacional precisa editar código.

---

# 40. TESTES OBRIGATÓRIOS

Adicionar testes cobrindo pelo menos:

1. ProdutoSpec mínimo válido;
2. CourseSpec completo válido;
3. campo obrigatório ausente;
4. campo desconhecido indevido;
5. versão de schema incompatível;
6. moeda inválida;
7. valor monetário inválido;
8. slug inválido;
9. referência inexistente;
10. tentativa de inserir secret;
11. `validate` sem efeitos colaterais;
12. `plan` sem efeitos colaterais;
13. `dry-run` sem efeitos colaterais;
14. apply cria produto;
15. apply repetido é idempotente;
16. atualização altera produto existente;
17. atualização não cria duplicata;
18. conflito de revision é detectado;
19. falha intermediária não publica produto parcialmente;
20. produto inválido não publica;
21. diff identifica alterações corretamente;
22. CourseSpec não acessa internals de pagamentos;
23. muralhas arquiteturais continuam verdes;
24. contratos existentes continuam verdes;
25. CI completo continua verde.

---

# 41. DOCUMENTAÇÃO

Criar documentação arquitetural explicando:

```text
O que é ProdutoSpec?
O que é CourseSpec?
O que não pertence a eles?
Quem é dono de cada dado?
Como criar um produto?
Como atualizar?
Como validar?
Como fazer dry-run?
Como gerar plan?
Como aplicar?
Como publicar?
Como arquivar?
Como versionar?
Como recuperar conflitos?
Como agentes de IA devem utilizar?
```

Adicionar também um diagrama textual semelhante a:

```text
                      ProdutoSpec
                           │
                    Spec Compiler
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
       catálogo          funil             quiz
          │                                  │
          └────────────┐       ┌─────────────┘
                       ↓       ↓
                       checkout
                          │
                          ↓
                      pagamentos
                          │
                          ↓
                        alunos
                          │
                          ↓
                      mensageria
```

Corrija o diagrama conforme os contratos reais do projeto.

ProdutoSpec não deve necessariamente conversar diretamente com pagamentos.

---

# 42. NÃO OVERENGINEER

Quero uma foundation forte, mas não quero Kubernetes conceitual dentro de uma funcionalidade simples.

Para V1 priorizar:

```text
schema
validation
versioning
IDs estáveis
idempotência
plan
dry-run
diff
apply
publication safety
auditabilidade
testes
documentação
```

Não implementar agora, salvo se já houver infraestrutura:

```text
Kafka
event sourcing completo
workflow engine externo
distributed transaction manager
novo message broker
nova database
```

---

# 43. MIGRAÇÕES

Se migrations forem necessárias:

* pequenas;
* reversíveis quando possível;
* sem dados específicos de um curso;
* sem hardcode de produto;
* sem acoplar células.

NUNCA criar migration:

```text
0007_create_formacao_pastoral.py
```

Curso é dado.

Não arquitetura.

---

# 44. COMPATIBILIDADE

Nada desta implementação pode quebrar:

```text
catalogo
funil
quiz
leads
mensageria
alunos
checkout
pagamentos
```

ProdutoSpec nasce **sobre** as capacidades existentes.

Não reescreva células inteiras para acomodá-lo.

---

# 45. DEFINITION OF DONE

A tarefa só está concluída quando existir evidência de:

```text
[ ] ProdutoSpec formal e versionado
[ ] CourseSpec formal
[ ] schema machine-readable
[ ] validação estrutural
[ ] validação semântica
[ ] IDs estáveis
[ ] valores monetários seguros
[ ] lifecycle
[ ] revision/version
[ ] optimistic concurrency ou equivalente
[ ] plan
[ ] dry-run
[ ] diff
[ ] idempotência
[ ] apply
[ ] publicação segura
[ ] proteção contra secrets
[ ] exemplos
[ ] documentação
[ ] testes
[ ] muralhas arquiteturais verdes
[ ] contratos verdes
[ ] CI verde
```

---

# 46. PROVA, NÃO PROMESSA

Ao finalizar, execute todos os checks relevantes.

No mínimo:

```text
make ci
```

e quaisquer:

```text
contrato-check
lint-imports
mypy
pytest
architectural tests
```

aplicáveis.

Mostre a saída real.

Não diga simplesmente:

> “Tudo funciona.”

Quero evidência.

---

# 47. HANDOFF

Ao final entregue:

## Arquitetura adotada

Explique em poucas linhas onde ProdutoSpec ficou e por quê.

## Arquivos criados

Lista completa.

## Arquivos alterados

Lista completa.

## Contratos

Quais foram criados ou modificados.

## Persistência

Explique exatamente onde fica:

```text
desired state
```

e onde cada tipo de:

```text
operational state
```

continua vivendo.

## Segurança

Explique por que ProdutoSpec não consegue furar pagamentos ou outras células.

## Testes

Liste os cenários implementados.

## CI

Cole a evidência.

## Pendências

Liste explicitamente qualquer parte propositalmente deixada para outra fase.

---

# 48. REGRA DE OURO

Durante toda a implementação aplique esta regra:

> **Criar um novo produto deve ser uma operação de dados. Criar uma nova capacidade deve ser uma operação de engenharia.**

Se, depois desta implementação, para criar o segundo curso eu ainda precisar modificar código-fonte, a arquitetura não cumpriu sua missão.

---

# 49. CENÁRIO FINAL DE ACEITAÇÃO

Quero poder provar conceitualmente o sistema com este teste.

Produto A já existe:

```text
Formação Pastoral
```

Então forneço um CourseSpec completamente diferente:

```text
product_id: curso_psicanalise
name: Psicanálise Clínica
price: R$297
12 módulos
49 aulas
certificado ativo
quiz ativo
landing page própria
fluxo de boas-vindas próprio
```

O sistema deve ser capaz de:

```text
VALIDATE
→ verde

PLAN
→ mostra exatamente o que será criado

DRY-RUN
→ nenhuma alteração

APPLY
→ cria/configura os recursos necessários

VERIFY
→ confirma consistência

PUBLISH
→ disponibiliza o novo curso
```

sem:

```text
alterar código
criar nova célula
duplicar o curso existente
mexer em internals de pagamentos
quebrar outros produtos
```

Depois forneço revision 2 do MESMO curso alterando preço e adicionando duas aulas.

O sistema deve:

```text
detectar que é atualização
mostrar DIFF
atualizar idempotentemente
preservar IDs
não duplicar dados
manter histórico
```

Esse é o teste arquitetural que define se ProdutoSpec/CourseSpec realmente se tornou o **DNA dos produtos da plataforma**.
