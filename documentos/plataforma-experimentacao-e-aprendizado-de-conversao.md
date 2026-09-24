---
titulo: Plataforma de Experimentação e Aprendizado de Conversão
publico: true
ordem: 13
---

# Plataforma de Experimentação e Aprendizado de Conversão

Um manual para entender como a Meshcraft transforma página, comportamento e
compra em aprendizado causal, sem fingir que o que ainda é plano já está pronto.

Este texto tem dois leitores. O leitor de produto precisa enxergar o filme:
o que a pessoa vê, o que a casa mede, como uma decisão nasce. O leitor técnico
precisa enxergar as fronteiras: células, contratos, eventos, identidade,
versionamento, fallback, testes e evolução futura.

## Sumário

1. O que estamos construindo
2. O que a plataforma faz e o que ela não faz
3. A jornada completa da pessoa
4. As três camadas
5. Como isso se encaixa nas células existentes
6. O que já existe no repositório
7. O que ainda falta
8. Entidades e modelos
9. Assignment, exposure e conversão
10. Identidade e privacidade
11. Métricas e decisão
12. SRM e inferência
13. Versionamento e promoção
14. Audiências, camadas e fila
15. Aprendizado organizacional
16. IA no lugar correto
17. O que fica adiado
18. O que nunca deve ser feito
19. Falhas e degradação
20. Manual operacional
21. Roadmap de implementação
22. Testes e provas
23. FAQ
24. Glossário
25. Dez lições para levar embora

## 1. O que estamos construindo

"Testar uma landing page" é pequeno demais. Parece trocar uma frase por outra
e olhar qual vendeu mais. A plataforma que está nascendo quer responder uma
pergunta maior:

```text
hipótese
→ variante
→ assignment
→ exposição
→ comportamento
→ conversão
→ inferência
→ decisão
→ aprendizado
→ nova baseline
```

A página é a superfície. O ativo é o aprendizado.

A analogia central é uma cozinha de teste.

A chef formula a pergunta: "se eu apresentar este prato como refeição de
trabalho, mais pessoas pedem a conta completa?". O maître escolhe, de forma
controlada, quem recebe a receita A e quem recebe a receita B. O garçom entrega
o prato e registra se a pessoa realmente viu e provou. O caixa registra o que
ela comprou. A controladoria calcula o resultado. A chef decide se a receita
entra no cardápio. O livro da cozinha registra o aprendizado para a próxima
rodada.

Traduzindo:

| Na cozinha | Na plataforma |
|---|---|
| Chef | produto e mantenedor formulando hipótese |
| Receita | variante |
| Maître | avaliador de assignment |
| Garçom | página renderizada e exposição |
| Caixa | checkout e pedido |
| Controladoria | métricas e inferência |
| Livro da cozinha | aprendizado registrado |

Isto não é apenas A/B testing. A/B testing é uma técnica dentro do caminho. A
plataforma inteira é a disciplina de formular, medir, decidir, promover e
aprender sem apagar a história.

## 2. O que a plataforma faz e o que ela não faz

| Faz | Não faz |
|---|---|
| mede hipóteses | não adivinha causalidade sem dados |
| mantém variantes imutáveis | não altera conteúdo histórico |
| mede exposição | não confunde assignment com exposição |
| compara versões | não compara textos sem contexto |
| calcula métricas | não declara vitória por taxa bruta |
| registra aprendizado | não transforma qualquer resultado em verdade universal |
| permite IA auxiliar | não deixa IA publicar livremente |
| preserva baseline | não derruba a página se o avaliador falhar |

Proibições explícitas:

- Não colocar `random()` dentro do template.
- Não chamar `experimentos` em toda requisição da página.
- Não duplicar copy nos eventos.
- Não alterar uma variante em execução.
- Não confundir atribuição de marketing com experimento causal.
- Não testar muitas variantes com tráfego insuficiente.
- Não usar CTR como métrica universal.
- Não promover automaticamente entre idiomas.
- Não permitir IA publicando tratamentos continuamente.
- Não apagar experimentos antigos.
- Não criar célula nova antes de existir um segundo dono real do domínio.

