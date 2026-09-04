# ANEXO — o contrato v1 da célula `encomendas`, em papel

> **O que é:** o contrato HTTP v1 que o plano mestre manda congelar na Fase 0,
> escrito **em papel** porque nesta casa o congelado em `contracts/` só pode
> nascer do export da porta de máquina (`armadilhas/228` e `243`). Este anexo
> é a fonte contra a qual o degrau 2.7 (a porta) se escreve e o
> degrau 2.8 (o congelamento) se confere. Quando
> `contracts/encomendas.openapi.yaml` existir, **ele vence** e este arquivo
> vira história.
>
> **Duas partes, de propósito.** A Parte A é o CONTRATO: o que outra célula
> chama por Bearer. A Parte B são as TELAS: páginas servidas pela própria
> célula, com formulário normal e o cookie repassado à `identidade`. Telas não
> são contrato nesta casa (lei §3.2), e cada rota a mais no contrato é uma
> rota a mais a defender pela borda (`armadilhas/103`, `186`).
>
> Lei: `DECISAO-fila-do-primeiro-dolar.md`. Produto:
> `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` (§8.3 é a lista original de rotas,
> aqui repartida entre A e B).

## Parte A — o contrato (porta de máquina, Bearer por par)

Convenções herdadas de todo contrato da casa: `openapi: 3.1.0`; Bearer
estático **por par** (`TOKENS_ACEITOS_<PAR>`, env ausente ⇒ 401 para todos);
ids de pessoa são o **id da plataforma** (nunca e-mail); dinheiro é inteiro em
**centavos**; "não conheço esta pessoa" é **200 com `existe: false`**, nunca
404 (a regra da porta de situação da `alunos`); nenhum dado de contato do
aluno sai por porta nenhuma (S3).

