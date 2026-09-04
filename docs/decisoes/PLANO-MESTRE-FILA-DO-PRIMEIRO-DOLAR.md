<!-- ============================================================================
     ESTE ARQUIVO É O TEXTO DO MANTENEDOR, SEM EDIÇÃO.

     Origem: C:\Users\davia\OneDrive\Documentos\sitesdoreino-docs\
             plano-mestre-fila-do-primeiro-dolar.md (fora do repositório),
             trazido por ele em 03/09/2026 com o pedido "quero implementá-lo
             no site". Versão 0.1, rascunho para aprovação dele.

     O que VALE como lei desta casa é `DECISAO-fila-do-primeiro-dolar.md`,
     que promove este plano, copia a seção 3 dele literalmente e registra as
     EMENDAS: os pontos em que o plano, escrito fora deste repositório, pede
     algo que um portão daqui recusa (contrato congelado antes da porta de
     máquina, teste vermelho na main) ou que uma decisão anterior do próprio
     mantenedor já fechou (a escola é 18+, o portfólio mora no Estúdio,
     dinheiro por último). Onde os dois divergirem, a DECISAO vence; e uma
     versão 0.2 deste plano só nasce da resposta dele à pergunta estruturada
     da Fase 0, nunca da mão de um agente.

     Este documento NÃO é painel: não guarda estado. "Isto já foi feito?" se
     responde no livro (painel/registros/) e na fila (fila/).
     ============================================================================ -->

# Fila do Primeiro Dólar — Plano Mestre

**Produto:** marketplace de encomendas 3D da Meshcraft Academy (meshcraft.top)
**Versão:** 0.1 — rascunho para aprovação do dono
**Data:** 3 de setembro de 2026
**Origem:** desenho base (uma fila, uma regra) + revisão antes do cliente e briefing blindado (Gemini) + elegibilidade × prioridade, passar com motivo, cancelamento, espera estimada, entidade Oferta e tela de plantão (GPT)

---

## 0. Como usar este documento

- **Seções 1–6** são o produto e as regras: o que o dono aprova. Nenhuma linha de código depende de opinião de agente; depende deste texto.
- **Seções 7–10** são a arquitetura e os invariantes: o que os agentes implementam e o que os testes-guarda protegem.
- **Seções 11–13** são o roadmap, o backlog e as métricas: a ordem de construção, os portões entre fases e como saber se está funcionando.
- **Seções 14–17** são riscos, decisões pendentes, glossário e anexos (textos de tela, cenários de aceite).

Regra do documento: **nenhuma fase começa sem o portão da anterior fechado pelo dono.** Calma é método, não lentidão.

---

## 1. Propósito e promessa

O momento mais difícil da carreira de um modelador é sair do zero: ninguém contrata quem nunca entregou, e ninguém entrega sem ser contratado. A Fila do Primeiro Dólar existe para atravessar exatamente esse ponto — uma vez por aluno.

**Promessa ao aluno:** seu primeiro dólar tem data. Você termina o curso, entra na fila e recebe uma encomenda do seu nível, com preço fechado, briefing fechado e alguém revisando antes de o cliente ver.

**Promessa ao cliente:** peça, pague, receba. Sem escolher freelancer, sem comparar propostas, sem negociar com um adolescente. A garantia é a escola.

O marketplace é uma rampa, não um destino. Depois da primeira entrega, o aluno ganha o portfólio e o botão de pedido direto, e passa a conquistar os próprios clientes — usando a plataforma para receber com segurança.

---

## 2. Princípios de desenho (inegociáveis)

1. **A plataforma escolhe o aluno, não o cliente.** Nunca haverá lista de freelancers, propostas ou lances.
2. **Uma fila, uma regra.** Quem entregou menos vai primeiro; empate, quem está na fila há mais tempo.
3. **Elegibilidade vem da Banca; prioridade vem das entregas.** O título diz o que o aluno pode receber; as entregas dizem quando.
4. **Passar é grátis.** Passar, silenciar ou pausar nunca muda o lugar na fila. Só abandonar muda.
5. **O cliente nunca vê a complexidade.** Cardápio de três cartões, quatro passos, uma linha de rastreio.
6. **Uma tela, três estados** para o aluno: na fila, oportunidade, em andamento. Uma criança de 12 anos entende sem tutorial.
7. **Tudo dentro da plataforma.** Pagamento retido, comunicação estruturada, arquivos, aprovação — inclusive para clientes que o aluno trouxe.
8. **Nenhuma primeira entrega chega ao cliente sem um humano olhar.**
9. **A escola é o primeiro cliente.** A fila só vale se houver pedido.
10. **Nomes em português**, no vocabulário que a escola já tem: Encomenda, Banca, Marcos, Degraus.
11. **Menores em primeiro lugar:** sem contato direto, sem dado pessoal exposto, repasse ao responsável.
12. **Parâmetros são configuração, não código.** Todo número deste documento (3h, 24h, 48h…) vive numa tabela editável pelo dono, com rito de mudança.

---

## 3. Escopo da v1 e o que fica fora

### Dentro