Estado honesto: a arquitetura de experimentação foi decidida como destino em
`docs/decisoes/DECISAO-a-pagina-real-antes-do-experimento.md`. O que existe
hoje é a fundação de página, versão, visitante e primeiro evento de visita.
Assignment, exposure e inferência ainda não existem no código.

## 3. A jornada completa da pessoa

Imagine Alice abrindo a oferta.

1. Alice chega ao site.
2. O `funil` resolve o site pelo Host.
3. O middleware de visitante cria ou reaproveita `meshcraft_visitante`.
4. A página `/oferta` pede ao `catalogo` a versão publicada da página.
5. O template desenha as seções publicadas.
6. O `funil` publica `funil.pagina-vista.v1`.
7. Alice percorre seções.
8. FUTURO: cada seção realmente vista emitirá `funil.secao-vista.v1`.
9. Alice clica no CTA.
10. FUTURO: o clique emitirá `funil.cta-clicado.v1`.
11. Alice deixa um lead.
12. FUTURO: depois de gravar o lead, o funil emitirá `funil.lead-capturado.v1`.
13. Alice inicia checkout.
14. O checkout pode gerar `pedido.criado.v1`.
15. FUTURO: a costura ligará visitante, lead e pedido.
16. FUTURO: uma decisão de experimento virará aprendizado e nova baseline.

Casos de borda:

| Situação | Comportamento correto |
|---|---|
| primeira visita | cria `meshcraft_visitante` opaco |
| retorno da mesma pessoa | mantém o mesmo visitante se o cookie é válido |
| cookie ausente | sorteia novo UUID4 |
| cookie inválido | descarta e sorteia outro |
| serviço de experimentos fora do ar | baseline local por snapshot, quando existir |
| Redis fora do ar | página abre, medição pode não sair |
| configuração inválida | baseline e recusa clara no controle |
| página sem publicação | 404 com mensagem de que ainda não foi publicada |
| catálogo indisponível | 503 com `Retry-After`, não tela vazia com 200 |
| assignment sem seção vista | não conta como exposure |
| compra dias depois | atribuição depende da costura visitante, lead e pedido |

EXISTE: o cookie `meshcraft_visitante`, a renderização de `/oferta` e
`funil.pagina-vista.v1` estão no código em `services/funil/apps/core/visitante.py`,
`services/funil/apps/core/views.py` e `contracts/eventos/funil.pagina-vista.v1.json`.

FALTA: os eventos de seção, CTA e lead já têm contrato, mas não foram emitidos
pela página nesta leitura.

## 4. As três camadas

```text
Control Plane
      ↓
configuração versionada
      ↓
snapshot local
      ↓
Data Plane
      ↓
assignment
      ↓
exposure
      ↓
eventos
      ↓
Analytics Plane
      ↓
inferência
      ↓
decisão
      ↓
aprendizado
```

### Control plane

Responsável por hipóteses, `ExperimentSpec`, `VariantSpec`, `AudienceSpec`,
alocação, camadas, ciclo de vida, fila, promoção, aprendizados e governança.

Estado: DECIDIDO, NÃO IMPLEMENTADO para experimentos de página. A decisão está
em `DECISAO-a-pagina-real-antes-do-experimento.md`.

### Data plane

Responsável por identidade, elegibilidade, assignment, exposição, avaliação
local, renderização, baseline e fallback.

Estado: PARCIAL. Identidade de visitante e renderização existem. Assignment,
exposure e snapshot de experimento ainda faltam.

### Analytics plane

Responsável por eventos, ingestão, métricas, guardrails, SRM, inferência,
decisão e aprendizado.

Estado: PARCIAL. O livro de fatos existe em `services/metricas/apps/fatos`.
Inferência experimental, SRM e promoção ainda faltam.

Misturar as três responsabilidades no mesmo código cria o pior desenho: a tela
decide ciência, o dado decide produto e a métrica derruba a página. A separação
mantém a página rápida, a decisão auditável e o livro imutável.

## 5. Como isso se encaixa nas células existentes