```yaml
openapi: 3.1.0
info:
  title: Encomendas — API interna
  version: 1.0.0
  description: |
    Superficie de MAQUINA da Fila do Primeiro Dolar. Quem consome:
    o Admin (parametros), a home e o Estudio (fila de uma pessoa, pecas
    aprovadas), a celula de pagamentos (pagamento confirmado, Fase 3) e o
    worker de auditoria (resultado, Fase 5).

    O Bearer prova QUEM CHAMA, nunca quem e a pessoa: nao chega cookie aqui.
    Por isso nenhuma porta desta superficie ACEITA, PASSA, ENTREGA ou APROVA
    nada em nome de um aluno ou de um cliente — esses gestos sao das telas
    (Parte B), onde a pessoa esta atras do login.

    Nao sai dado de contato do aluno por porta nenhuma (INV-ENC-S3), e so
    saem pecas com autorizacao do cliente registrada (INV-ENC-S4).

    Lei do assunto: docs/decisoes/DECISAO-fila-do-primeiro-dolar.md.

servers:
  - url: /api/encomendas

security:
  - bearer: []

paths:

  /parametros:
    get:
      operationId: getParameters
      summary: Os parametros vigentes da fila, com o historico de cada um
      description: |
        A tabela da secao 6.12 do plano, como DADO (lei §3.8). Devolve, por
        chave, o valor vigente e as linhas anteriores (valor, desde, motivo,
        quem). E a leitura da tela /admin/encomendas/parametros/.
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/Parametro' }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }

  /parametros/{chave}:
    put:
      operationId: setParameter
      summary: Muda um parametro acrescentando uma linha nova com motivo
      description: |
        NUNCA reescreve a linha vigente: acrescenta uma nova, que passa a
        valer em `desde`. O motor le o valor vigente em `agora`, entao um
        parametro mudado as 15h nao reescreve uma oferta feita as 14h.
        `motivo` e obrigatorio e curto demais e recusado: e o rastro que a
        proxima pessoa le. `quem` e o id de plataforma de quem mudou (o
        Admin ja o conhece). Chave desconhecida e 404: o vocabulario e
        fechado, e nasce no codigo da celula, nunca pela porta.
      parameters:
        - name: chave
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/MudancaDeParametro' }
      responses:
        '200':
          description: A linha nova, ja vigente
          content:
            application/json:
              schema: { $ref: '#/components/schemas/LinhaDeParametro' }
        '400': { description: Valor fora do tipo ou da faixa da chave, ou motivo curto demais }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }
        '404': { description: Chave desconhecida }

  /perfis/{id}/fila:
    get:
      operationId: getQueueStanding
      summary: Em que pe esta a fila de uma pessoa — para a home e o Estudio
      description: |
        A pergunta que a home logada e o Estudio fazem: "esta pessoa esta na
        Fila do Primeiro Dolar? quando chega a vez dela?". Responde 200 com
        `existe: false` para quem nao tem perfil profissional — nunca 404.

        A ESPERA substitui a posicao (plano §5.4): o numero que o aluno quer
        nao e "7o", e "em cerca de 3 dias". `espera_estimada_dias` e
        calculada por posicao x ritmo recente de encomendas do nivel, e vem
        nula quando nao ha ritmo para medir (nunca inventada).

        Nao sai nada que identifique a pessoa alem do id que quem chama ja
        tinha.
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string }
          description: Id da PLATAFORMA (identidade), nunca e-mail
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/FilaDeUmaPessoa' }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }

  /perfis/{id}/pecas-aprovadas:
    get:
      operationId: getApprovedPieces
      summary: As pecas aprovadas E autorizadas de uma pessoa, para o Estudio
      description: |
        A unica porta por onde uma peca sai desta celula. So pecas de
        encomendas `aprovada` ou `concluida` E com `autorizacao_portfolio`
        registrada pelo cliente (INV-ENC-S4). Nada de briefing, nada de
        cliente, nada de contato (INV-ENC-S3). 200 com lista vazia para quem
        nao tem nada — nunca 404.

        Os contadores "entregas" e "no prazo" viajam junto porque o Estudio
        os mostra ao lado das pecas (plano §5.6) e calcular do lado de la
        seria copiar regra.
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/PecasAprovadas' }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }

  /interno/pagamentos/confirmado:
    post:
      operationId: confirmPayment
      summary: A celula de pagamentos avisa que a cobranca de uma encomenda foi confirmada
      description: |
        E o gatilho de `aguardando_pagamento -> na_fila` (INV-ENC-D13). Chega
        da celula `pagamentos`, por Bearer do par pagamentos->encomendas,
        DEPOIS de ela ter conferido o status na API do provedor (nunca do
        corpo nao assinado do webhook — retrospectiva, padrao 4).

        Idempotente por `chave_idempotencia`: o mesmo aviso entregue N vezes
        produz UMA transicao e UM evento `encomenda.paga.v1`. Encomenda que
        nao esta em `aguardando_pagamento` responde 409 com o estado atual,
        sem efeito.

        ATE A FASE 3 responde 501. A confirmacao de `origem = escola` NAO
        passa por aqui: e gesto do plantao, na tela, com autor (lei §3.4).

        `/interno` NAO resolve pela borda publica (armadilhas/186).
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/PagamentoConfirmado' }
      responses:
        '200':
          description: Transicao feita (ou ja feita antes, pela mesma chave)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EstadoDaEncomenda' }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }
        '404': { description: Encomenda desconhecida }
        '409': { description: A encomenda nao esta aguardando pagamento; o corpo traz o estado atual }
        '501': { description: Ate a Fase 3 esta porta existe e nao opera }

  /interno/auditoria/resultado:
    post:
      operationId: reportAudit
      summary: O worker de auditoria devolve o veredito sobre uma entrega
      description: |
        A auditoria automatica (Blender headless) roda fora desta celula e
        responde por aqui: aprovada, ou reprovada com os itens medidos
        (triangulos, escala, UV, textura, nomenclatura). Reprovada leva a
        encomenda de `entregue` de volta a `em_producao` com a mensagem
        clara que o aluno ve ("Escala fora do padrao: 0,3 studs; o minimo e
        1"). Emite `entrega.auditada.v1`.

        Idempotente por `entrega_id` + `versao`: o mesmo veredito duas vezes
        nao muda nada. ATE A FASE 5 responde 501.
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ResultadoDaAuditoria' }
      responses:
        '200':
          description: Veredito registrado (ou ja registrado antes)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EstadoDaEncomenda' }
        '401': { description: Sem Bearer, ou Bearer de par nao aceito }
        '404': { description: Entrega desconhecida }
        '501': { description: Ate a Fase 5 esta porta existe e nao opera }

components:
  securitySchemes:
    bearer:
      type: http
      scheme: bearer

  schemas:

    LinhaDeParametro:
      type: object
      required: [valor, desde, motivo, quem]
      properties:
        valor: { type: string, description: Sempre texto; a chave diz o tipo (inteiro, hora, enum) e a celula valida }
        desde: { type: string, format: date-time }
        motivo: { type: string }
        quem: { type: string, description: Id de plataforma de quem mudou }

    Parametro:
      type: object
      required: [chave, tipo, vigente, historico]
      properties:
        chave: { type: string, description: Uma das chaves da lei §6 (vocabulario fechado) }
        tipo: { type: string, enum: [inteiro, horas, dias, hora_do_dia, enum] }
        descricao: { type: string }
        vigente: { $ref: '#/components/schemas/LinhaDeParametro' }
        historico:
          type: array
          description: Da mais recente para a mais antiga, a vigente incluida
          items: { $ref: '#/components/schemas/LinhaDeParametro' }

    MudancaDeParametro:
      type: object
      required: [valor, motivo, quem]
      properties:
        valor: { type: string }
        motivo: { type: string, minLength: 15 }
        quem: { type: string }

    FilaDeUmaPessoa:
      type: object
      required: [existe]
      properties:
        existe: { type: boolean, description: false = sem perfil profissional; os outros campos vem ausentes }
        titulo_banca:
          type: [string, 'null']
          enum: [nivel_1, nivel_2, nivel_3, null]
        disponibilidade:
          type: string
          enum: [disponivel, pausado, trabalhando]
        na_fila_desde: { type: [string, 'null'], format: date-time }
        entregas_aprovadas: { type: integer, minimum: 0 }
        espera_estimada_dias:
          type: [integer, 'null']
          description: Nula quando nao ha ritmo recente para medir. Nunca inventada.
        encomenda_ativa_id:
          type: [string, 'null']
          description: A encomenda da fila em andamento, se houver (uma por vez)

    PecaAprovada:
      type: object
      required: [encomenda_id, nome_da_peca, cartao, origem, aprovada_em, no_prazo]
      properties:
        encomenda_id: { type: string }
        nome_da_peca: { type: string, description: O nome que o cliente deu no briefing; nenhuma outra linha do briefing sai }
        cartao: { type: string, enum: [item_simples, vestivel_ou_veiculo, personagem] }
        origem: { type: string, enum: [fila, direto, escola] }
        aprovada_em: { type: string, format: date-time }
        no_prazo: { type: boolean }
        previa_url:
          type: [string, 'null']
          description: Endereco da previa que o aluno enviou na entrega; nulo ate a Fase 5 decidir onde moram os arquivos

    PecasAprovadas:
      type: object
      required: [entregas, no_prazo, pecas]
      properties:
        entregas: { type: integer, minimum: 0, description: Contador de entregas aprovadas (fila + direto + escola) }
        no_prazo: { type: integer, minimum: 0 }
        pecas:
          type: array
          items: { $ref: '#/components/schemas/PecaAprovada' }

    PagamentoConfirmado:
      type: object
      required: [encomenda_id, pagamento_id, valor_pago_cents, confirmado_em, chave_idempotencia]
      properties:
        encomenda_id: { type: string }
        pagamento_id: { type: string, description: O id do pagamento na celula de pagamentos (opaco aqui) }
        valor_pago_cents: { type: integer, minimum: 1 }
        confirmado_em: { type: string, format: date-time }
        chave_idempotencia: { type: string }

    ResultadoDaAuditoria:
      type: object
      required: [entrega_id, versao, resultado, itens]
      properties:
        entrega_id: { type: string }
        versao: { type: integer, enum: [1, 2] }
        resultado: { type: string, enum: [aprovada, reprovada] }
        itens:
          type: array
          description: Vazio quando aprovada; um por criterio medido quando reprovada
          items:
            type: object
            required: [codigo, mensagem]
            properties:
              codigo: { type: string, enum: [triangulos, dimensoes, escala, uv, textura, nomenclatura] }
              mensagem: { type: string, description: A frase que o aluno le, ja em portugues }
              medido: { type: [string, 'null'] }
              limite: { type: [string, 'null'] }

    EstadoDaEncomenda:
      type: object
      required: [encomenda_id, status]
      properties:
        encomenda_id: { type: string }
        status:
          type: string
          enum: [aguardando_pagamento, na_fila, oferecida, aberta, para_reclassificar, em_producao, entregue, em_revisao, aguardando_cliente, em_correcao, aprovada, concluida, abandonada, em_mediacao, cancelada]
```

