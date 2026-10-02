---
titulo: Plataforma de Experimentação e Aprendizado de Conversão
publico: false
ordem: 13
---

# Plataforma de Experimentação e Aprendizado de Conversão

Um manual para entender como a Meshcraft transforma página, comportamento e
compra em aprendizado causal, sem fingir que o que ainda é plano já está pronto.

Este texto tem dois leitores. O leitor de produto precisa enxergar o filme:
o que a pessoa vê, o que a casa mede, como uma decisão nasce. O leitor técnico
precisa enxergar as fronteiras: células, contratos, eventos, identidade,
versionamento, fallback, testes e evolução futura.

**Leitura técnica conferida em 24/09/2026 (UTC), revisão `7ae5ce816f1b5a5bf86f2486a8e86fdae74dd4a5`.** Isto é uma fotografia do código, não um painel de produção. EXISTE significa implementação encontrada; não certifica serviço implantado. Testes citados foram lidos; as suítes das células NÃO FORAM RODADAS nesta edição documental.

**Como ler os estados:** EXISTE = localizado no código; FALTA = ausência identificada, inclusive a parte ausente de uma implementação parcial; DECIDIDO, NÃO IMPLEMENTADO = decisão expressa do repositório; ADIADO = gatilho já autorizado na decisão; FORA DO ESCOPO ATUAL = não entra neste MVP; NÃO CONFIRMADO NO CÓDIGO = conceito ou proposta deste plano sem implementação encontrada. Uma proposta detalhada aqui não cria uma segunda lei.

O plano executável está no capítulo 21. O percurso de estudo segue os capítulos em ordem.

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
21. Plano de execução do MVP
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

**DECIDIDO, NÃO IMPLEMENTADO como plataforma completa.** A tabela descreve o destino do produto. O inventário do capítulo 6 distingue o que existe.

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

No experimento proposto, entre receber o cookie e renderizar, Alice passa pela audiência. Se não for elegível, recebe baseline. Se for, o avaliador escolhe A ou B e registra assignment. Só quando o slot atende ao critério de visibilidade surge exposure. Pedido criado ainda não é compra: a confirmação vem de pagamentos. Uma devolução posterior permanece ligada àquele pedido. Eventos recebidos fora de ordem usam o horário do fato e a janela congelada, não o conteúdo atualmente publicado.

Se Alice recebe B e fecha a aba antes da visibilidade mínima, há assignment e não há exposure. Se compra dias depois dentro da janela e com vínculo válido, a conversão pertence à coorte original. Fora da janela fica no histórico, sem alterar a métrica principal dessa janela. Sem vínculo, fica não atribuída. Todos esses passos de atribuição experimental estão FALTA, não são capacidades do evento de visita existente.

> **Pausa.** A cozinha separou o prato B, mas Alice saiu antes de o garçom entregar. A ficha de separação prova que ela provou o prato? Não. É essa diferença que assignment e exposure preservam.

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

Estado: EXISTE parcialmente; FALTA completar. Identidade de visitante e renderização existem. Assignment,
exposure e snapshot de experimento ainda faltam.

### Analytics plane

Responsável por eventos, ingestão, métricas, guardrails, SRM, inferência,
decisão e aprendizado.

Estado: EXISTE parcialmente; FALTA completar. O livro de fatos existe em `services/metricas/apps/fatos`.
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
e métricas deriváveis. Dados que não devem cruzar para o livro analítico: e-mail,
telefone, nome e texto de copy. IDs opacos também podem ser dados pessoais quando vinculáveis: precisam de finalidade, retenção e tratamento dos direitos do titular. Não confundir minimização com anonimização.

## 6. O que já existe no repositório

| Item | Estado | Onde vive | O que garante | Teste citado |
|---|---|---|---|---|
| `Page` | EXISTE | `services/catalogo/apps/paginas/models.py` | identidade estável por site e slug | `services/catalogo/tests/test_paginas_pela_porta.py` |
| `PageDraft` | EXISTE | mesmo arquivo | rascunho mutável e validado | `services/catalogo/tests/test_vocabulario_de_paginas.py` |
| `PageVersion` | EXISTE | mesmo arquivo | versão publicada imutável | `services/catalogo/tests/test_pagina_publicada_imutavel.py` |
| vocabulário de slots | EXISTE | `services/catalogo/apps/paginas/vocabulario.py` | seções e slots semânticos | `test_vocabulario_de_paginas.py` |
| API de página | EXISTE | `services/catalogo/apps/paginas/api.py` | ler, gravar rascunho e publicar | `services/catalogo/tests/test_paginas_pela_porta.py` |
| cookie `meshcraft_visitante` | EXISTE | `services/funil/apps/core/visitante.py` | visitante opaco e persistente | `services/funil/tests/test_identidade_do_visitante.py` |
| renderização `/oferta` | EXISTE | `services/funil/apps/core/views.py` e template | desenha versão publicada | `services/funil/tests/test_pagina_de_oferta.py` |
| `funil.pagina-vista.v1` | EXISTE | contrato e `_medir_visita` | primeiro fato da página | `services/funil/tests/test_pagina_vista.py` |
| publicação fail-open da telemetria | EXISTE | `services/funil/apps/core/telemetria.py` | Redis não derruba página | `services/funil/tests/test_pagina_vista.py` |
| livro append-only | EXISTE | `services/metricas/apps/fatos/models.py` | fato imutável e idempotente | `services/metricas/tests/test_evento_imutavel.py` |
| recepção de eventos | EXISTE | `services/metricas/apps/fatos/recepcao.py` | envelope válido vira fato, inválido vira morto | `services/metricas/tests/test_recepcao.py` |
| contratos de seção, CTA e lead | EXISTE COMO CONTRATO | `contracts/eventos/funil.*.v1.json` | formato fechado dos fatos futuros | contrato congelado |
| editor administrativo de página | EXISTE | `services/admin` | escreve e publica página pelo `catalogo` | `services/admin/tests/test_pagina_de_venda.py` |

Limite importante: contrato existir não significa emissão implementada. A casa
já desenhou `funil.secao-vista`, `funil.cta-clicado` e `funil.lead-capturado`,
mas o código lido só publicou `funil.pagina-vista`.

### Divergências que afetam a implementação