| Célula | Responsabilidade |
|---|---|
| `catalogo` | site, produto, oferta, página, rascunho e versão publicada |
| `funil` | renderização, identidade do visitante, avaliação local futura e eventos da página |
| `experimentos` | futura dona do control plane transversal |
| `metricas` | livro imutável de fatos e leitura histórica |
| `leads` | lead e dados da pessoa |
| `checkout` | início e conclusão do checkout |
| `pagamentos` | pagamento, recusa, estorno e reembolso |
| `alunos` | ativação e comportamento posterior |
| `admin` | escrita, publicação, leitura e decisão humana |

O dono de cada fato continua sendo a célula que o produz. O `catalogo` é dono
da página publicada. O `funil` é dono do fato de que uma visita ocorreu. A
`metricas` consome e guarda o fato, mas não vira dona da página, do lead ou do
pedido.

Dados que cruzam células via contrato: ids opacos, versão, site, slug, evento
e métricas deriváveis. Dados que não devem cruzar para o livro: e-mail,
telefone, nome, texto de copy e qualquer dado pessoal apagável.

Uma célula não lê o banco da outra porque a Constituição da plataforma separa
dados por célula. A comunicação acontece por API interna, conforme
`contracts/*.openapi.yaml`, ou por evento versionado em `contracts/eventos/`.

## 6. O que já existe no repositório

| Item | Estado | Onde vive | O que garante | Teste citado |
|---|---|---|---|---|
| `Page` | EXISTE | `services/catalogo/apps/paginas/models.py` | identidade estável por site e slug | testes de páginas do catálogo |
| `PageDraft` | EXISTE | mesmo arquivo | rascunho mutável e validado | testes de vocabulário e páginas |
| `PageVersion` | EXISTE | mesmo arquivo | versão publicada imutável | testes de imutabilidade |
| vocabulário de slots | EXISTE | `services/catalogo/apps/paginas/vocabulario.py` | seções e slots semânticos | `test_vocabulario_de_paginas.py` |
| API de página | EXISTE | `services/catalogo/apps/paginas/api.py` | ler, gravar rascunho e publicar | testes de API da página |
| cookie `meshcraft_visitante` | EXISTE | `services/funil/apps/core/visitante.py` | visitante opaco e persistente | `services/funil/tests/test_identidade_do_visitante.py` |
| renderização `/oferta` | EXISTE | `services/funil/apps/core/views.py` e template | desenha versão publicada | `services/admin/tests/test_pagina_de_venda.py` e testes do funil |
| `funil.pagina-vista.v1` | EXISTE | contrato e `_medir_visita` | primeiro fato da página | `services/funil/tests/test_pagina_vista.py` |
| publicação fail-open da telemetria | EXISTE | `services/funil/apps/core/telemetria.py` | Redis não derruba página | testes de página vista |
| livro append-only | EXISTE | `services/metricas/apps/fatos/models.py` | fato imutável e idempotente | testes da metricas |
| recepção de eventos | EXISTE | `services/metricas/apps/fatos/recepcao.py` | envelope válido vira fato, inválido vira morto | testes da recepção |
| contratos de seção, CTA e lead | EXISTE COMO CONTRATO | `contracts/eventos/funil.*.v1.json` | formato fechado dos fatos futuros | contrato congelado |
| editor administrativo de página | EXISTE | `services/admin` | escreve e publica página pelo `catalogo` | `services/admin/tests/test_pagina_de_venda.py` |

Limite importante: contrato existir não significa emissão implementada. A casa
já desenhou `funil.secao-vista`, `funil.cta-clicado` e `funil.lead-capturado`,
mas o código lido só publicou `funil.pagina-vista`.

## 7. O que ainda falta

| Falta | Efeito prático da ausência |
|---|---|
| emitir `funil.secao-vista` | não sabemos até onde a pessoa desceu |
| emitir `funil.cta-clicado` | não sabemos qual CTA levou ao checkout |
| emitir `funil.lead-capturado` | lead não fica ligado à página e versão |
| consumir os quatro streams com leituras de funil | o livro guarda fatos, mas ainda falta painel específico |
| painel do funil calculado do livro | o mantenedor não vê a escada de conversão |
| propagar `visitor_id` até lead e compra | compra não volta ao visitante anônimo |
| costura visitante, lead e pedido | atribuição causal fica incompleta |
| primeiro avaliador local | ninguém escolhe variante por regra |
| assignment | não há divisão de tráfego |
| exposure | não há prova de que a variante apareceu |
| `ExperimentSpec` | não há contrato científico do teste |
| `VariantSpec` | não há intervenção imutável formal |
| promoção | vencedor não vira nova baseline de forma auditável |
| aprendizado | resultado não vira conhecimento consultável |