**Quem consome o quê** (entra em `celulas.yml` no PR do cliente que lê
`ENCOMENDAS_API_URL`, nunca antes — `armadilhas/224`):

| Consumidor | Operações | Quando |
|---|---|---|
| `admin` | `getParameters`, `setParameter` | Fase 2 (a tela `/admin/encomendas/parametros/` pode nascer junto com o degrau 2.10) |
| `funil` (home logada) | `getQueueStanding` | Fase 4 |
| `pages` (Estúdio) | `getQueueStanding`, `getApprovedPieces` | Fase 6 |
| `pagamentos` | `confirmPayment` | Fase 3 |
| worker de auditoria | `reportAudit` | Fase 5 |

## Parte B — as telas (não são contrato)

Servidas pela célula sob `/encomendas`, com o cookie repassado à `identidade`
(nunca assinado aqui, INV-P12) e a autorização decidida **aqui**, fail-closed.
Cada gesto é um `<form method="post">` normal; script, se houver, só
intercepta e cai para o formulário. A lista abaixo é a §8.3 do plano
traduzida em páginas; os textos de cada tela estão no Anexo A do plano.

### Do aluno — `/encomendas` (uma tela, três estados)

| Gesto do plano | Tela / ação | Estado |
|---|---|---|
| `GET /minha-fila` | `GET /encomendas` — na fila · oportunidade · em andamento, decidido pelo servidor | Fase 4 |
| `PUT /minha-fila/disponibilidade` | `POST /encomendas/disponibilidade` (Disponível / Indisponível; "Voltar à fila" é o mesmo gesto) | Fase 4 |
| `GET /ofertas/atual` | é o estado "oportunidade" de `GET /encomendas`, com o relógio | Fase 4 |
| `POST /ofertas/{id}/aceitar` | `POST /encomendas/ofertas/<id>/aceitar` | Fase 4 |
| `POST /ofertas/{id}/passar` | `POST /encomendas/ofertas/<id>/passar` com `motivo` ∈ {sem_tempo, valor_baixo, nao_curto, nao_me_sinto_pronto} | Fase 4 |
| `POST /encomendas/{id}/perguntar` | `POST /encomendas/<id>/perguntar` (estruturada, até 3 por encomenda, visível ao plantão — S1) | Fase 5 |
| `POST /encomendas/{id}/entregar` | `POST /encomendas/<id>/entregar` (checklist + STUDS + arquivos) | Fase 5 |
| `POST /encomendas/{id}/pedir-extensao` | `POST /encomendas/<id>/extensao` (uma, 48h, até 24h antes) | Fase 5 |