| Afirmação documental | Evidência executável | O que prevalece e o efeito |
|---|---|---|
| Decisão de 19/09, §§4/9: métricas recebe os novos fatos sem alteração | `services/metricas/apps/fatos/management/commands/consume_eventos.py::STREAMS` lista assuntos explicitamente e não inclui os quatro `funil.*` | O código determina o comportamento. A fundação precisa de lote de consumo; emitir não basta |
| `constituicoes/AGENTS.metricas.md`: inválido é recusado e só IDs opacos ficam | `recepcao.py::receber` valida envelope e guarda `data` inteiro; `pedido.criado.v1.json` contém `customer` | O código mostra que a garantia integral não existe. A lei continua sendo requisito a implementar, não autorização para gravar PII |
| Docstring de `telemetria.py` diz que falta endereço de Redis na VPS | `infra/docker-compose.yml`, serviço funil, já declara `REDIS_STREAMS_URL` | Configuração versionada prevalece sobre o comentário; execução na VPS ainda exige medição |
| “Página vista” sugere algo que apareceu no navegador | `views.py::_medir_visita` é chamado no servidor após renderizar, e a view aceita HEAD | É evento de página servida; não é prova de exposure. HEAD, robôs, cache e visitas repetidas exigem definição de denominador |
| Exemplos usam `page_id` como chave dos eventos | Contratos atuais usam `site_id`, `pagina_slug`, `pagina_version`; `api.py::_corpo_publicada` devolve `versao.id` no campo `id` | Não tratar esse `id` como ID estável de Page; não trocar os nomes do contrato ao implementar |
| Referência a versão histórica parece permitir buscar qualquer publicação | `getPage` devolve a última versão; não há operação de histórico nessa superfície | A persistência histórica existe, mas FALTA uma leitura contratada para auditoria e promoção |
| Uma vitória em português parece reutilizável por tradução | Modelos Page/PageVersion não têm campo de idioma e os eventos v1 não o declaram | Decidido (Emenda 1, 26/09/2026): sem idioma como dimensão do experimento, de propósito, não por lacuna; a chave de unicidade do `ativo` é a `Page` (site e slug). Uma promoção continua sem generalizar entre mercados por si só |

**Provas existentes localizadas:** `services/catalogo/tests/test_pagina_publicada_imutavel.py::test_a_trava_tambem_mora_no_banco`, `services/catalogo/tests/test_paginas_pela_porta.py::test_slug_e_unico_por_site_e_a_pagina_de_um_site_nao_vaza_para_outro`, `services/funil/tests/test_pagina_vista.py::test_redis_fora_do_ar_nao_derruba_a_pagina` e `services/metricas/tests/test_recepcao.py::test_reentrega_nao_conta_duas_vezes`. Localizar esses testes não equivale a executá-los.

**História de falha para guardar:** a cozinha escreveu a ficha da entrega, mas o arquivista não estava ouvindo aquele canal. A prateleira de fichas continuou vazia com a cozinha funcionando. O defeito é a lista de canais, não falta de gráfico. Outro caso: a compra de sexta-feira não pode consultar a headline publicada na segunda para decidir o que Alice viu na terça.

## 7. O que ainda falta

| Falta | Efeito prático da ausência |
|---|---|
| emitir `funil.secao-vista` | não sabemos até onde a pessoa desceu |
| emitir `funil.cta-clicado` | não sabemos qual CTA levou ao checkout |
| emitir `funil.lead-capturado` | lead não fica ligado à página e versão |
| consumir os quatro streams com leituras de funil | a lista STREAMS não assina nenhum dos quatro; hoje não basta emitir para chegar ao livro |
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