## 8. Entidades e modelos

`PageTemplate` é a forma permitida da página: quais seções existem e que papel
cada slot cumpre. No código atual, isso aparece como vocabulário em
`vocabulario.py`, não como tabela com esse nome.

`PageSpec` é a definição da página específica: este site, este slug, esta
oferta. Hoje isso aparece em `Page` e no vínculo opcional com `Offer`.

`PageDraft` é o conteúdo em edição. É mutável e existe para o admin escrever
sem mudar o que o visitante vê.

`PageVersion` é o snapshot publicado e imutável. Eventos apontam para ele por
`pagina_version`.

`RenderedPage` é o que o visitante recebeu: página, versão, blocos, oferta,
preço, CTA e dados necessários para telemetria.

`VariantSpec` é o conteúdo alternativo com hipótese e classificação. FALTA.

`ExperimentSpec` é o contrato científico do experimento. FALTA.

Exemplo de `ExperimentSpec` futuro:

```json
{
  "id": "EXP-OFERTA-HEADLINE-001",
  "nome": "Headline profissional contra headline hobby",
  "hipotese": "Enquadrar como avanço profissional aumenta checkout_started em tráfego frio.",
  "escopo": "pagina",
  "pagina": {"site_id": "meshcraft", "slug": "oferta"},
  "slot": "cubo.headline",
  "unidade": "visitor_id",
  "audiencia": {"origem": "trafego-frio", "idioma": "pt-br"},
  "controle": {"variant_id": "A", "page_version": 17},
  "tratamentos": [{"variant_id": "B", "descricao": "headline profissional"}],
  "alocacao": {"A": 50, "B": 50},
  "metrica_principal": "checkout_started",
  "metricas_secundarias": ["cta_clicado", "lead_capturado"],
  "guardrails": ["reembolso", "chargeback", "erro_de_pagina"],
  "mde": {"checkout_started": "20%"},
  "janela": {"dias": 14},
  "regra_de_inicio": "quando page_version 17 estiver publicada",
  "regra_de_parada": "amostra planejada ou regra sequencial declarada",
  "metodo": "teste de duas proporções com horizonte fixo",
  "proprietario": "mantenedor",
  "estado": "rascunho"
}
```

Estado deste exemplo: DECIDIDO COMO FORMA CONCEITUAL, NÃO IMPLEMENTADO.

## 9. Assignment, exposure e conversão

```text
Assignment:
o sistema decidiu que Alice pertence à variante B.

Exposure:
Alice realmente viu o slot alterado.

Conversion:
Alice executou o comportamento medido.
```

Assignment sem exposure não deve entrar como pessoa tratada porque Alice pode
ter sido sorteada para B e fechado a aba antes do cubo aparecer. Exposure deve
ser registrado no momento correto, quando o slot entra na tela. Conversão deve
carregar referência suficiente ao experimento para que compra tardia ainda seja
ligada ao que foi visto.

Eventos precisam ser idempotentes: reentrega da fila não pode contar duas
vezes. A `metricas` já guarda `event_id` único em `Evento`. Isso é base, não
experimento pronto.

## 10. Identidade e privacidade

O `visitor_id` existe para contar gente antes de existir login ou lead. Ele é
opaco porque serve para ligar fatos, não para descrever a pessoa. Não deve
conter e-mail, IP, telefone nem hash desses dados. O cookie é de primeira parte,
criado pelo domínio da própria página, e o JavaScript não lê o valor do cookie.

Quando a pessoa vira lead ou compra, a costura deve ligar o id opaco do
visitante ao id opaco do lead e do pedido. Cada dado pessoal fica na célula
dona. A `metricas` pode guardar ids opacos e fatos, não dados pessoais
apagáveis.