- Cardápio de três cartões (item simples, vestível/veículo, personagem), com preço fixo nos dois primeiros e sob orçamento no terceiro
- Fila do Primeiro Dólar: ofertas sequenciais, passar com motivo, pausa automática, chamada aberta
- Briefing blindado, entrega com checklist, auditoria automática, revisão humana, aprovação explícita ou tácita, uma correção
- Pagamento retido e repasse ao aluno (ou ao responsável)
- Portfólio público automático e pedido direto
- Tela de plantão do professor (revisão, reclassificação, mediação, cliente novo)
- Eventos para a gamificação (Marcos #3 e #4) e cerimônia do primeiro dólar
- Espera estimada para o aluno, rastreio para o cliente

### Fora — dito explicitamente para nenhum agente "melhorar" por conta própria

- Chat livre entre cliente e aluno
- Escolha de freelancer, propostas, lances, ranking, notas públicas
- Matriz de competências por categoria (o título da Banca é a matriz)
- Percentuais de distribuição entre níveis (a cascata faz isso)
- Orçamento livre nos níveis 1 e 2
- Equipes, líder de projeto, mais de uma encomenda da fila por vez
- Matchmaking por IA; classificação de briefing por IA
- Cliente escolher o nível do modelador
- App nativo (v1 é web responsiva, mobile-first)
- Qualquer nome em inglês na interface

---

## 4. Atores e papéis

| Papel | Quem é | O que faz |
|---|---|---|
| **Aluno** | Formado com título de Banca (ou curso concluído, até a formação existir) | Fica na fila, aceita ou passa, produz, entrega, publica portfólio |
| **Responsável** | Adulto vinculado ao aluno menor de idade | Titular da conta de recebimento; recebe cópia das notificações-chave |
| **Cliente** | Estúdio Roblox, dono de loja UGC, criador de conteúdo, outro aluno, ou a escola | Escolhe no cardápio, preenche o briefing, paga, aprova |
| **Escola-cliente** | A própria Meshcraft | Abre encomendas reais e pagas toda semana, sobretudo no lançamento |
| **Revisor** | Professor no início; depois, alunos com título Nível 3, pagos por revisão | Olha a entrega antes do cliente; aprova ou devolve com notas |
| **Plantão** | Professor / equipe da escola | Reclassifica, media disputas, aprova cliente novo, acompanha atrasos e pedidos de ajuda |
| **Dono** | Açaí | Aprova regras, parâmetros e preços; fecha os portões das fases |

---

## 5. O produto

### 5.1 Cardápio do cliente

Três cartões, por tipo de item. O tipo define nível, preço e prazo; o cliente nunca escolhe "nível de modelador".

| Cartão | O que é (7 Degraus) | Nível da encomenda | Prazo de produção | Preço |
|---|---|---|---|---|
| **Item simples** | prop, arma, acessório rígido (degraus 1–3) | Iniciante | 3 dias | fixo (tabela) |
| **Vestível ou veículo** | cabelo, roupa layered, veículo (degraus 4–6) | Intermediário | 7 dias | fixo (tabela) |
| **Personagem** | corpo/cabeça (degrau 7), rigging, animação | Avançado | 14 dias | sob orçamento |

**Letra miúda de cada cartão** (o guarda de dificuldade): quantidade de peças (1), limite de triângulos, com ou sem rig, com ou sem animação, textura (simples ou PBR), formatos entregues, uma correção incluída. É a letra miúda que impede alguém de "achar" que o pedido é simples.

O que não está nos 7 Degraus (mapas, cenários, sistemas de jogo) não está no cardápio.

**Prazo prometido ao cliente = prazo de produção + 1 dia de revisão.**

### 5.2 Briefing blindado

O formulário do cliente é o Padrão Meshcraft de Entrega visto do outro lado: as perguntas que o aluno responde ao entregar, o cliente responde ao pedir.

Campos: item (herdado do cartão) · nome da peça · onde vai ser usada (UGC / jogo próprio / outro) · 1 a 5 imagens de referência · estilo (lista fechada + campo curto) · cores principais · limite técnico (preenchido pelo cartão, editável só para baixo) · formato final (.fbx + texturas + versão pronta para o Roblox, por padrão) · observações (até 500 caracteres). **Sem campo de contato.**

O aluno recebe um briefing que já é o checklist da entrega. Uma spec, dois lados.

### 5.3 Jornada do cliente — quatro passos

1. **Descreva.** Escolhe o cartão, preenche o briefing.
2. **Confirme.** Vê preço, prazo prometido e entregáveis.
3. **Pague.** Pix ou cartão; o valor fica retido.
4. **Acompanhe.** Uma linha: *Procurando seu modelador → Ana aceitou → Em produção → Em revisão → Entregue.* Na entrega: **Aprovar** ou **Pedir um ajuste**. Silêncio de 48h aprova.

Cliente novo: a primeira encomenda passa pelo plantão antes de entrar na fila (meta: menos de 4h em horário útil). É proteção de menores, não burocracia.

### 5.4 Jornada do aluno — uma tela, três estados

1. **Na fila.** "Você está na Fila do Primeiro Dólar. Sua vez: em cerca de 3 dias." Um interruptor: Disponível / Indisponível. Nada mais.
2. **Oportunidade.** Cartão com título, valor que o aluno recebe, prazo, referência, entregáveis e a frase "Este trabalho está dentro do seu nível." Dois botões: **Aceitar** e **Passar**. Relógio visível. Passar abre quatro motivos, um toque: *Sem tempo agora · Valor baixo · Não curto esse tipo · Ainda não me sinto pronto(a).*
3. **Em andamento.** Briefing, prazo, perguntas ao cliente (estruturadas, até 3), botão **Entregar**. "Enviado para revisão" e "Aguardando o cliente" são sub-estados deste, não telas novas.

A espera estimada substitui a posição: o número que o aluno quer não é "7º", é "quando chega a minha vez". Calculada por posição × ritmo recente de encomendas do nível. Se der semanas, não se esconde — é o indicador que diz à escola quantas encomendas abrir.

### 5.5 Entrega, auditoria, revisão, aprovação

- **Entregar** abre o checklist do Padrão Meshcraft de Entrega e a autoavaliação STUDS; o aluno envia .fbx/.blend, texturas e prévia.
- **Auditoria automática** roda na hora (Blender headless): triângulos, dimensões e escala, presença de UV, tamanho de textura, nomenclatura. Falha bloqueia com mensagem clara ("Escala fora do padrão"); o aluno corrige antes de qualquer humano ver.
- **Revisão humana:** obrigatória na primeira entrega de cada aluno; depois, por amostragem. Revisor tem 24h; aprova ou devolve com notas (devolução do revisor não consome a correção do cliente). Sem ação em 24h, escala para o plantão — nunca vai ao cliente sem revisão.
- **Cliente:** Aprovar, ou Pedir um ajuste (uma vez, com texto estruturado). Segundo pedido → mediação pelo plantão. Silêncio de 48h = aprovado.
- **Aprovada** → repasse, portfólio, Marcos, cerimônia.

### 5.6 Portfólio e pedido direto

Na primeira aprovação, `meshcraft.top/@usuario` entra no ar: nome de exibição (sem sobrenome para menores), título de Banca, peças aprovadas com selo "Encomenda Meshcraft", contadores "entregas" e "no prazo". Sem contato, sem nota, sem idade.

Botão **Encomendar direto**: o cliente cai no mesmo cardápio, briefing e pagamento, mas a encomenda vai direto para aquele aluno, sem fila. Cliente que o aluno trouxe do Discord, YouTube ou grupos usa a mesma esteira — dinheiro retido, revisão, Marcos.

Peças só aparecem com autorização do cliente (caixa marcada por padrão no checkout). Pedidos diretos contam como entregas (para prioridade e Marcos), mas não ocupam a vaga única da fila.

### 5.7 Plantão do professor

Uma lista, ordenada por urgência: encomendas atrasadas · entregas aguardando revisão há mais de 12h · pedidos de ajuda (aluno ou cliente) · encomendas para reclassificar · clientes novos aguardando aprovação · mediações abertas · repasses bloqueados (aluno sem responsável). Cada item tem uma ação de um clique. É a rede de segurança dos primeiros meses.

### 5.8 Cerimônia e Marcos

Primeira aprovação: tela cheia — "Você ganhou seu primeiro dólar com 3D." Essa tela **é** o Marco #3 (Primeiro Dólar). Primeira aprovação vinda de um cliente que não seja a escola (fila ou direto) carimba o Marco #4 (Primeiro Cliente Real). Sem título novo: os títulos são os da Banca.

---

## 6. Livro de regras

### 6.1 Elegibilidade — o que o aluno pode receber

- **Iniciante:** título Modelador Nível 1 (ou curso concluído, até a formação existir).
- **Intermediário:** título Nível 2 **e** pelo menos 1 entrega aprovada.
- **Avançado:** título Nível 3 (quando a Parte III existir) **e** 5 entregas aprovadas **e** nenhum abandono nos últimos 90 dias.
- Idade mínima e responsável vinculado: decisão pendente (seção 15).

### 6.2 Prioridade — quando recebe

Entre os elegíveis e disponíveis: **menos entregas aprovadas primeiro; empate, data de entrada na fila mais antiga.** Data de entrada = quando o aluno ativou a fila pela primeira vez. Só o abandono a altera (vai para o fim).

### 6.3 Oferta

- Uma encomenda tem no máximo uma oferta pendente; um aluno tem no máximo uma oferta pendente.
- Relógio: 3 horas, correndo só das 8h às 22h (Brasília). Fora da janela o relógio congela.
- **Aceitar:** reserva a encomenda; o aluno vira "trabalhando".
- **Passar:** instantâneo, com motivo; a oferta vai para o próximo; o aluno mantém o lugar e não recebe essa encomenda de novo (salvo se ela virar aberta).
- **Silêncio:** expira; vai para o próximo; sem punição. Três silêncios consecutivos → pausa automática ("Você parece estar ocupado(a)"); o aluno religa e volta ao mesmo lugar. Um Aceitar ou Passar zera a contagem.

### 6.4 Chamada aberta

Encomenda há 24h na fila sem aceite (ou sem elegíveis disponíveis) vira **Aberta**: todos os elegíveis são avisados; o primeiro que aceitar leva. O nível mínimo continua valendo.

### 6.5 Uma por vez

Aluno com encomenda da fila ativa não recebe ofertas. Pedidos diretos não ocupam essa vaga.

### 6.6 Prazo, extensão e abandono

- Prazo de produção pelo cartão. **Extensão:** uma, de 48h, pedida até 24h antes do prazo; o cliente é avisado com a nova data.
- Prazo vencido (com extensão, se houve) sem entrega = **abandono**: a encomenda volta à fila (nova rodada de ofertas, sem esse aluno), o aluno vai para o fim da fila, o cliente é avisado com nova previsão. Segundo abandono em 90 dias: pausa de 30 dias.
- Entregar asset comprado ou copiado como se fosse próprio = abandono + suspensão pelo plantão.

### 6.7 Cancelamento

- Cliente cancela **antes do aceite:** reembolso integral; nada acontece com ninguém.
- Cliente cancela **após o aceite:** vai para mediação; o aluno **mantém** o lugar e a contagem (não é entrega nem abandono); o plantão decide reembolso parcial ou integral e registra.
- Cliente some **após a entrega:** 48h de silêncio aprovam; o aluno recebe.
- Problema técnico comprovado (arquivo do cliente, referência impossível): o plantão devolve a encomenda à fila sem penalidade ao aluno.

### 6.8 Revisão

Primeira entrega de cada aluno: obrigatória. Demais: amostragem (parâmetro). Revisor: professor até existir Nível 3; depois, alunos Nível 3 pagos por revisão, nunca revisando a própria encomenda. SLA de 24h com escalonamento ao plantão.

### 6.9 Aprovação e correção

Aprovação explícita ou tácita (48h). Uma correção incluída, com prazo de 48h para o aluno; a segunda vai para mediação.

### 6.10 Dinheiro

- Encomenda só entra na fila após confirmação do pagamento (webhook).
- Valor retido até a aprovação. Repasse = valor − taxa, no dia útil seguinte à aprovação (parâmetro).
- Menor de idade: repasse só para conta de responsável verificado; sem responsável, o repasse fica bloqueado e o plantão é avisado. O aluno nunca perde o valor.
- Taxa do nível 1 destinada ao revisor (decisão pendente).
- Reembolso só antes do aceite (automático) ou por decisão de mediação registrada.

### 6.11 Reclassificação

Dois "Ainda não me sinto pronto(a)" na mesma encomenda → ela sai da fila para o plantão reclassificar (sobe de nível e ajusta preço com o cliente, ou cancela com reembolso). Três do mesmo aluno em 30 dias → aviso ao professor para conversar. Nunca punição.

### 6.12 Parâmetros iniciais (todos configuráveis)

| Parâmetro | Valor inicial |
|---|---|
| Relógio da oferta | 3h |
| Janela do relógio | 8h–22h (America/Sao_Paulo) |
| Silêncios consecutivos para pausa automática | 3 |
| Tempo na fila para virar Aberta | 24h |
| Encomendas da fila simultâneas por aluno | 1 |
| Prazo de produção (simples / vestível-veículo / personagem) | 3 / 7 / 14 dias |
| Dia de revisão somado ao prazo prometido | 1 |
| Extensão | 1 × 48h, pedida até 24h antes |
| SLA do revisor | 24h |
| Amostragem de revisão após a primeira entrega | 1 em 5 |
| Aprovação tácita do cliente | 48h |
| Correções incluídas | 1 (prazo 48h) |
| Passes "não me sinto pronto" para reclassificar | 2 na mesma encomenda |
| Passes "não me sinto pronto" para aviso ao professor | 3 em 30 dias |
| Repasse após aprovação | próximo dia útil |
| Aprovação de cliente novo pelo plantão | meta de 4h úteis |
| Entregas para o nível avançado | 5 |
| Janela de "nenhum abandono" | 90 dias |
| Pausa por segundo abandono | 30 dias |

Rito de mudança: o dono altera na tabela, a mudança fica registrada com data e motivo, e nenhum valor vive em código.

---

## 7. Modelo de domínio

### 7.1 Entidades

- **PerfilProfissional** (um por aluno): `titulo_banca`, `disponibilidade` (disponivel / pausado / trabalhando), `data_entrada_fila`, `entregas_aprovadas`, `silencios_consecutivos`, `abandonos` (datas), `responsavel_id`, `conta_repasse_id`, `portfolio_publicado_em`.
- **Encomenda**: `origem` (fila / direto / escola), `cliente_id`, `cartao`, `nivel`, `briefing` (json), `preco`, `taxa`, `prazo_producao`, `prazo_prometido`, `status`, `aluno_id`, histórico de status com autor, `autorizacao_portfolio`, `pagamento_id`.
- **Oferta**: `encomenda_id`, `aluno_id`, `oferecida_em`, `expira_em` (calculado com a janela), `resultado` (pendente / aceita / passou / expirou / cancelada), `motivo_passe`, `respondida_em`. Registro de primeira classe: é o histórico, a auditoria de justiça e a fonte dos três usos do passar com motivo.
- **Entrega**: `encomenda_id`, arquivos, `checklist` (json), `studs_auto` (json), `auditoria` (aprovada / reprovada + itens), `versao` (1 ou 2).
- **Revisao**: `entrega_id`, `revisor_id`, `resultado` (aprovada / devolvida), `notas`, `prazo`.
- **Correcao**: `encomenda_id`, pedido do cliente (estruturado), `prazo`.
- **Mediacao**: `encomenda_id`, motivo, decisão, reembolso, `registrada_por`.
- **Cliente**: referência à célula `identidade`; `status` (novo / aprovado / bloqueado).
- **Portfolio** (materializado): `aluno_id`, peças (`encomenda_id`, imagem, título, autorizado).
- **Repasse** (vive na célula de pagamentos): `encomenda_id`, valor, destino, status.

### 7.2 Máquinas de estado

**Encomenda**

```
aguardando_pagamento → na_fila → oferecida → em_producao → entregue → em_revisao
  → aguardando_cliente → aprovada → concluida

Desvios:
  oferecida → na_fila            (passe ou expiração)
  na_fila | oferecida → aberta → em_producao
  na_fila | oferecida → para_reclassificar → na_fila | cancelada
  entregue → em_producao         (auditoria automática reprovou)
  em_revisao → em_producao       (revisor devolveu)
  aguardando_cliente → em_correcao → entregue
  em_producao → abandonada → na_fila
  qualquer estado ativo → em_mediacao → aprovada | cancelada
  aguardando_pagamento | na_fila → cancelada
```

**Oferta**

```
pendente → aceita | passou | expirou | cancelada
```

**PerfilProfissional (disponibilidade)**

```
disponivel ⇄ pausado                 (manual ou automático)
disponivel → trabalhando             (aceite)
trabalhando → disponivel             (aprovada, abandono, mediação encerrada)
```

### 7.3 Eventos

Stream `encomendas` no Redis Streams. Envelope: `id`, `tipo`, `versao`, `ocorrido_em`, `chave_idempotencia`, `dados`.

`encomenda.paga` · `encomenda.oferecida` · `oferta.aceita` · `oferta.passou` · `oferta.expirou` · `encomenda.aberta` · `encomenda.entregue` · `entrega.auditada` · `entrega.revisada` · `encomenda.aguardando_cliente` · `encomenda.correcao_pedida` · `encomenda.aprovada` · `encomenda.concluida` · `encomenda.abandonada` · `encomenda.cancelada` · `encomenda.em_mediacao` · `aluno.pausado` · `aluno.disponivel` · `portfolio.publicado` · `pedido_direto.criado`

Consumidores: gamificação (Marcos), notificações, pagamentos (repasse em `encomenda.aprovada`; responde com `repasse.efetuado`), métricas. Ninguém lê o banco de ninguém.

### 7.4 Algoritmo de oferta

```
gatilhos: encomenda.paga | oferta.passou | oferta.expirou | encomenda.abandonada | tique (1/min)

para cada encomenda em na_fila, da mais antiga para a mais nova:
  se idade_na_fila >= 24h            → virar aberta; continuar
  elegiveis = perfis com titulo >= nivel_minimo(encomenda)
              e (nivel == iniciante ou entregas_aprovadas >= minimo_do_nivel)
              e sem abandono recente quando o nível exigir
              e disponibilidade == disponivel
              e sem oferta pendente
              e sem oferta anterior nesta encomenda
  se vazio                            → virar aberta; continuar
  escolhido = min(elegiveis, chave = (entregas_aprovadas, data_entrada_fila))
  criar Oferta(pendente, expira_em = agora + 3h úteis dentro da janela)
  emitir encomenda.oferecida

tique: para cada oferta pendente com expira_em <= agora
  → expirou; silencios_consecutivos += 1; se == 3 → pausar aluno; reavaliar encomenda
```

Propriedades obrigatórias:
- O motor é função de (estado atual, agora). Rodar duas vezes seguidas não cria duas ofertas (trava por encomenda).
- Relógios não são timers agendados; são reavaliação periódica. Sobrevive a reinício, deploy e queda do Redis.
- O cálculo de "horas úteis" (8h–22h, fuso de São Paulo) é uma função única, pura e testada.

---

## 8. Arquitetura

### 8.1 Uma célula nova: `encomendas`

Responsável por: perfis profissionais, fila, ofertas, encomendas, entregas, revisões, correções, mediações, portfólio, pedidos diretos, plantão. Banco próprio. API HTTP versionada. Emite os eventos da seção 7.3. Constituição própria escrita na Fase 0, com a seção 3 (fora de escopo) copiada literalmente.

### 8.2 O que não entra nela

- **Dinheiro.** Cobrança, retenção, taxa, repasse e reembolso ficam na célula de pagamentos (a que fala com o Mercado Pago). `encomendas` só sabe "pago", "repassado", "reembolsado" — por webhook interno e eventos.
- **Identidade.** Quem é aluno, cliente, responsável, professor — célula `identidade`. `encomendas` guarda ids e o vínculo aluno → responsável só como referência.
- **Gamificação.** Consome eventos. `encomendas` não sabe o que é Marco.
- **Notificações.** Consumidor separado, no canal decidido (seção 15).
- **Auditoria automática.** Worker próprio (imagem com Blender headless), chamado de forma assíncrona; resultado volta por `entrega.auditada`.

### 8.3 Contrato HTTP v1 (congelado na Fase 0)

**Cliente:** `GET /v1/cardapio` · `POST /v1/encomendas` · `GET /v1/encomendas/{id}` · `POST /v1/encomendas/{id}/aprovar` · `POST /v1/encomendas/{id}/pedir-correcao` · `POST /v1/encomendas/{id}/cancelar`

**Aluno:** `GET /v1/minha-fila` · `PUT /v1/minha-fila/disponibilidade` · `GET /v1/ofertas/atual` · `POST /v1/ofertas/{id}/aceitar` · `POST /v1/ofertas/{id}/passar` · `POST /v1/encomendas/{id}/perguntar` · `POST /v1/encomendas/{id}/entregar` · `POST /v1/encomendas/{id}/pedir-extensao`

**Revisor e plantão:** `GET /v1/plantao` · `POST /v1/entregas/{id}/revisar` · `POST /v1/encomendas/{id}/reclassificar` · `POST /v1/encomendas/{id}/mediar` · `POST /v1/clientes/{id}/aprovar`

**Público:** `GET /v1/portfolios/{usuario}` · `POST /v1/pedidos-diretos`

**Interno:** `POST /v1/interno/pagamentos/confirmado` (da célula de pagamentos) · `POST /v1/interno/auditoria/resultado` (do worker)

### 8.4 Extensão da célula de pagamentos

Capacidades novas: cobrança vinculada a uma encomenda; retenção até `encomenda.aprovada`; repasse para conta do aluno ou do responsável; reembolso por decisão registrada; conservação (pago = repasse + taxa + reembolso). O mecanismo — split do Mercado Pago ou receber e repassar via Pix — é decisão pendente que depende de parecer contábil/jurídico. Cada mudança aqui é PR separado (1 PR = 1 célula).

### 8.5 Portfólio público

Página materializada, regenerada a cada `encomenda.aprovada` (nunca consulta ao vivo), servida em `meshcraft.top/@usuario`. Sem dado de contato. "Encomendar direto" leva ao cardápio com o aluno fixado.

### 8.6 Relógios

Um tique por minuto reavalia: ofertas expiradas, encomendas para abrir, prazos vencidos (abandono), aprovações tácitas, SLAs de revisão, pausas vencidas. Nada agendado individualmente.

### 8.7 Frontend

Web responsiva, mobile-first (o aluno usa celular). Uma rota para o aluno (`/encomendas`), uma para o cliente, uma para o plantão. Sem painel corporativo.

---

## 9. Invariantes com testes-guarda

Cada invariante é um teste que falha se violado; a CI barra o merge, como nos invariantes de dinheiro atuais. Os agentes implementam contra os testes, não contra a descrição.

### Justiça

- **J1.** Uma encomenda nunca tem duas ofertas pendentes.
- **J2.** Um aluno nunca tem duas ofertas pendentes.
- **J3.** Toda oferta vai ao elegível disponível com menor `(entregas_aprovadas, data_entrada_fila)`.
- **J4.** Passar, expirar e pausar nunca alteram `data_entrada_fila`. Só abandono.
- **J5.** Nenhuma oferta a aluno com título abaixo do nível mínimo da encomenda.
- **J6.** Nenhum aluno recebe a mesma encomenda duas vezes, salvo em chamada aberta.
- **J7.** Aluno "trabalhando" não recebe ofertas.
- **J8.** O relógio da oferta não avança fora da janela 8h–22h.
- **J9.** Nenhuma encomenda passa de 24h em `na_fila` / `oferecida` sem virar aberta.
- **J10.** Reexecutar o motor sem mudança de estado não cria oferta nova.

### Dinheiro (somam-se aos 12 existentes)

- **D13.** Encomenda só entra na fila após confirmação de pagamento.
- **D14.** Repasse só após `aprovada`.
- **D15.** Reembolso só antes do aceite (automático) ou por mediação registrada com autor.
- **D16.** Para toda encomenda: pago = repasse + taxa + reembolso.
- **D17.** Repasse de menor de idade só para conta de responsável verificado.

### Segurança

- **S1.** Não existe texto livre trocado entre cliente e aluno fora dos campos estruturados; todos visíveis ao plantão.
- **S2.** Primeira entrega de um aluno nunca chega ao cliente sem `entrega.revisada` aprovada por humano.
- **S3.** Nenhum dado de contato do aluno em resposta de API do cliente ou no portfólio.
- **S4.** Peça no portfólio só com autorização do cliente registrada.
- **S5.** Encomenda de cliente novo não entra na fila sem aprovação do plantão.

---

## 10. Proteção de menores e conformidade

- Cadastro de aluno menor de idade exige responsável vinculado (na célula `identidade`), que recebe cópia de: primeira oferta aceita, primeira aprovação, qualquer mediação, todo repasse.
- Comunicação estruturada, sem contato direto, sem sobrenome, foto ou idade expostos ao cliente. Nome de exibição no portfólio.
- Briefing e referências de cliente novo passam pelo plantão; conteúdo impróprio bloqueia o cliente.
- Termos de uso: cessão da peça ao cliente na aprovação; direito de exibição no portfólio; compromisso de originalidade da entrega.
- **Parecer jurídico** (trabalho de menores, custódia de valores, LGPD, termos) é portão da Fase 0. Este documento desenha o produto para minimizar risco; não substitui o parecer — e quem escreve não é advogado.

---

## 11. Roadmap

Ritmo: uma fase por vez, portão fechado pelo dono. Estimativas em semanas são orientação, não compromisso.

### Fase 0 — Decisões e papel (1–2 semanas)

**Entregáveis:** este documento aprovado · constituição da célula `encomendas` · contrato OpenAPI v1 congelado · esquema de eventos v1 · invariantes J/D/S escritos como testes esqueleto (falhando) · tabela de preços v0 · parecer jurídico encomendado · decisões da seção 15 tomadas ou adiadas por escrito.

**Portão:** documento e contrato aprovados; parecer em andamento com data prevista.

### Fase 1 — Piloto de papel (2–4 semanas, sem código)

A escola abre 5–10 encomendas reais e pagas; 5–10 formados entram numa fila mantida à mão pelo professor, seguindo o livro de regras à risca: relógio de 3h, passar com motivo anotado, revisão antes de o cliente ver, escola pagando o aluno (ou o responsável) direto. Tudo registrado em planilha: cada oferta, cada motivo, cada tempo, cada erro de entrega.

Como a escola é o único cliente, não há custódia de dinheiro de terceiros — o piloto roda antes do parecer estar pronto.

**Portão:** cinco primeiras entregas aprovadas; parâmetros da seção 6.12 revisados com dados reais; lista de "armadilhas" da célula iniciada; os cinco erros de entrega mais comuns anotados (viram a auditoria automática).

**Por que antes do código:** cada regra errada descoberta aqui custa uma linha na planilha; depois, custa um PR.

### Fase 2 — Motor da fila (2–3 semanas)

Célula `encomendas` com perfis, encomendas, ofertas, motor de oferta, relógios, pausa automática, chamada aberta. Testes J1–J10. Simulador de 100 alunos e 30 encomendas como teste de propriedade.

**Portão:** invariantes de justiça verdes; simulação reproduz o piloto de papel.

### Fase 3 — Cliente e dinheiro (2–3 semanas)

Cardápio, briefing, criação de encomenda; cobrança → webhook → `na_fila`; extensão da célula de pagamentos (retenção, repasse, reembolso, D13–D17); rastreio; aprovar, corrigir, cancelar.

**Portão: "Primeiro Dólar que anda"** — caminho completo verde localmente: pagamento → oferta → aceite → entrega → revisão → aprovação → repasse, com invariantes de dinheiro verdes. É o equivalente do "esqueleto que anda" para este produto.

### Fase 4 — Aluno (1–2 semanas) — em paralelo com a Fase 3, após o contrato

Tela de três estados; cartão da oportunidade; passar com motivo; pausa; espera estimada; notificações no canal decidido.

**Portão:** teste de usabilidade com três alunos reais, no celular, sem tutorial e sem ajuda.

### Fase 5 — Entrega e revisão (2–3 semanas) — em paralelo com 3 e 4, após o contrato

Upload; checklist; worker de auditoria automática; revisão com SLA e amostragem; correção; extensão; abandono; aprovação tácita.

**Portão:** S2 verde; a auditoria pega os cinco erros mais comuns do piloto de papel.

### Fase 6 — Rampa de saída (1–2 semanas)

Portfólio materializado; autorização; pedido direto; eventos para a gamificação; cerimônia; Marcos #3 e #4.

**Portão:** pedido direto percorre a mesma esteira; Marco carimbado por evento, sem leitura de banco alheio.

### Fase 7 — Plantão (1–2 semanas)

Lista única por urgência; reclassificação por motivo; aprovação de cliente novo; mediação com reembolso registrado; repasses bloqueados.

**Portão:** o professor opera uma semana simulada só pela tela, sem SQL e sem chat de emergência.

### Fase 8 — Lançamento assistido (4–6 semanas)

Deploy na VPS; webhook real do Mercado Pago; teste cronometrado de rollback (< 5 min); turma piloto (10–20 formados) com a escola como cliente principal; dono e professor acompanham diariamente pelo plantão.

**Portão:** 30 dias sem violação de invariante em produção; 80% dos pilotos com primeira entrega aprovada.

### Fase 9 — Calibração e abertura (contínua)

Painel de métricas (seção 13); revisão dos parâmetros com dados; abertura para todos os formados; revisores Nível 3 quando existirem; segunda rodada de decisões (preços, taxa, moeda).

### Paralelismo com as sessões de agentes

Após a Fase 2 (motor verde), as Fases 3, 4 e 5 podem correr em três árvores de trabalho ao mesmo tempo — todas dentro de `encomendas`, exceto os PRs da célula de pagamentos, que são separados. Fases 6 e 7 dependem da 5. **Nunca duas sessões no motor de oferta ao mesmo tempo.**

---

## 12. Backlog em tamanho de PR

Regras já em vigor na plataforma: 1 PR = 1 célula, orçamento de 15 arquivos, contrato congelado. "Dep." = depende de.

| # | Fase | Item | Célula | Dep. |
|---|---|---|---|---|
| 0.1 | 0 | Constituição da célula `encomendas` (inclui seção 3 literal) | docs | — |
| 0.2 | 0 | Contrato OpenAPI v1 | encomendas | 0.1 |
| 0.3 | 0 | Esquema de eventos v1 | encomendas | 0.1 |
| 0.4 | 0 | Testes-guarda J/D/S como esqueleto (falhando) | encomendas / pagamentos | 0.2 |
| 0.5 | 0 | Tabela de parâmetros como configuração + rito de mudança | encomendas | 0.1 |
| 2.1 | 2 | Esqueleto da célula (processo, banco, saúde, CI) | encomendas | 0.2 |
| 2.2 | 2 | PerfilProfissional + fila (modelo, migrações) | encomendas | 2.1 |
| 2.3 | 2 | Encomenda + máquina de estados | encomendas | 2.1 |
| 2.4 | 2 | Oferta + máquina de estados | encomendas | 2.3 |
| 2.5 | 2 | Motor de oferta (seleção do próximo) + J1–J7 | encomendas | 2.4 |
| 2.6 | 2 | Relógios: tique, horas úteis + J8–J10 | encomendas | 2.5 |
| 2.7 | 2 | Pausa automática e disponibilidade | encomendas | 2.6 |
| 2.8 | 2 | Chamada aberta | encomendas | 2.6 |
| 2.9 | 2 | Simulador de 100 alunos (teste de propriedade) | encomendas | 2.8 |
| 3.1 | 3 | Cardápio + briefing + validação | encomendas | 2.3 |
| 3.2 | 3 | Cobrança vinculada a encomenda | pagamentos | 0.4 |
| 3.3 | 3 | Webhook interno → `na_fila` (D13) | encomendas | 3.2 |
| 3.4 | 3 | Retenção + repasse (D14, D16, D17) | pagamentos | 3.2 |
| 3.5 | 3 | Reembolso por decisão registrada (D15) | pagamentos | 3.4 |
| 3.6 | 3 | Rastreio, aprovar, cancelar antes do aceite | encomendas | 3.3 |
| 3.7 | 3 | Teste "Primeiro Dólar que anda" | encomendas | 3.6, 5.4 |
| 4.1 | 4 | Tela do aluno: três estados | front | 2.7 |
| 4.2 | 4 | Cartão da oportunidade + passar com motivo | front | 4.1 |
| 4.3 | 4 | Espera estimada (cálculo + tela) | encomendas / front | 2.9 |
| 4.4 | 4 | Notificações (consumidor de eventos) | notificações | 0.3 |
| 5.1 | 5 | Upload + armazenamento de entregas | encomendas | 2.3 |
| 5.2 | 5 | Worker de auditoria automática (Blender headless) | auditoria | 5.1 |
| 5.3 | 5 | Revisão humana: SLA, amostragem, escalonamento (S2) | encomendas | 5.2 |
| 5.4 | 5 | Aprovação tácita + correção 1× + entrada em mediação | encomendas | 5.3 |
| 5.5 | 5 | Extensão e abandono | encomendas | 2.6 |
| 6.1 | 6 | Portfólio materializado + autorização (S3, S4) | encomendas | 5.4 |
| 6.2 | 6 | Pedido direto | encomendas | 6.1 |
| 6.3 | 6 | Consumo de eventos pela gamificação (Marcos #3 e #4) | gamificação | 0.3 |
| 6.4 | 6 | Cerimônia do primeiro dólar | front | 6.3 |
| 7.1 | 7 | Tela de plantão (lista única por urgência) | front / encomendas | 5.4 |
| 7.2 | 7 | Reclassificação por motivo + aprovação de cliente novo (S5) | encomendas | 4.2 |
| 7.3 | 7 | Mediação com reembolso registrado | encomendas | 3.5 |
| 8.1 | 8 | Deploy, webhook real, rollback cronometrado | infra | tudo acima |
| 9.1 | 9 | Painel de métricas | métricas | 0.3 |

---

## 13. Métricas

**Norte:** percentual de formados com primeira entrega aprovada em até 30 dias após concluir o curso. Meta do piloto: 80%.

**Apoio:**
- Tempo mediano da conclusão do curso à primeira entrega aprovada
- Tempo mediano do pagamento ao aceite (o SLA que o cliente sente)
- Percentual de encomendas aceitas na primeira oferta
- Distribuição dos motivos de passe (por nível e por cartão)
- Percentual de entregas aprovadas sem correção; percentual de aprovações tácitas
- Abandonos e mediações por 100 encomendas
- Espera estimada média por nível
- Encomendas por semana ÷ alunos disponíveis — a razão que diz quanta demanda falta

---

## 14. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Faltam encomendas | Escola-cliente com compromisso semanal; alunos como clientes; parceria com estúdios e lojas UGC; espera estimada visível ao dono |
| Fantasmas na fila | Pausa automática por silêncio; janela 8h–22h; espera estimada |
| Custódia de valores de terceiros | Parecer contábil/jurídico na Fase 0; piloto de papel roda sem custódia; alternativa split do Mercado Pago |
| Menores de idade | Responsável vinculado, comunicação estruturada, plantão aprova cliente novo, parecer |
| Gargalo de revisão | Obrigatória só na primeira; amostragem; SLA com escalonamento; revisores Nível 3 pagos |
| Cliente impróprio ou abusivo | S5, bloqueio pelo plantão, nenhum contato direto |
| Encomenda mal classificada | Cardápio por tipo de item; letra miúda; reclassificação por motivo |
| Asset copiado entregue como próprio | Auditoria, revisão, termo de originalidade, suspensão |
| Relógios frágeis | Tique idempotente sem timers agendados; teste de reinício no meio de ofertas pendentes |
| Agentes "melhorando" o desenho | Seção 3 literal na constituição; invariantes barram no CI |
| Aluno se sentindo pressionado a aceitar | Passar grátis; aviso ao professor por motivo, nunca punição |
| Cliente esperando demais | Passe instantâneo; chamada aberta em 24h; prazo prometido inclui a revisão |

---

## 15. Decisões pendentes (do dono)

1. Tabela de preços v0 e moeda: exibir em US$ e cobrar em R$ pela cotação do dia, ou só R$?
2. Taxa por nível e destino. Recomendação: nível 1 pequena e integral ao revisor.
3. Mecanismo de custódia e repasse (split do Mercado Pago vs. receber e repassar via Pix) — com o parecer.
4. Parecer jurídico: trabalho de menores, responsável, termos de uso, LGPD, cessão de direitos e portfólio.
5. Idade mínima da fila e exigência de responsável. Recomendação: 13+, responsável obrigatório para menores de 18.
6. Canal de notificação: site + e-mail do responsável? push? WhatsApp?
7. Compromisso da escola como cliente no lançamento: quantas encomendas por semana, por quanto tempo.
8. Quem revisa até existir Nível 3 e quanto vale a revisão.
9. Amostragem de revisão após a primeira entrega (1 em 5?).
10. Nome no menu ("Encomendas") e nome da funcionalidade ("Fila do Primeiro Dólar"). Recomendação: ambos.
11. Marco #4: primeira aprovação de cliente que não seja a escola (recomendação) ou primeiro pedido direto?

---

## 16. Glossário

- **Encomenda** — um pedido pago de uma peça 3D, do cardápio, com nível, prazo e briefing fechados.
- **Oferta** — a chance de um aluno específico aceitar uma encomenda específica, com relógio.
- **Fila do Primeiro Dólar** — a ordem de oferta: menos entregas primeiro, empate por data de entrada.
- **Cardápio** — os três cartões que o cliente escolhe; o cartão define nível, preço e prazo.
- **Briefing blindado** — o formulário do cliente, espelho do Padrão Meshcraft de Entrega.
- **Padrão Meshcraft de Entrega** — a spec aberta do que uma peça entregue precisa conter; vira checklist na entrega.
- **STUDS** — Silhueta, Topologia, UV, Densidade, eScala; autoavaliação do aluno, parcialmente automatizada.
- **Degrau** — um dos 7 Degraus do currículo; define o nível da encomenda.
- **Banca / Título** — o exame que dá o título de Modelador Nível 1, 2 ou 3; define elegibilidade.
- **Auditoria** — verificação automática do arquivo entregue, antes de qualquer humano.
- **Revisão** — olhar humano sobre a entrega, antes do cliente.
- **Correção** — o ajuste único que o cliente pode pedir.
- **Aberta** — encomenda sem aceite há 24h, visível a todos os elegíveis; o primeiro que aceitar leva.
- **Pausa** — aluno fora das ofertas, sem perder o lugar; manual ou automática.
- **Abandono** — prazo vencido sem entrega; única coisa que muda o lugar na fila.
- **Mediação** — decisão humana registrada quando cliente e aluno não se resolvem.
- **Repasse** — o pagamento ao aluno (ou ao responsável) após a aprovação.
- **Responsável** — adulto vinculado ao aluno menor, titular da conta de recebimento.
- **Plantão** — a tela e o papel do professor como rede de segurança.
- **Pedido direto** — encomenda que chega pelo portfólio do aluno e vai direto para ele, sem fila.
- **Portfólio** — página pública `meshcraft.top/@usuario`, publicada na primeira aprovação.
- **Escola-cliente** — a Meshcraft abrindo encomendas reais e pagas.

---

## Anexo A — Textos de tela (v1)

### Aluno

- **Na fila:** "Você está na Fila do Primeiro Dólar." / "Sua vez: em cerca de 3 dias." / interruptor "Disponível". Pausado: "Sua fila está pausada. Seu lugar continua guardado. [Voltar à fila]"
- **Oportunidade:** "Uma encomenda para você" / "[Nome da peça] · US$ 10 para você · entrega em 3 dias" / "Este trabalho está dentro do seu nível." / "Você tem 2h41 para decidir. Passar não tira seu lugar." / [Aceitar] [Passar]
- **Passar:** "Por quê? Um toque." / Sem tempo agora · Valor baixo · Não curto esse tipo · Ainda não me sinto pronto(a)
- **Pausa automática:** "Você parece estar ocupado(a). Sua fila foi pausada. Seu lugar continua guardado. [Voltar à fila]"
- **Em andamento:** "Entrega até sábado, 22h." / "Precisa de mais tempo? Peça 48h a mais (uma vez)." / [Entregar]
- **Auditoria reprovou:** "Quase. Escala fora do padrão: a peça está com 0,3 studs de altura; o mínimo é 1." / [Enviar de novo]
- **Entregue:** "Enviado para revisão. Você recebe o retorno em até 1 dia."
- **Devolvida pelo revisor:** "Quase lá. [Nome] deixou 2 notas para você."
- **Aguardando cliente:** "Sua peça chegou ao cliente. Se ele não responder em 48h, aprovamos por você."
- **Primeira aprovação:** "Você ganhou seu primeiro dólar com 3D." / "Marco: Primeiro Dólar" / "Seu portfólio está no ar: meshcraft.top/@ana"
- **Abandono:** "O prazo passou e a encomenda voltou para a fila. Você continua na fila, agora no fim dela. Da próxima vez, peça a extensão antes."

### Cliente

- **Passo 1:** "O que você precisa?" — três cartões
- **Passo 2:** "US$ 10 · entrega até quinta · você recebe .fbx, texturas e versão pronta para o Roblox · 1 ajuste incluído"
- **Após pagar:** "Procurando seu modelador…"
- **Aceite:** "Ana aceitou sua encomenda. Entrega até quinta."
- **Entrega:** "Sua peça chegou. [Aprovar] [Pedir um ajuste]" / "Sem resposta em 48h, aprovamos por você."
- **Autorização (checkout):** "Permitir que esta peça apareça no portfólio de quem fizer" (marcado)
- **Cliente novo:** "Sua primeira encomenda passa por uma conferência rápida da escola. Em geral, menos de 4 horas."

### Plantão

- Cabeçalho: "Hoje: 2 atrasadas · 3 aguardando revisão · 1 para reclassificar · 1 cliente novo"

---

## Anexo B — Cenários de aceite

1. **Caminho feliz completo.** Cliente paga → oferta ao primeiro elegível → aceite → entrega → auditoria aprova → revisão aprova → cliente aprova → repasse → `concluida`; Marco #3 carimbado; portfólio publicado.
2. **Passar.** Primeiro passa com motivo; o segundo recebe em menos de 1 segundo; `data_entrada_fila` do primeiro inalterada; o primeiro não recebe essa encomenda de novo.
3. **Silêncio ×3.** Três expirações seguidas → pausado; "Voltar à fila" → disponível, mesma posição; um Passar no meio zera a contagem.
4. **Chamada aberta.** Nenhum aceite em 24h → `aberta`; dois alunos tentam aceitar ao mesmo tempo → só um consegue.
5. **Duas encomendas simultâneas.** Vão a alunos diferentes; ninguém com duas ofertas pendentes (J2).
6. **Nível mínimo.** Aluno com título Nível 1 nunca recebe intermediária, mesmo sendo o único disponível (vira aberta só para elegíveis).
7. **Cancelamento antes do aceite.** Reembolso integral; oferta pendente cancelada; aluno mantém posição.
8. **Cancelamento após o aceite.** Vai para mediação; aluno mantém posição e contagem; reembolso só por decisão registrada.
9. **Abandono.** Prazo vencido → volta à fila sem esse aluno; aluno ao fim; cliente avisado com nova previsão.
10. **Primeira entrega.** Passa obrigatoriamente por revisão; a segunda respeita a amostragem; nenhuma chega ao cliente sem `entrega.revisada` quando exigida (S2).
11. **Aprovação tácita.** 48h sem resposta → `aprovada` → repasse no próximo dia útil.
12. **Correção.** Um pedido → `em_correcao` → nova entrega; segundo pedido → mediação.
13. **Pedido direto.** Não entra na fila; vai ao aluno; mesma esteira de revisão e dinheiro; não bloqueia a vaga da fila.
14. **Repasse de menor.** Sem responsável verificado → repasse bloqueado, plantão avisado, valor preservado (D17).
15. **Reinício.** Processo cai com ofertas pendentes → ao voltar, relógios corretos, nenhuma oferta duplicada (J10).
16. **Reclassificação.** Dois "não me sinto pronto" na mesma encomenda → `para_reclassificar`; some das ofertas até a decisão do plantão.
17. **Conservação.** Para toda encomenda encerrada: pago = repasse + taxa + reembolso (D16).