`PageVersion` é o snapshot publicado e imutável. Eventos apontam para ele pelo conjunto `site_id`, `pagina_slug` e `pagina_version`, não pelo número da versão isolado.

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
  "janela": {"recrutamento_maximo_dias": 14, "conversao_dias": 7},
  "regra_de_inicio": "quando page_version 17 estiver publicada",
  "regra_de_parada": "amostra por braço e período mínimo pré-fixados; prazo máximo sem amostra é inconclusivo; aguardar maturação",
  "metodo": "teste de duas proporções com horizonte fixo",
  "proprietario": "mantenedor",
  "estado": "rascunho"
}
```

Estado deste exemplo: NÃO CONFIRMADO NO CÓDIGO. É proposta didática, não schema vigente nem experimento cadastrado. `meshcraft` é um apelido ilustrativo, não o UUID real de site. Versão 17, janela e MDE são exemplos, não medições.

Antes da ativação, transformar a hipótese em especificação executável: `site_id` real, idioma explícito, audiência observável antes da intervenção, conteúdo B congelado com classificação “enquadramento profissional”, algoritmo/revisão/salt de alocação, denominador por visitante, janela de conversão distinta do período de recrutamento, amostra por braço, limites numéricos dos guardrails, prazo máximo e responsável. Não inferir “iniciante” ou “tráfego frio” apenas de URL sem uma definição verificável. A frase de parada do exemplo deve ser substituída por UMA regra, conforme L8, nunca escolher entre fixa e sequencial após olhar os dados.

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

**Cuidado causal:** não contar Alice como exposta não significa apagá-la da análise de todos os atribuídos. O MVP usa intenção de tratar na comparação principal. Filtrar somente quem viu pode selecionar grupos diferentes se B altera a chance de exposição. Uma análise por exposição precisa de gatilho pré-tratamento comparável nos dois braços. [Microsoft Research, análise por gatilho](https://www.microsoft.com/en-us/research/articles/patterns-of-trustworthy-experimentation-post-experiment-stage).

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
dona. O destino analítico deve receber apenas referências mínimas e fatos. Isso não torna os IDs anônimos nem dá licença para retenção ilimitada.

LGPD e minimização: livro imutável não é lugar para dado que alguém pode ter
direito de apagar. Por isso `funil.lead-capturado.v1` exige `lead_id` e não
e-mail, nome ou telefone. Quem precisar de detalhe pergunta à célula `leads`,
que é a casa desse dado.

### LGPD, cookie e retenção

O cookie atual dura um ano, usa HttpOnly, SameSite=Lax e Secure em HTTPS. Isso está em `visitante.py`; não demonstra, sozinho, conformidade. O identificador distingue navegadores com cookie persistente, não pessoas com certeza. Dois dispositivos podem gerar dois IDs; apagar cookie rompe a continuidade.

Antes de ativar medição experimental, o controlador precisa registrar finalidade, base legal aplicável, prazo necessário, transparência e mecanismo de escolha quando exigido. Ser primeira parte não isenta automaticamente um cookie analítico. A revisão de retenção e direitos precisa abranger fatos, vínculos, logs, backups e eventos mortos. [Guia de cookies da ANPD](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_cookies_e_protecao_de_dados_pessoais).

No código atual, `referrer` e UTMs entram sem uma garantia geral de remoção de informações pessoais, e `recepcao.py` guarda `data` como recebido. A proteção pretendida é parcial. FALTA aplicar lista permitida, limites e saneamento antes de persistir, inclusive na DLQ. A API de métricas não deve buscar dados da pessoa para completar evento; quem mostra detalhe autorizado é a célula dona ou a administração via contrato.

## 11. Métricas e decisão

Métrica principal é a que decide o experimento. Métrica secundária explica.
Métrica diagnóstica mostra mecanismo. Métrica de negócio confirma impacto.
Guardrail impede vitória que machuca a casa.

Exemplo hipotético, sem dados reais da Meshcraft:

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

Conversão é o comportamento definido antes do teste. CTR é taxa de clique e serve como diagnóstico de um CTA; `checkout_started` exige entrada confirmada no checkout, não clique presumido. `pedido.criado` não comprova pagamento. Receita líquida precisa declarar a fórmula: recebimentos confirmados menos devoluções e chargebacks, sem subtrair duas vezes a mesma perda; taxas entram se a definição escolhida for líquida de taxas. Reembolso é devolução; chargeback é contestação revertida pelo arranjo de pagamento.

MDE é o menor efeito escolhido para dimensionar a capacidade do teste. Não é o efeito que o teste promete achar. Significância estatística mede compatibilidade dos dados com um modelo; relevância prática pergunta se a mudança merece o custo e o risco. Janela de conversão é o tempo em que uma ação será atribuída; não se confunde com duração do recrutamento. Guardrail sem dados maduros é desconhecido, não saudável.

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

Uma flutuação pequena em torno de 50/50 é normal. SRM é desvio estatisticamente incompatível com a alocação esperada segundo o teste e limiar definidos. A falta de SRM não prova ausência de todo viés. [Microsoft Research, diagnóstico de SRM](https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/).

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

Camada é uma regra de alocação, não apenas um nome de pasta. No MVP, EXP-01 roda e EXP-02/EXP-03 aguardam. Uma camada de exclusão mútua divide públicos para que a mesma pessoa não receba intervenções incompatíveis. Camadas independentes podem sobrepor pessoas e NÃO eliminam interação automaticamente.

Headline e imagem só podem se combinar com desenho fatorial ou regra pré-especificada que identifique seus efeitos e interações, além de tráfego suficiente. Alterar preço ainda exige mandato próprio de produto/contrato. Muitos tratamentos com pouco tráfego impedem uma leitura útil. Exclusões devem ser definidas antes da atribuição, não usadas para retirar quem converteu menos.

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

Estado: FALTA para experimentação de conversão. O laboratório organizacional do admin não é evidência de um avaliador de conversão. A busca por ExperimentSpec, VariantSpec, assignment e exposure nas implementações inspecionadas não encontrou esse ciclo.

Um registro completo de aprendizado contém hipótese, audiência, contexto, controle e tratamento congelados; efeito e incerteza com unidade e janela; amostra por braço; validade da medição; decisão e responsável; generalização permitida; limites e próximos testes. “Inconclusivo por tráfego insuficiente” é um resultado útil e não uma variante perdedora. O modelo pode começar como registro estruturado simples, sem grafo.

## 16. IA no lugar correto

FORA DO ESCOPO ATUAL como automação da plataforma. Os usos abaixo são possibilidades assistidas e dependem dos gatilhos e decisões do capítulo 17.

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

A decisão de 19/09, §§6 e 7, distingue ADIADO com gatilho de descartado até nova decisão escrita. A tabela indica pré-condições técnicas; nos itens descartados elas não substituem a nova decisão. CUPED, bandits, personalização, grafo e IA de hipóteses continuam FORA DO ESCOPO ATUAL.

| Adiado | Por que fica fora da primeira versão | Gatilho de entrada |
|---|---|---|
| CUPED | não há histórico por visitante suficiente | tráfego e comportamento anterior confiáveis |
| bandits contextuais | exigem mais tráfego e controle | testes estáveis e volume alto |
| personalização automática | antes é preciso medir sem personalizar | experimentação confiável e identidade costurada |
| holdout global | mede efeito acumulado, não primeiro teste | dez vitórias embarcadas sem medição conjunta, conforme decisão §6 |
| knowledge graph completo | grafo vazio não ensina | aprendizados reais acumulados |
| geração autônoma de copy | governança vem antes de autonomia | nova decisão escrita e fluxo de aprovação; autopublicação continua proibida |
| otimização adaptativa | muda alocação e inferência | decisão específica, dados e método válido para alocação adaptativa; teste sequencial sozinho não basta |
| experimentos internacionais automáticos | idioma não herda causalidade | mercados com tráfego e métricas próprias |

## 18. O que nunca deve ser feito

- Chamada síncrona obrigatória ao avaliador de experimentos no caminho da página.
- `random()` no template.
- Variante mutável.
- Evento sem versão.
- Tratar conversão sem vínculo verificável como conversão exposta; o fato de compra continua existindo como não atribuído.
- Copy duplicada nos eventos.
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
| envelope inválido | fila de mortos; payload interno não tem validação completa hoje | nada perceptível, operador investiga |
| exposição ausente | não contar como tratado | resultado inconclusivo |
| métrica incompleta | não decidir vencedor | decisão bloqueada |
| SRM | experimento inválido ou investigação obrigatória | sem mudança na página |
| compra sem visitor_id | conversão não atribuída ao visitante | compra acontece |

## 20. Manual operacional

EXISTE o fluxo de rascunho/publicação de página em `/admin/paginas/`. FALTA construir os procedimentos experimentais da tabela. Ela especifica os aceites para a tela futura, não instrui a clicar em botões que já existam. Ao publicar hoje, salvar o rascunho, publicar e conferir a URL pública; resposta da API sozinha não é a prova completa.

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

## 21. Plano de execução do MVP

**FALTA construir o MVP. Este capítulo é o plano de implementação, não um relato de execução.** O pedido desta edição é produzir a documentação e preservar o código. Nenhum pacote abaixo foi iniciado por esta edição, e nenhum prazo de calendário é prometido sem medir tráfego e disponibilidade.

### 21.1 A entrega que encerra o MVP

O mantenedor abre a página de venda na administração, escolhe a versão publicada, escreve uma hipótese para `cubo.headline`, compara controle A e tratamento B, confere a prévia e inicia. Visitantes elegíveis recebem sempre o mesmo braço desse experimento. A tela separa atribuídos, expostos, conversões, falhas e amostras ainda imaturas. Ao encerrar, mostra um resultado reproduzível ou explica por que é inconclusivo. Uma decisão humana registra o aprendizado e, quando cabível, publica uma nova versão. Reverter publica outra versão com o conteúdo anterior.

O núcleo inclui telemetria, identidade até pedido e pagamento, avaliação local, exposição, análise, encerramento, promoção, reversão e aprendizado simples. Um experimento que só troca texto e conta cliques NÃO encerra este MVP.

Escolha do desenho (Emenda 1, 26/09/2026): uma página de `meshcraft.top`, um slot de texto, dois braços 50/50, uma métrica principal, um experimento `ativo` por `Page` (sem estado `pausado` e sem dimensão de idioma: a `Page` não tem idioma; a chave é site e slug). Nenhuma mudança de preço ou pagamento. A oferta e seus valores ficam constantes na comparação.

**Fora do caminho crítico:** editor visual de variantes, gráficos ornamentais, múltiplos tratamentos, camadas genéricas, fila automática, personalização, IA operadora, grafo, nova célula e novos serviços pagos. Corte de polimento não corta acessibilidade, segurança, diagnóstico ou recuperação.

### 21.2 De quem é cada parte

| Parte proposta | Dono inicial | Por que fica ali |
|---|---|---|
| Especificação, tratamentos imutáveis, ciclo e referência da baseline | `catalogo`, domínio de páginas | Já guarda a página e suas versões; não cria banco no funil |
| Avaliação determinística e renderização | `funil` | Decide a resposta com os dados já carregados |
| Assignment e exposição | `funil` | É quem escolhe e apresenta a versão |
| Identificação do lead | `leads` | Guarda dados da pessoa e o vínculo autorizado |
| Entrada no checkout e pedido | `checkout` | Distingue abrir checkout de criar pedido |
| Aprovação, recusa e devolução financeira | `pagamentos` | Nenhum clique pode afirmar que houve compra |
| Projeção histórica e cálculo reproduzível | `metricas` | Lê fatos |
| Formulário, resultado, decisão e aprendizado | `admin`, com persistência da decisão no domínio da página | Uma porta humana, sem segunda verdade da variante |

Essas são propostas concretas deste plano, ainda sem schemas congelados. A futura célula `experimentos` só nasce quando uma segunda superfície comprovar necessidade do mesmo controle. Camadas para dois testes na mesma página não justificam, sozinhas, essa extração.

### 21.3 Caminho crítico e ordem de entrega

```text
L0 medir e preparar a página
  |