LGPD e minimização: livro imutável não é lugar para dado que alguém pode ter
direito de apagar. Por isso `funil.lead-capturado.v1` exige `lead_id` e não
e-mail, nome ou telefone. Quem precisar de detalhe pergunta à célula `leads`,
que é a casa desse dado.

## 11. Métricas e decisão

Métrica principal é a que decide o experimento. Métrica secundária explica.
Métrica diagnóstica mostra mecanismo. Métrica de negócio confirma impacto.
Guardrail impede vitória que machuca a casa.

Exemplo:

```text
CTA subiu 20%
checkout_started subiu 8%
compra ficou igual
reembolso subiu 15%
```

Isso não é vitória automática. Clique não é negócio, checkout iniciado não é
receita, e reembolso piorando pode anular ganho aparente.

Regra de promoção:

```text
significância estatística
+
relevância prática
+
guardrails saudáveis
=
candidato à promoção
```

Conversão precisa ter janela. Receita líquida precisa olhar reembolso e
chargeback. MDE precisa ser definido antes, para não escolher o tamanho do
efeito depois de ver o resultado.

## 12. SRM e inferência

50/50 é o padrão inicial porque divide tráfego com simplicidade e reduz
perguntas que não ajudam. SRM, ou Sample Ratio Mismatch, é quando a divisão
observada não bate com a planejada. Um teste planejado para 50/50 que entrega
70/30 pode estar medindo bug de assignment, cache, público ou coleta, não
preferência real.

Observar o teste continuamente aumenta o risco de falso positivo quando o
método não foi desenhado para isso. Desenho fixo significa definir tamanho,
janela e regra antes. Teste sequencial só entra quando a regra de parada também
foi decidida antes.

Não declare vencedor apenas porque `p < 0,05`. Pergunte:

- O efeito é grande o bastante para importar?
- A métrica principal moveu?
- Os guardrails ficaram saudáveis?
- O experimento teve exposure real?
- A amostra obedeceu à alocação?

## 13. Versionamento e promoção

```text
PageVersion 17
      ↓
Experimento 71
A versus B
      ↓
B vence
      ↓
PageVersion 18 baseada em B
      ↓
Experimento 72
B versus C
```

A versão antiga permanece porque eventos antigos apontam para ela. Variante não
pode ser editada porque copy alterada é outra intervenção. O experimento antigo
continua consultável porque aprendizado sem contexto vira folclore.

Uma vitória em português não vira automaticamente vitória em inglês. Idioma é
mercado, repertório e promessa cultural. O vencedor pode inspirar tradução, mas
não importar causalidade.

## 14. Audiências, camadas e fila

Audiência define quem pode entrar. Exclusão tira quem contaminaria a leitura.
Alocação distribui entre variantes. Layer impede dois testes de mexerem no
mesmo espaço mental ao mesmo tempo. Fila de candidatos guarda hipóteses que
ainda não têm tráfego ou prioridade.

Exemplo:

```text
EXP-01: headline
EXP-02: imagem
EXP-03: preço
```

Headline e imagem podem conviver se a hipótese aceitar interação ou se estiverem
em camadas separadas. Headline e preço juntos podem contaminar a leitura: se a
compra sobe, não se sabe se foi promessa ou preço. Muitos tratamentos com pouco
tráfego produzem barulho com aparência científica.

## 15. Aprendizado organizacional

O resultado não deve terminar em:

```text
B venceu.
```

Ele deve virar:

```text
Para tráfego frio de iniciantes, no mercado brasileiro, durante a oferta X,
o enquadramento profissional aumentou checkout_started em relação ao
enquadramento hobby, dentro da janela Y, com intervalo Z e sem aumento
observável de reembolso.
```

`ExperimentLearning` futuro deve carregar hipótese, audiência, contexto,
controle, tratamento, efeito, incerteza, amostra, validade, decisão,
generalização, limites e próximos testes.

Estado: FALTA para experimentação de conversão. Já existe, no `admin`, um
laboratório organizacional de experimentos como registros do livro, mas isso
não é assignment de página nem inferência causal sobre variantes.

## 16. IA no lugar correto

Antes do teste, IA pode analisar histórico, sugerir hipóteses, propor
candidatos, identificar lacunas e sugerir próximos testes.