### Do cliente — `/encomendas/pedir` e `/encomendas/acompanhar/<id>`

| Gesto do plano | Tela / ação | Estado |
|---|---|---|
| `GET /cardapio` | `GET /encomendas/pedir` — três cartões com a letra miúda; `?para=<apelido>` fixa o aluno (pedido direto) | Fase 3 |
| `POST /encomendas` | `POST /encomendas/pedir` — briefing blindado, **sem campo de contato**; leva a confirmar e pagar | Fase 3 |
| `GET /encomendas/{id}` | `GET /encomendas/acompanhar/<id>` — a linha de rastreio | Fase 3 |
| `POST /encomendas/{id}/aprovar` | `POST /encomendas/acompanhar/<id>/aprovar` | Fase 3 |
| `POST /encomendas/{id}/pedir-correcao` | `POST /encomendas/acompanhar/<id>/ajuste` (uma vez, estruturado; a segunda vai à mediação) | Fase 5 |
| `POST /encomendas/{id}/cancelar` | `POST /encomendas/acompanhar/<id>/cancelar` (antes do aceite: automático; depois: mediação) | Fase 3 |
| `POST /pedidos-diretos` | é `/encomendas/pedir?para=<apelido>`; a encomenda nasce com `origem = direto` | Fase 6 |