L1 contratos mínimos
  |
L2 instrumentação ---- L3 recepção e leitura
  |                         |
  +---------- L4 painel ----+
                |
L5 identidade e fatos de negócio
                |
L6 especificação e snapshot
                |
L7 avaliador e exposição
                |
L8 inferência + L9 decisão, promoção e aprendizado
                |
L10 ensaio completo e ativação
```

A execução pode sobrepor trabalho apenas depois do contrato comum, com arquivos e bancadas independentes. Provedor integra antes do consumidor. L8 pode usar fixtures aprovadas enquanto L7 termina, mas não pode declarar entrega sem a prova real de L7. Nenhum executor está designado em segundo plano por este plano.

Cada pacote deve caber no orçamento vigente de arquivos. Se exceder, divida por provedor e consumidor, preservando o aceite do pacote. PR de contrato contém somente contratos. Não transforme esta tabela em números de tarefas fictícios: a sessão de implementação consulta a fila existente antes de abrir lacunas.

### L0. Fixar a superfície e a régua

**Entrada:** acesso à página pública e ao editor, baseline de código identificada e oferta de teste disponível. **Responsável:** sessão de implementação, com o mantenedor apenas na aprovação do conteúdo e risco de negócio.

**Ação:** conferir se a página tem promessa, prova e CTA reais; guardar a versão usada; medir visitas elegíveis, taxa principal, falhas e atraso de ingestão. Identificar tráfego interno e automações antes da alocação. Escolher métrica a partir do gargalo observado. Proposta inicial: entrada confirmada no checkout por visitante atribuído, sem chamar isso de compra.

**Alvos:** leitura de `services/catalogo/apps/paginas/`, `services/funil/apps/core/views.py`, `services/admin/apps/core/paginas.py`, contratos e decisão de 19/09. Conteúdo pela tela existente. **Contrato:** nenhum novo neste lote. **Risco:** iniciar teste sobre página vazia ou escolher métrica por conveniência.

**Saída:** URL com conteúdo aprovado; versão capturada; definição de audiência, denominador, janela, MDE e guardrails escrita; amostra necessária calculada. Sem tráfego medido, a duração fica desconhecida, nunca inventada. **Fora:** alocador.

### L1. Congelar somente as fronteiras usadas

**Entrada:** L0 e mandato explícito para os contratos afetados. **Responsável:** executor de contratos.

**Ação:** desenhar adições ao catálogo para spec, ciclo, snapshot e consulta histórica de versão; leitura agregada e linhagem em métricas; fatos de assignment, exposição, entrada de checkout e vínculo de conversão. Revisar contratos de identidade no lead e pedido sem introduzir dado pessoal no fluxo analítico.

Os quatro `funil.*.v1.json` já existem; não recriá-los. Eles não declaram experimento, variante, assignment ou exposure. Como usam `additionalProperties: false`, simplesmente enviar essas chaves hoje viola o contrato. Campo opcional exige rito aditivo; mudança incompatível exige v2 e transição de consumidores. Pela Emenda 1, `experimento_id` e `variante_id` são OPCIONAIS e sempre juntos (dependentRequired nos dois sentidos) nos quatro eventos; sem experimento ativo, nenhum dos dois aparece. Não existe campo de idioma a fechar aqui.

**Campos a fechar:** site, página, versão da página, versão da configuração, experimento, variante, assignment, exposição quando conhecida, identidade opaca, horário do fato com fuso e idempotência. O evento de pedido existente tem `customer` com e-mail e nome: criar uma projeção analítica sanitizada na célula dona antes de assinar esse fluxo no livro.

**Alvos:** `contracts/catalogo.openapi.yaml`, `contracts/metricas.openapi.yaml`, contratos de leads/checkout e `contracts/eventos/`, em lotes de contrato separados conforme necessidade. Nomes novos são propostos, não endpoints existentes.

**Provas:** fixtures válidas aceitas; versão desconhecida, mistura de site, payload com copy e dado pessoal recusados; contrato anterior continua aceito. **Saída:** fronteiras aprovadas e congeladas, com mapa provedor-consumidor e política de retenção. **Fora:** implementação dos serviços.

### L2. Emitir o que o navegador e o servidor realmente sabem

**Entrada:** L1 e página publicada. **Responsável:** executor do funil.

**Ação:** implementar seção vista e clique no navegador; lead capturado somente após resposta válida de `leads`. O template atual não possui formulário de lead: instrumentar a superfície de captura existente com contexto de página quando houver, sem inventar um formulário na oferta para satisfazer uma métrica. A confirmação deve conter `lead_id`; sucesso HTTP vazio não prova captura.

Para seção vista, registrar no máximo uma vez por seção por carregamento. Para o slot experimental, a proposta de exposição é pelo menos 50% do elemento visível por 1 segundo contínuo, com aba visível, reiniciando o relógio ao ocultar. Isso mede oportunidade de ver, nunca leitura ou atenção humana. Os critérios devem ser versionados e iguais em A e B.

Cada carregamento recebe contexto de renderização. O servidor valida site, página, versão, seção e slot contra esse contexto; não aceita o `site_id` arbitrário do navegador. Uma referência assinada com validade cobre os campos imutáveis, não autoriza compra e não leva dado pessoal. CSRF/origem e limitação de abuso seguem o padrão da célula.

Manter o mesmo `event_id` nas tentativas do mesmo fato. Hoje `telemetria.publicar` cria UUID novo a cada chamada: repetir a chamada não é deduplicação semântica. Diferenciar uma tentativa de rede repetida de dois cliques legítimos.

**Alvos:** `services/funil/apps/core/telemetria.py`, `views.py`, rotas, template e arquivo JavaScript próprio de telemetria, testes correspondentes. **Dados:** contexto de renderização, identificação opaca e fato; sem frases, e-mail ou URL completa com parâmetros livres.

**Provas:** navegador fecha sem expor, rola e volta, clica e navega imediatamente, perde resposta, reenvia e recebe confirmação do lead; Redis indisponível não bloqueia CTA nem formulário. **Saída:** cada fato de fixture aparece uma vez no stream correto e tem contrato válido. **Fora:** experimento ativo.

### L3. Fazer o livro receber, sem esconder perda ou dados pessoais

**Entrada:** contratos e emissão disponível. **Responsável:** executor de métricas; configuração de execução em lote de infraestrutura quando necessária.

**Ação:** assinar explicitamente os quatro streams na lista `STREAMS`; testar replay desde o começo, grupos, mensagens pendentes, ACK depois da gravação e reentrega. A inscrição genérica do texto da decisão não substitui essa lista concreta. O compose atual já fornece `REDIS_STREAMS_URL` ao funil; conferir o processo implantado, não adicionar env às cegas.

Definir proteção para os novos dados antes da persistência. Envelope inválido vira evento morto; falha de banco deve permanecer reentregável. Dado proibido não pode acabar inteiro na fila de mortos, no log ou na DLQ: guardar motivo e metadados sanitizados. Para eventos de negócio, o produtor entrega projeção sem `customer`; o livro não precisa consultar a pessoa.

**Alvos:** `services/metricas/apps/fatos/recepcao.py`, `management/commands/consume_eventos.py`, API de leitura e testes; infraestrutura só se a medição apontar falta. **Riscos:** ligar stream com payload pessoal; confundir processo vivo com consumidor atualizando.

**Provas:** duplicata gera um Evento; envelope ruim não entra na contagem; falha de banco reentrega; entrada com dado pessoal não persiste em nenhum destino do ensaio. **Saída:** consulta autenticada por site, página e versão reproduz a fixture e informa frescor/cobertura. **Fora:** inferência.

### L4. Mostrar o funil que existe

**Entrada:** L3 medido. **Responsável:** executor da administração.

**Ação:** construir uma tela simples com visitas, visitantes distintos, alcance por seção, cliques e leads; filtros de site, página, versão e período (sem filtro de idioma: a página não tem essa dimensão). Mostrar a definição e a procedência de cada número. Quando houver experimento, o braço de cada visitante é o `variante_id` da sua primeira `pagina-vista` daquele experimento e vale para todos os passos seguintes (Emenda 1, item 5); visitante com mais de um `variante_id` no experimento entra na contagem separada `visitantes_com_bracos_trocados`, um alarme de qualidade, nunca descartado em silêncio.

**Alvos:** cliente de métricas e tela em `services/admin/`. **Contrato:** somente a leitura congelada em L1. **Provas:** fixtures com dois sites, versões diferentes e eventos duplicados; zero verdadeiro distinto de sem coleta; serviço lento exibe carregamento, falha preserva filtros e oferece tentar novamente.

**Saída:** uma jornada de teste aparece na tela com os mesmos IDs e totais do livro; erro de rede não aparece como conversão zero. **Fora:** gráficos avançados.

### L5. Costurar visitante, lead, pedido e dinheiro

**Entrada:** telemetria visível e contratos de L1. **Responsáveis:** executores das células donas, em ordem de provedor.

**Ação:** persistir o contexto autorizado de visitante e experimento no caminho até o pedido. Identidade recebida de cookie não assinado é medição, nunca autenticação. Contexto adulterado ou de outro site é descartado da atribuição; checkout e pagamento continuam funcionando.

A referência atravessa a entrada no checkout, sobrevive à criação do pedido e à confirmação assíncrona de pagamento. O fato de compra é emitido por quem confirma pagamento, com `order_id` e uma referência opaca; a projeção histórica liga ao contexto capturado no pedido. Reembolso e chargeback referenciam o pedido original e não a variante atualmente no ar. Compra sem costura fica explicitamente não atribuída.

**Alvos:** `services/leads/`, `services/checkout/`, fronteira permitida de `services/pagamentos/`, contratos e leitura de métricas. O núcleo congelado de pagamentos permanece fora do mandato; ampliar sua fronteira exige decisão antes de editar.

**Provas:** pagamento dias depois da exposição, conversão antes de o evento de exposição chegar ao livro, múltiplas visitas, retorno após promoção, duas abas, cookie perdido, outro dispositivo e recusa/reembolso duplicados. O horário do fato decide a janela, não o horário de chegada. Regra de junção (Emenda 1, item 6): um pedido só conta para o experimento se `criado_em` (ou `pago_em`) do pedido estiver entre a primeira `pagina-vista` daquele experimento para o visitante e o fim da janela (`fim_planejado`); fora desse intervalo, o pedido fica no histórico, não atribuído àquele experimento. Evento atrasado causa nova revisão da análise, sem reescrever o fato.

**Saída:** fixture de ponta a ponta distingue entrada no checkout, pedido, compra, reembolso e conversão não atribuída; nenhum dado pessoal chega ao livro analítico. **Fora:** identidade universal entre dispositivos e atribuição multitoque.

### L6. Persistir o experimento e distribuir um snapshot seguro

**Entrada:** A e B do roadmap geral encerradas, com página real e fatos medidos. **Responsável:** executor do catálogo.

**Ação:** guardar spec e tratamentos congelados no domínio de página, amarrados a site, versão, slot e oferta (sem idioma: a `Page` não tem essa dimensão). No máximo um experimento `ativo` por `Page` (Emenda 1). Ciclo (Emenda 1, item 1): `rascunho` → `ativo` → `encerrado`, e `rascunho` → `encerrado` também vale. Sem estado `pausado`: parar um braço ruim é encerrar; retomar é abrir um experimento novo, com UUID e sorteio novos, porque pausa e retomada contaminariam o braço de quem viu `a` durante a pausa. A spec guarda `metrica_principal`, `taxa_base`, `mde` (efeito mínimo detectável, absoluto), `n_por_braco_planejado` (fórmula da DECISAO §3, alfa 0,05 bicaudal, poder 0,8) e `dias_planejados`; `fim_planejado = iniciado_em + dias_planejados`. Decisão e promoção são registros ligados ao encerramento, não reescrita do resultado.

Entregar a configuração junto ao caminho contratado de obtenção da página, sem uma nova chamada a `experimentos`. No funil, avaliar uma cópia validada localmente. Definir revisão monotônica, instante de validade e expiração. Proposta do MVP: atualização de estado em até 60 segundos; após expirar, somente baseline. Reinício sem snapshot também serve baseline quando o catálogo entrega página; se o catálogo não entregar conteúdo, preserva-se a resposta 503 atual.

Encerrar (inclusive antecipadamente, por segurança) impede novas renderizações de tratamento após a propagação do snapshot. Páginas abertas continuam podendo enviar fatos e compras tardias, dentro da janela `[iniciado_em, fim_planejado]`; não rotular essas compras como nova exposição. Redis de eventos não é o repositório exclusivo do snapshot.

**Provas:** gravação concorrente, variante alterada após revisão, spec de outro site/página, baseline divergente, snapshot corrompido, revisão antiga e expiração. Publicação concorrente exige comparação da versão esperada em transação; `base_version` atual sozinho não fornece essa proteção.

**Saída:** snapshots reproduzíveis e baseline identificável; propagação do encerramento convergente com limite medido; histórico consultável por contrato. **Fora:** serviço transversal.

### L7. Atribuir e registrar a exposição

**Entrada:** L6 e medição de L2/L3. **Responsável:** executor do funil.

**Ação:** sorteio pela fórmula canônica (DESENHO-COMUM): `balde = int(sha256(f"{experimento_id}:{visitor_id}").hexdigest()[:8], 16) % 10000`. Variantes ordenadas por `variante_id`; peso em pontos-base somando 10000 (50/50 = 5000 e 5000); a variante é a primeira cujo peso acumulado passa de `balde`. Sem site, sem idioma e sem salt de revisão na entrada do hash: determinístico e sticky sem guardar nada, porque o mesmo par experimento e visitante sempre cai no mesmo balde. Nunca usar `hash()` de processo ou `random()` do template. Visitante que retorna mantém o braço; mudar a copy ou reabrir depois de um encerramento exige experimento novo (UUID novo, sorteio novo).

Assignment registra a escolha; exposição segue o critério de visibilidade comum aos braços. Deduplicar a unidade de análise por experimento e visitante, preservando os fatos de cada visita. Se não houver cookie persistente elegível, servir baseline e registrar exclusão, sem fingir visitante recorrente.

**Cache é parte deste lote:** toda resposta do funil que inclui `experimento_ativo` sai com `Cache-Control: private, no-store` (Emenda 1, item 7); sem experimento ativo, a política de cache atual da vitrine continua valendo. Impedir que HTML com visitante, token ou variante vá para outro navegador. Testar a borda real com dois visitantes alternados, cache aquecido e service worker.

**Provas:** vetores fixos do hash (par experimento e visitante) iguais entre processos e reinícios; retorno sticky; corpus sintético grande com distribuição dentro de limites pré-fixados; isolamento entre experimentos e entre sites; resposta com `experimento_ativo` sempre `private, no-store`; falta de snapshot, de Redis e de JavaScript. Corpus sintético não substitui o SRM de produção.

**Saída:** A/A técnico com cópias idênticas percorre assignment, exposure, conversão e livro; ensaio A/B exibe só o slot permitido. **Fora:** múltiplos slots e seleção por perfil.

### L8. Produzir uma conclusão que possa ser recusada

**Entrada:** L7 e amostra/régua pré-registradas. **Responsável:** executor de métricas.

**Ação:** implementar a análise principal por intenção de tratar, isto é, por todos os visitantes elegíveis atribuídos. Exposição é medida separadamente e permite auditoria; não excluir silenciosamente os que fecharam a página. Comparação só de expostos exige gatilho que o tratamento não altere e análise causal específica.

Para o primeiro teste, proposta de horizonte fixo: uma métrica binária por visitante, 50/50, alfa bilateral 5%, poder planejado 80%, MDE definido pelo negócio. Alfa e poder são parâmetros do desenho proposto, não números medidos na Meshcraft. Usar implementação estatística validada e testes numéricos independentes. Contagem pequena exige método adequado ou conclusão de insuficiência; evitar aproximação normal inválida.

Regra única, horizonte fixo, sem peeking (Emenda 1, item 3): o experimento guarda `n_por_braco_planejado` e `dias_planejados`, e `fim_planejado = iniciado_em + dias_planejados`. Enquanto `coletando`, a tela mostra só contagens, SRM e progresso até o horizonte: NUNCA p nem intervalo de confiança. `p` e o intervalo são calculados UMA VEZ, na janela `[iniciado_em, fim_planejado]`, e ficam congelados depois disso; não recalcular a cada nova visita. Se no horizonte algum braço tiver N menor que `n_por_braco_planejado`, o veredito é `inconclusivo (amostra insuficiente)`. Se a previsão exigir mais de duas semanas ou decisão de eficácia antecipada, a decisão de 19/09 exige desenho sequencial antes do início, e este MVP não implementa peeking nem parada antecipada por p pequeno.

SRM roda em DUAS bases (Emenda 1, item 4): qui-quadrado sobre `atribuidos` e qui-quadrado sobre `expostos`, cada um contra os pesos planejados; a tela mostra expostos e atribuídos por braço. Qualquer alarme, em qualquer uma das duas bases, bloqueia `candidato à promoção`. Encerramento por segurança pode ser imediato, sem transformar o encerramento antecipado em vitória.

**Saída:** resultado com unidade, N por braço, conversões, taxa, efeito absoluto/relativo, intervalo, método, janela, maturidade, SRM (duas bases), cobertura e guardrails. Três estados (Resultado, F9): `coletando` (antes do horizonte, sem p nem IC visíveis), `inconclusivo` (horizonte atingido com amostra insuficiente, SRM alarmado, ou efeito sem significância/relevância) e `candidato à promoção` (horizonte cumprido, amostra atingida, SRM limpo nas duas bases e efeito significativo e relevante). Fixture deve produzir os três.

**Fora:** múltiplas métricas concorrendo a principal e ajuste oportunista depois da leitura.

### L9. Decidir, promover, aprender e reverter

**Entrada:** L8 reproduzível e conteúdo aprovado. **Responsáveis:** executor do catálogo para transição/persistência e executor da administração para a porta humana.

**Ação:** uma tela com hipótese, versões lado a lado, estado de coleta, resultado e motivo da decisão. Sem dados não oferece promoção. Guardrail sem amostra ou sem maturidade não recebe selo verde. Registrar análise, parâmetros, corte de dados, operador e justificativa.

Promover copia a baseline congelada e aplica apenas o tratamento aprovado, criando nova `PageVersion`. Verificar em transação se a versão corrente ainda é a esperada. Mudou por outra edição? Recusar, mostrar o conflito e exigir nova revisão; nunca sobrescrever silenciosamente. Repetir a mesma promoção retorna a mesma publicação, por chave de idempotência.

O aprendizado simples faz parte deste MVP, mesmo que a fase F organize sua busca mais tarde. Encerramento inconclusivo também gera aprendizado. Reversão cria outra publicação a partir do conteúdo anterior e registra motivo, preservando todas as versões.

**Saída:** iniciar, encerrar (inclusive antecipadamente), decidir, promover e reverter funcionam pelo admin; sem estado `pausado` no meio do caminho; recarga e duplo clique não duplicam efeitos; histórico e aprendizado abrem depois da promoção. **Fora:** editor rico, taxonomias extensas e automação decisória.

### L10. Provar da cadeira do visitante e do mantenedor

**Entrada:** todos os lotes anteriores e ambiente isolado com provedores de pagamento em modo de teste. **Responsável:** sessão de implementação.

**Roteiro de aceite:** criar hipótese; publicar baseline; aprovar variantes; iniciar A/A; executar duas identidades controladas; confirmar sticky, exposição e conversão; desligar Redis; conferir que a página abre; restaurar; conferir lacuna declarada; encerrar antecipadamente um braço de teste e confirmar que ele não recebe mais tratamento nem pode ser retomado (só um experimento novo); encerrar fixture no horizonte; conferir cálculo (p e IC só aparecem depois do horizonte, nunca antes); registrar decisão e aprendizado; promover; abrir URL pública; reverter; abrir histórico.

Repetir para site errado, versão concorrente, cookie inválido, evento duplicado, pagamento tardio (dentro e fora da janela `[iniciado_em, fim_planejado]`) e SRM induzido nas duas bases. Não fazer cobrança real para provar software. Fixture artificial fica fora da análise de visitantes reais.

**Saída:** vídeo ou sequência de telas, IDs rastreáveis, saídas de testes e prova pública da versão; nenhum caminho exige terminal do mantenedor. **MVP funcional:** o ciclo completo funciona inclusive quando conclui “inconclusivo”. **Experimento validado em produção:** exige tráfego real e janela madura; não é a mesma declaração.

### 21.4 A conta do tempo e o freio de escopo

```text
tempo até decisão =
tempo de construção e validação
+ tempo de recrutamento necessário
+ janela de maturação
+ tolerância de ingestão
```

A estimativa de recrutamento divide a amostra total pelos visitantes elegíveis novos por dia, respeitando os braços e exclusões. Exemplo didático, não medição do site: 1.000 visitantes necessários e 100 elegíveis por dia pedem cerca de 10 dias de recrutamento, além da maturação. Não aumentar o MDE escondido para prometer resultado mais rápido.

Ao fim de cada lote, a sessão registra critério encerrado, evidência e próxima dependência. Falha herdada não vira correção geral da fábrica. Lacuna fora do mandato vai à fila; bloqueio obrigatório impede o lote dependente e libera somente trabalho independente. Números de fila e datas vêm das fontes reais na abertura da implementação.

A próxima execução técnica, quando autorizada, começa por L0: medir página, telemetria e tráfego atuais e registrar o contrato de execução. Este plano não autoriza migração, mudança de API pública, alteração financeira nem ativação de tratamentos em produção por inferência.

### 21.5 Roadmap completo, sem confundir evolução com MVP

| Fase | Objetivo e dados | Células/contratos | Testes e risco principal | Critério de saída | O que fica de fora |
|---|---|---|---|---|---|
| A Telemetria, L0 a L4 | Visita, seção, clique e lead por versão | Funil, métricas e admin; quatro contratos existentes e leitura aditiva | Replay, payload inválido, perda e duplicata; risco de zero falso | Jornada real de teste aparece no painel com cobertura | Assignment |
| B Identidade, L5 | Visitante, lead, pedido, compra e devolução | Células donas; contratos opacos de ligação e projeção de negócio | Compra tardia e privacidade; risco de ligar pessoa errada | Pedido rastreável à coorte, sem PII no livro | Identidade entre dispositivos |
| C Primeiro experimento, L6/L7 | Spec, A/B 50/50, assignment e exposure | Domínio de páginas no catálogo, funil e contratos novos | Sticky, cache, baseline e snapshot; risco de servir variante errada | A/A instrumentado e A/B controlado sem dependência síncrona adicional | Vários tratamentos |
| D Governança, L8/L9/L10 | MDE, amostra, SRM, incerteza, decisão e promoção | Métricas, catálogo e admin; leitura e transição versionadas | Recusa de promoção inválida, concorrência e reversão | Ciclo completo comprovado; resultado inconclusivo aceito | Decisão autônoma |
| E Orquestração, ADIADO | Audiências, camadas e fila | Domínio da página; extração transversal só com segunda superfície | Interações e exclusão mútua; risco de contaminação | Dois testes simultâneos têm alocação auditável sem colisão | Bandits |
| F Aprendizado organizado, ADIADO | Busca e taxonomia sobre aprendizagens que o MVP já registra | Domínio dono e admin; contrato de consulta quando necessário | Contexto preservado e contradições visíveis | Busca encontra decisões por audiência, hipótese e limites | Grafo completo |
| G IA e avançado, FORA DO ESCOPO ATUAL | Apoio analítico sobre histórico confiável | Fronteiras aprovadas; sem nova API especulativa | Reprodução de análises e barreira contra autopublicação | Nova decisão formal para os itens descartados, seguida de piloto auditado | Autopublicação e extrapolação internacional |

O gatilho de E é concorrência real de testes na mesma página. O gatilho de F é dificuldade concreta para recuperar aprendizados existentes. Para G, dados suficientes são necessários, mas não revogam a decisão de 19/09 que descartou CUPED, bandits, personalização, grafo e IA de hipóteses até nova decisão escrita.

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
- no máximo um experimento `ativo` por `Page` (sem idioma como dimensão, Emenda 1);
- ausência de dados pessoais nos eventos.

EXISTE: parte dessa lista já existe para página, visitante, evento e livro de
fatos. FALTA: guardas de assignment, exposure, SRM, promoção e aprendizado.

### Matriz de provas que fecha os invariantes

| Guarda | Prova positiva | Mutação que deve falhar |
|---|---|---|
| Versão imutável | save, update e SQL recusam alteração | retirar trava do banco e tentar UPDATE |
| Assignment sticky | mesmos vetores produzem mesmo braço após reinício | salt ou hash dependente do processo |
| Distribuição | corpus fixo atende intervalo pré-especificado; produção tem SRM medido | deslocar limite de B |
| Exposure separado | aba oculta e slot não visto não emitem | emitir no carregamento do servidor |
| Baseline | snapshot inválido/expirado mantém conteúdo padrão | exceção que derruba a resposta |
| Sem copy | payload só contém chaves contratadas | acrescentar texto da headline |
| Página e versão | evento recupera o conteúdo correto | trocar versão pelo valor corrente |
| Visitante persistente | retorno válido mantém UUID | regenerar a cada requisição |
| Idempotência | reentrega mantém uma ocorrência | gerar UUID novo no retry do mesmo fato |
| SRM | fixture enviesada bloqueia resultado | ignorar alarme na promoção |
| Promoção | nova versão idempotente e baseline esperada | promover sobre edição concorrente |
| Histórico | aprendizado abre a versão anterior | consultar só versão corrente |
| Sites | site B não lê nem atribui evento de A | remover filtro de tenant |
| Braço fixo | expostos e convertidos contam pelo braço da primeira `pagina-vista`, mesmo se o evento seguinte trouxer outro `variante_id` | contar pelo `variante_id` de cada evento |
| Sem `pausado` | banco recusa transição para um estado `pausado` inexistente; retomar sempre gera experimento novo | reintroduzir estado `pausado` |
| Privacidade | PII recusada/sanitizada antes de log, livro e fila de mortos | copiar customer, querystring ou referrer bruto |
| Conversão tardia | compra válida chega antes/depois da exposição e reconcilia pela data do fato, dentro de `[iniciado_em, fim_planejado]` | juntar pela ordem de chegada |
| Cache do experimento | resposta com `experimento_ativo` sai com `Cache-Control: private, no-store` | servir HTML cacheado de A para B |
| Instrumento quebrado | falha de conexão mostra ERROR ou desconhecido | converter exceção em taxa zero |

Guardas experimentais desta tabela estão FALTA. Para cada implementação, executar proteção presente, removê-la em cópia isolada, registrar o teste vermelho e restaurar para obter verde. Não remover trava nem fabricar tráfego em produção para demonstrar a mutação. Não criar teste que apenas confira constantes que ele próprio acabou de definir.

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
Baseline vence, ou o experimento é encerrado e investigado (sem estado `pausado`: retomar é abrir um experimento novo).

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
| exposure | registro de visibilidade segundo critério definido; não prova atenção ou leitura |
| conversão | comportamento medido |
| audiência | grupo elegível para o teste |
| camada | espaço de exclusão para testes simultâneos |
| alocação | porcentagem de tráfego por variante |
| MDE | menor efeito que vale detectar |
| SRM | desvio entre divisão planejada e observada |
| guardrail | métrica que impede vitória perigosa |
| inferência | cálculo que estima efeito e incerteza |
| intervalo de confiança | faixa calculada por método com cobertura de longo prazo declarada; não uma probabilidade posterior sobre este intervalo |
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

1. A página é a superfície; o aprendizado é o ativo.
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
- A ausência de dados pessoais é requisito; as lacunas atuais de saneamento e recepção foram explicitadas, sem certificar proteção inexistente.
- Assignment e exposure foram separados.
- Baseline e fallback foram explicados.
- Itens adiados têm motivo e gatilho.
- Cada fase tem critério de saída verificável.
- A jornada começa na cadeira do visitante e termina na decisão.
- A célula `experimentos` ficou futura, condicionada a segundo dono real.