Durante o teste, IA pode detectar anomalias, verificar SRM, avisar sobre
ausência de exposure, alertar guardrails e apontar instrumentação quebrada.

Depois do teste, IA pode interpretar resultados, escrever `ExperimentLearning`,
sugerir novos experimentos, agrupar padrões e detectar contradições.

IA não publica sozinha, não altera experimento em execução, não declara vitória
sem critérios, não transforma correlação em causalidade e não traduz vencedor
automaticamente para outro mercado.

## 17. O que fica adiado

| Adiado | Por que fica fora da primeira versão | Gatilho de entrada |
|---|---|---|
| CUPED | não há histórico por visitante suficiente | tráfego e comportamento anterior confiáveis |
| bandits contextuais | exigem mais tráfego e controle | testes estáveis e volume alto |
| personalização automática | antes é preciso medir sem personalizar | experimentação confiável e identidade costurada |
| holdout global | mede efeito acumulado, não primeiro teste | várias vitórias promovidas |
| knowledge graph completo | grafo vazio não ensina | aprendizados reais acumulados |
| geração autônoma de copy | governança vem antes de autonomia | fluxo de aprovação e guardrails sólidos |
| otimização adaptativa | mexe na alocação durante o teste | método sequencial definido |
| experimentos internacionais automáticos | idioma não herda causalidade | mercados com tráfego e métricas próprias |

## 18. O que nunca deve ser feito

- Chamada síncrona obrigatória no caminho da página.
- `random()` no template.
- Variante mutável.
- Evento sem versão.
- Conversão sem referência de exposição.
- Copy duplicada nos eventos.
- Acesso ao banco de outra célula.
- Experimento sem métrica principal.
- Experimento sem MDE.
- Múltiplos tratamentos com tráfego insuficiente.
- Peeking sem método sequencial.
- Promoção baseada só em CTR.
- IA publicando sem aprovação.
- Mistura de atribuição de marketing com causalidade.
- Apagar histórico.
- Declarar vencedor entre idiomas por tradução.
- Personalização antes de experimentação confiável.

## 19. Falhas e degradação

| Falha | Comportamento correto | O que o usuário vê |
|---|---|---|
| Redis fora do ar | página abre, evento pode ser perdido | página normal |
| configuração inválida | baseline | versão padrão |
| célula `experimentos` fora do ar | baseline pelo snapshot | página abre |
| cookie inválido | novo `visitor_id` | nada perceptível |
| catálogo fora do ar | 503 com orientação de atualizar | aviso claro |
| evento duplicado | uma ocorrência no livro | nada perceptível |
| evento inválido | fila de mortos | nada perceptível, operador investiga |
| exposição ausente | não contar como tratado | resultado inconclusivo |
| métrica incompleta | não decidir vencedor | decisão bloqueada |
| SRM | experimento inválido ou investigação obrigatória | sem mudança na página |
| compra sem visitor_id | conversão não atribuída ao visitante | compra acontece |

## 20. Manual operacional

| Procedimento | Pré-condição | Ação | Resultado esperado | Erro possível | O que fazer | Prova |
|---|---|---|---|---|---|---|
| criar hipótese | gargalo identificado | escrever pergunta e métrica | hipótese auditável | métrica vaga | reescrever com evento e janela | registro de hipótese |
| criar variante | `PageVersion` baseline | criar `VariantSpec` | intervenção imutável | copy sem hipótese | recusar | variante congelada |
| revisar variante | variante pronta | revisar risco e copy | aprovada ou recusada | dado pessoal no evento | remover | checklist |
| publicar página | rascunho válido | chamar `publishPage` | nova `PageVersion` | rascunho vazio | escrever primeiro | resposta da API |
| iniciar experimento | tráfego e eventos prontos | ativar spec | assignment começa | sem exposure | bloquear início | evento de início |
| pausar experimento | risco ou falha | parar novos assignments | baseline continua | pause derruba página | usar snapshot baseline | página abrindo |
| encerrar experimento | janela ou amostra fechada | congelar análise | resultado calculado | SRM | investigar | relatório |
| investigar SRM | alocação divergente | comparar esperado e observado | causa ou invalidação | dados incompletos | não promover | diagnóstico |
| rejeitar inconclusivo | efeito insuficiente | registrar limite | sem promoção | pressão por vencedor | manter baseline | aprendizado |
| promover vencedor | critérios satisfeitos | publicar nova baseline | nova `PageVersion` | guardrail ruim | não promover | versão nova |
| registrar aprendizado | resultado revisado | escrever `ExperimentLearning` | conhecimento consultável | generalização indevida | restringir contexto | registro |
| reverter promoção | regressão medida | voltar baseline ou publicar nova | página recuperada | histórico apagado | preservar versões | versão posterior |
| investigar evento ausente | métrica zerada | conferir emissão e recepção | causa localizada | Redis ausente | corrigir env ou instrumentação | evento no livro |
| consultar exposição | experimento rodando | filtrar por experiment, variant e slot | exposures reais | só assignment | não contar tratado | consulta |
| conferir origem da métrica | número suspeito | ir até eventos crus | linhagem clara | fato sem site | fila de mortos | event_id |