### Do plantão — `/encomendas/plantao` (professor ou administrador)

| Gesto do plano | Tela / ação | Estado |
|---|---|---|
| `GET /plantao` | `GET /encomendas/plantao` — uma lista, por urgência (plano §5.7), com o cabeçalho "Hoje: 2 atrasadas · 3 aguardando revisão…" | Fase 7 (uma versão mínima nasce na Fase 2 para dar título e abrir encomenda da escola) |
| dar o título (lei §3.6) | `POST /encomendas/plantao/titulo` — pessoa, nível, data, autor | **Fase 2** |
| abrir encomenda da escola (lei §3.4) | `POST /encomendas/plantao/encomenda-da-escola` — cartão, briefing, "pago pela escola" com autor | **Fase 2** |
| `POST /entregas/{id}/revisar` | `POST /encomendas/plantao/entregas/<id>/revisar` (aprova / devolve com notas) | Fase 5 |
| `POST /encomendas/{id}/reclassificar` | `POST /encomendas/plantao/<id>/reclassificar` | Fase 7 |
| `POST /encomendas/{id}/mediar` | `POST /encomendas/plantao/<id>/mediar` (decisão + reembolso registrado com autor — D15) | Fase 7 |
| `POST /clientes/{id}/aprovar` | `POST /encomendas/plantao/clientes/<id>/aprovar` (S5) | Fase 7 |

### Público

| Gesto do plano | Onde mora | Estado |
|---|---|---|
| `GET /portfolios/{usuario}` | **não é desta célula**: o Estúdio (`/estudio/<apelido>`, célula `pages`) pergunta `getApprovedPieces` e mostra o selo (lei §3.5) | Fase 6 |

## Os eventos

Os 20 esquemas moram em `contracts/eventos/` (TAR-108), um arquivo por fato,
no envelope canônico da casa (`event`, `version`, `event_id`, `occurred_at`,
`ator_id` quando há pessoa agindo, `data`), `additionalProperties: false`,
só ids opacos. Consumidores previstos: `gamificacao` (Marcos #3 e #4, por
`encomenda.aprovada.v1` e `pedido-direto.criado.v1`), `pagamentos` (repasse
em `encomenda.aprovada.v1`, reembolso em `encomenda.cancelada.v1` e
`encomenda.em-mediacao.v1`), métricas (todos). O sininho não consome estes:
recebe `notificacao.devida.v1` emitido por esta célula (lei §3.7).