## 21. Roadmap de implementação

| Fase | Objetivo | Arquivos ou células | Dados | Contratos | Testes | Riscos | Critério de saída | Fora |
|---|---|---|---|---|---|---|---|---|
| A Telemetria | medir a página | `funil`, `metricas`, `admin` | seção, CTA, lead | eventos `funil.*` | emissão e recepção | evento perdido | funil visível no painel | assignment |
| B Identidade | costurar visitante, lead e pedido | `funil`, `leads`, `checkout` | visitor, lead, pedido | lead e pedido | jornada completa | dado pessoal no livro | compra atribuível | inferência |
| C Primeiro experimento | um slot, duas variantes | página e avaliador local | assignment e exposure | spec futuro | sticky e baseline | página depender de serviço | A/B 50/50 medido | camadas |
| D Governança | decidir com rigor | `admin`, `metricas` | MDE, SRM, guardrails | leitura | SRM e decisão | vencedor falso | promoção candidata | IA autônoma |
| E Orquestração | evitar contaminação | futura `experimentos` | audiência e layer | spec transversal | exclusão mútua | testes simultâneos ruins | fila ordenada | bandits |
| F Aprendizado | tornar resultado patrimônio | `admin` e livro | learning | registro | consulta por contexto | generalização falsa | aprendizado pesquisável | knowledge graph completo |
| G IA e avançado | apoiar escala | IA, admin e métricas | histórico | políticas | auditoria | autonomia cedo demais | IA analista aprovada | autopublicação |

## 22. Testes e provas

Cada invariante precisa ter:

```text
teste vermelho sem a proteção
+
teste verde com a proteção
```

Testes-guarda necessários:

- versão publicada imutável;
- assignment sticky;
- distribuição planejada;
- exposure separado;
- fallback para baseline;
- evento sem texto de copy;
- evento com página e versão;
- visitante persistente;
- duplicata idempotente;
- SRM;
- promoção;
- preservação do histórico;
- isolamento entre sites;
- isolamento entre idiomas;
- ausência de dados pessoais nos eventos.

EXISTE: parte dessa lista já existe para página, visitante, evento e livro de
fatos. FALTA: guardas de assignment, exposure, SRM, promoção e aprendizado.

## 23. FAQ

**Isso é um A/B test?**  
É mais que isso. A/B test é a técnica de comparação. A plataforma inclui
hipótese, exposição, inferência, decisão, promoção e aprendizado.

**Por que não testar páginas inteiras?**  
Pode acontecer depois, mas primeiro a casa precisa saber qual intervenção moveu
qual degrau. Página inteira ensina menos quando o tráfego é baixo.

**Por que não chamar a célula de experimentos em cada visita?**  
Porque a página não pode depender de chamada síncrona para abrir. Avaliação deve
ser local, por snapshot.

**Por que assignment não é exposure?**  
Porque ser sorteado para B não prova que a pessoa viu B.

**Por que não usar só compra?**  
Porque compra exige muito mais tráfego. A decisão de 19/09/2026 calculou que
métrica de compra pode pedir dezenas de milhares de visitantes por braço.

**Por que não declarar vencedor por conversão bruta?**  
Porque conversão bruta ignora incerteza, guardrails, SRM e efeito prático.

**Por que 50/50?**  
Porque é simples, equilibrado e barato para começar.

**Por que uma variante é imutável?**  
Porque mudar a copy muda a intervenção. O histórico precisa apontar para o que
foi visto.

**Por que um vencedor em português não é vencedor em inglês?**  
Porque idioma muda contexto, promessa e audiência.

**Por que IA não publica sozinha?**  
Porque publicar é decisão de produto e risco. IA ajuda a preparar e auditar.

**Quando entra personalização?**  
Depois que experimentação, identidade e guardrails estiverem confiáveis.

**Quando entra o grafo?**  
Depois de haver aprendizados suficientes para relacionar.

**O que acontece se Redis cair?**  
A página abre e a medição pode não sair.

**O que acontece se o experimento estiver errado?**  
Baseline vence, ou o experimento é pausado e investigado.

**Qual é a diferença entre atribuição e causalidade?**  
Atribuição diz a que toque uma compra foi ligada. Causalidade exige comparação
controlada entre grupos.

**Como uma promoção vira nova baseline?**  
Publicando uma nova `PageVersion` baseada no vencedor, sem alterar a versão
antiga.

**O que já existe hoje?**  
Página versionada, visitante opaco, renderização de oferta, evento de página
vista e livro de fatos.

**O que ainda falta?**  
Seção vista, CTA clicado, lead capturado, costura até compra, assignment,
exposure, inferência, promoção e aprendizado de conversão.

## 24. Glossário

| Termo | Definição simples |
|---|---|
| baseline | versão padrão contra a qual se compara |
| hipótese | pergunta que o teste tenta responder |
| variante | intervenção alternativa e imutável |
| slot | lugar semântico da página, como `cubo.headline` |
| PageVersion | publicação congelada da página |
| assignment | decisão de qual variante a pessoa receberá |
| exposure | prova de que a pessoa viu a intervenção |
| conversão | comportamento medido |
| audiência | grupo elegível para o teste |
| camada | espaço de exclusão para testes simultâneos |
| alocação | porcentagem de tráfego por variante |
| MDE | menor efeito que vale detectar |
| SRM | desvio entre divisão planejada e observada |
| guardrail | métrica que impede vitória perigosa |
| inferência | cálculo que estima efeito e incerteza |
| intervalo de confiança | faixa plausível do efeito |
| teste sequencial | teste com regra formal de leitura ao longo do tempo |
| holdout | grupo preservado para medir efeito acumulado |
| CUPED | técnica que usa histórico para reduzir variância |
| bandit | método que adapta alocação durante o teste |
| aprendizado | conclusão contextual registrada |
| causalidade | efeito atribuído a uma intervenção controlada |
| atribuição | ligação operacional entre toque e resultado |
| snapshot | cópia local da configuração usada para avaliar rápido |
| fallback | comportamento quando algo falha |
| baseline promotion | vencedor virando nova versão padrão |

## 25. Dez lições para levar embora

1. A página é a superfície, não o aprendizado.
2. Uma hipótese sem exposição não foi testada.
3. Um assignment não prova que alguém viu algo.
4. Copy alterada é uma nova intervenção.
5. O evento deve carregar a versão, nunca a frase.
6. Uma página que mede mal ainda precisa continuar abrindo.
7. Clique não é negócio.
8. Um vencedor precisa sobreviver aos guardrails.
9. Um resultado não generaliza automaticamente para outro idioma.
10. O ativo final não é a melhor variante, mas o conhecimento acumulado.

## Auditoria final do manual

- Funcionalidade futura foi rotulada como FALTA, ADIADO ou DECIDIDO, NÃO IMPLEMENTADO.
- A decisão da página real antes do experimento foi preservada.
- Eventos têm dono declarado.
- Dados pessoais ficaram fora do livro de fatos.
- Assignment e exposure foram separados.
- Baseline e fallback foram explicados.
- Itens adiados têm motivo e gatilho.
- Cada fase tem critério de saída verificável.
- A jornada começa na cadeira do visitante e termina na decisão.
- A célula `experimentos` ficou futura, condicionada a segundo dono real.
