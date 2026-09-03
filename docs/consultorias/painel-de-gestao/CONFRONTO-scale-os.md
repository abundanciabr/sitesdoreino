# CONFRONTO | os quatro documentos do "Meshcraft Scale OS" contra as decisões da casa

**Escrito em 03/09/2026**, antes de derivar qualquer plano, como manda a
`armadilhas/299`: primeiro as premissas de fato, uma a uma, contra
`docs/decisoes/DECISAO-*.md`, contra a memória da sessão e contra o código em
`origin/main`. Só depois o plano.

Os quatro documentos (guardados inteiros nesta pasta):

| # | Documento | O que é |
|---|---|---|
| 1 | `SCALE-OS-1-a-tese.md` | A tese: OKR + 4DX + Teoria das Restrições + experimentos + economia unitária, em sete camadas. 40 seções. |
| 2 | `SCALE-OS-2-manual-operacional.md` | O manual: as quatro fases (achar, provar, escalar, compor), a cadência (semana, mês, trimestre, ano), os 12 indicadores, a constituição de 15 regras, a implantação em 12 semanas. 176 itens. |
| 3 | `SCALE-OS-3-arquitetura-do-painel.md` | O painel: o menu de 11 áreas e 28 telas, a home em 11 blocos, os pipelines de decisão para tarefa. 172 itens. |
| 4 | `SCALE-OS-4-especificacao-tecnica.md` | A técnica: células, rotas, tabelas, APIs, permissões, jobs, testes, a ordem de 12 lotes. 276 itens. |

Eles são continuação direta das arquiteturas v1, v2 e v3 (mesma IA, mesma
conversa), e por isso carregam as mesmas premissas que a casa já decidiu ao
contrário. O que muda em relação a v1 a v3: o assunto deixa de ser "que
negócio construir" e passa a ser "como gerir e como o painel se constrói".
Isso aproxima muito os documentos do que a casa já tem, e é por isso que a
tabela de "já existe com outro nome" (§3) ficou longa.

---

## §1 As premissas de fato, uma a uma

Legenda do veredito: **MANTIDA** (a decisão da casa fica; a premissa do
documento sai) · **SEM SUJEITO** (o documento assume algo que não existe aqui,
e a peça é traduzida para o que existe) · **JÁ EXISTE** (a casa tem, com outro
nome; mapear, não reconstruir) · **NOVA** (não há decisão nem construção; entra
no plano) · **PARA ELE** (só o mantenedor decide; vai para a caixa de perguntas).

| # | Premissa do documento | Onde aparece | O que a casa decidiu | Veredito |
|---|---|---|---|---|
| 1 | Existem alunos menores de 18 (escopo `customer.minor_sensitive.view`, "proteção de dados de menores", objeção "PARENT 14%"). | Doc 4 §144 e §193; Doc 3 §68 | Escola 18+, sem menores (30/08/2026, `DECISAO-gamificacao.md` §9; reconfirmado em 03/09 diante da v1). | **MANTIDA.** Sai o escopo de menor, sai a objeção "pais". É a terceira vez que a IA de fora traz isto; a reconfirmação de 03/09 já está registrada, e por isso a pergunta não se repete. |
| 2 | Equipe: CEO, Growth owner, Product/Education owner, Customer Success owner, Finance owner, Tech owner, vendedores com "close rate", setter e closer. | Doc 2 Parte XXVI; Doc 3 §66, §133, §134; Doc 1 §8 | Não existe equipe comercial (03/09). Quem atende é o mantenedor, a professora e os robôs. | **SEM SUJEITO.** Toda tela "por função" colapsa em duas lentes: a do dono e a dos robôs. A professora é a única segunda pessoa possível (ver §5, pergunta 3). |
| 3 | Onze papéis de acesso (RBAC: super_admin, ceo, growth, finance, education, customer_success, sales, tech, analyst, robot, viewer). | Doc 4 §141 a §143 | `ADMIN_EMAILS` é a única fonte de "pode entrar", derivada na hora, nunca gravada (`DECISAO-celula-admin.md` §2). Administrador é ortogonal e mora só na `admin` (`DECISAO-categorias-de-usuario.md` §2.1). Robô não tem crachá de sessão: robô fala por `gh`, arquivo e pipeline (Lei 5; `PARECER-uma-porta-de-leitura`). | **MANTIDA.** Não nasce tabela de papéis. Se um dia houver segundo leitor, é decisão dele (pergunta 3). |
| 4 | CRM contratado como fonte de "relacionamento" e de "CRM buyers" na conciliação. | Doc 2 §102; Doc 3 §90; Doc 4 §115 | A própria plataforma é o CRM (03/09): `identidade` + `leads` + `alunos` + `mensageria`. | **MANTIDA.** A conciliação diária compara `pagamentos` × `alunos` × `identidade` × o livro de fatos; não há terceira ponta. |
| 5 | Checkout ativo, PIX, cartão, recuperação de carrinho, anúncios pagos, CAC, payback, margem de contribuição, LTV. É a espinha de 9 dos 12 indicadores do "placar do CEO", da restrição-exemplo (checkout → pagamento) e de metade das telas. | Doc 1 §14 a §16, §32; Doc 2 Partes X a XIII, XVII; Doc 3 §9, §10, §36 a §53, §65 a §68; Doc 4 Partes XI, XV, XIX | Venda, checkout e pagamento congelados desde 22/08/2026 até ele dizer que o site vai vender. Nada de tile de venda (`DECISAO-celula-admin.md` §4.1). Gasto de anúncio não existe como dado: entra digitado, com data e autoridade `mantenedor` (plano atual §5.2). | **MANTIDA.** Tudo isso entra DESENHADO (cartão com `fonte: null` e `sem_fonte_porque`), nunca aceso, e acende sozinho no dia em que a ordem vier. Ver §4. |
| 6 | Quatro células novas: `painel`, `revenue`, `analytics`, `automation` (mais `community`, `talent`, `b2b` no futuro). | Doc 4 §7 a §12 | Os fatos do negócio moram numa célula nova só (nome de trabalho `metricas`, 03/09). O motor de mensagens automáticas mora DENTRO da `mensageria` (30/08, contra a recomendação de célula nova). A `admin` é a porta de tudo que é gestão (`DECISAO-a-gestao-da-caixa-mora-no-admin.md`). | **MANTIDA.** O próprio Doc 4 §10 admite `revenue` e `analytics` numa célula só: é a `metricas`. `automation` é a `mensageria` (`apps/jornadas/`). `painel` como célula é a `admin`. Não nascem quatro; nasce uma. |
| 7 | As telas moram sob o prefixo `/painel/…` (28 rotas). | Doc 4 Parte III | Tudo que é gestão mora em `/admin/`; e `/admin/painel/` é o livro de ocorrências. A rota genérica `painel/<qualquer coisa>` engole qualquer irmã, e por isso o placar nasceu em `/admin/placar/` e o perpétuo em `/admin/perpetuo/` (`DECISAO-a-area-do-lancamento-perpetuo.md` §1). | **MANTIDA.** As telas novas nascem como `/admin/<coisa>/`, fora do prefixo `painel/`, e cada uma entra em `painel/mapa-do-site.json` (o cartógrafo reprova endereço fora do mapa). |
| 8 | Motor de tarefas com banco próprio dentro da célula `painel`: tabelas `task`, `task_lock`, `task_dependency`, `robot`, `robot_run`, `execution_exception`; Kanban de 8 colunas; lotes; `conflict_group`; "READY só com dependências resolvidas". | Doc 4 Partes XXII a XXIV; Doc 3 §74 a §83; Doc 2 Parte XXVIII | Já existe, e foi decidido de OUTRO jeito com três pareceres externos em 29/08/2026: "nenhum banco novo, nenhum servidor novo, nenhuma lista digitada à mão" (`VEREDITO.md` da central de orquestração; `PARECER-uma-porta-de-leitura`). `fila/` (arquivo por tarefa, arquivo por evento, estado calculado), `ci/fila.py` (o balcão), `ci/reservar.py` (a trava atômica no servidor, expira em 3h), `celulas.yml` + `toca` (o grupo de conflito, conferido contra o diff em sombra), `RUNBOOK-LOTES.md` (lotes), a aba `/admin/caixa/robos/` (o quadro, o ao-vivo, as esperas), registro tipo `pendencia` com os quatro campos (a exceção que chega decidível). | **JÁ EXISTE.** Nada a construir. O que a fila de próxima ação do painel produzir vira `python ci/fila.py criar`, nunca outro quadro. |
| 9 | Memória de decisão (`decision` com `review_date`, job diário que abre tarefa "revisar decisão"; `validated_learning`; `decision_log`). | Doc 4 Partes XXVII e XXVIII; Doc 3 §91 a §95; Doc 2 Parte XXII | O livro (`painel/registros/`): tipo `decisao`, `responde_a`, `vence_em_dias` (o vencimento que a caixa "precisa de você" cobra sozinha), `evidencia` + `verificado_em`. As lições validadas são `armadilhas/` (uma por arquivo, com sino que avisa quando a assinatura reaparece). | **JÁ EXISTE.** "Resultado real depois de 90 dias" é um registro novo com `responde_a`, nunca edição. Uma vista "decisões e o que deu" no painel é regra de cálculo em `painel/logica.js`, por PR. |
| 10 | Registro de métricas (`metric_definition`: chave, definição de negócio, fórmula, unidade, direção de otimização, dono, fonte, versão, frescor). | Doc 4 §55; Doc 2 §101; Doc 3 §115, §116 | `painel/cartoes/` (03/09): um arquivo por métrica, fail-closed, com nome, tipo, andar, pergunta, definição, fórmula, fonte (ou `sem_fonte_porque`), autoridade, dono, frequência, par, alvo, limiares, versão, desde. Validado por `placar.py::validar` com teste do caso que deve reprovar. | **JÁ EXISTE**, e o Doc 4 traz quatro campos que faltam e valem entrar: `direcao` (subir é bom, descer é bom, faixa), `unidade`, `frescor_maximo` (a partir de quando o número é "velho") e `dimensoes` (por onde se pode abrir o número: site, turma, mês de entrada). Entram por PR no validador, com teste. |
| 11 | Trilha de auditoria (`audit_log` com antes/depois, ator, motivo). | Doc 4 Parte XXXVI | Toda escrita da `admin` gera linha de auditoria append-only com o valor anterior, protegida por trigger no banco (`DECISAO-celula-admin.md` §4.3). | **JÁ EXISTE.** |
| 12 | Caixa de aprovações ("what needs my decision?") com ações que exigem humano. | Doc 3 §137, §138; Doc 4 Parte XXXIV | A caixa "precisa de você" é CALCULADA (pedido sem resposta), com os quatro campos da decisão (`se_eu_nao_decidir`, `recomendacao`, `reversivel`, `impacto`). | **JÁ EXISTE.** A lista de "ações que exigem aprovação" do Doc 4 §139 é quase toda de venda; o que resta (apagar dado, rollback) já é PR ou pipeline com mandato. |
| 13 | Envelope de evento próprio: `event_name`, `schema_version`, `producer`, `received_at`, `customer_id`, `context` (user agent, UTM, IP). | Doc 4 §3, §178, §179 | Envelope canônico da casa: `{event, version, event_id, occurred_at, data}` com `site_id` dentro de `data`, `additionalProperties: false`, e NENHUM dado pessoal viaja em evento (`contracts/README.md`; `identidade.pessoa-cadastrada.v1`). | **MANTIDA.** `received_at` é do consumidor (a `metricas` o grava ao receber). `context` com IP e user agent é dado pessoal e não entra em evento; UTM e origem são a atribuição, que é medição própria (ver §4, item 6). |
| 14 | Modelos de leitura (CQRS leve): a home lê de `snapshot`s com cache de 30 a 120 s; "não fazer 20 pedidos no carregamento". | Doc 4 §4 a §6, §36, §37 | Contadores em tempo real por HTTP, exatos, sem atraso (25/08, `DECISAO-celula-admin.md` §3.3, a opção barata foi vista e recusada). Abrir o painel do dono custa UM pedido (`painel/LEIA-ME.md`). | **MANTIDA, com a tradução que o plano atual já fez:** o número "agora" (quantas pessoas são alunas) vem ao vivo da célula dona, sem cache; o número "desde quando" (coorte, foto de D30, história) vem da `metricas`, que é foto por natureza. A home faz um pedido por bloco, com teto de tempo por bloco (2,0 s, o padrão do `funil`), e bloco que não chegou diz "não chegou", nunca zero. |
| 15 | Interruptores de função com porcentagem de público (`feature_flag` com `rollout_percentage`). | Doc 4 Parte LIV; Doc 2 §129 | Interruptor da casa é `ativa` + `vigente_desde` (gamificação, "nunca retroativo" como mecanismo) e versão publicada como pedra (mensageria). Porcentagem de público não faz sentido para um painel de um leitor. | **SEM SUJEITO.** Tela nova entra por PR, atrás da porta; não há público para fatiar. |
| 16 | Tempo real por SSE ou WebSocket para incidentes e robôs. | Doc 4 Parte XXXVII | O próprio Doc 4 §148 diz que polling controlado basta. A aba dos robôs já lê ao vivo do navegador (API pública do GitHub, com o teto de 60 chamadas por hora documentado em `divida.py`). | **JÁ EXISTE** no que importa. Sem infraestrutura nova de tempo real. |
| 17 | Frontend: templates Django + Alpine + HTMX + UMA biblioteca de gráficos; não migrar para React. | Doc 4 Parte XLV | A casa é Django + templates + Alpine (receita R6), CSP `script-src 'self'` na `admin`. HTMX não faz parte da pilha. | **MANTIDA, com uma escolha técnica minha:** sem HTMX (fetch + Alpine já fazem o incremental); uma biblioteca de gráficos só, servida como estático da própria célula (a CSP exige), escolhida no PR que desenhar o primeiro gráfico. |
| 18 | Duas estrelas-guia acima de tudo: "taxa de resultado profissional" (portfólio aprovado, primeiro trabalho pago) e "margem de contribuição mensal". | Doc 1 §19; Doc 2 Parte IV; Doc 3 §7 | A Meta Crucialmente Importante nº 1 é o número de alunos na plataforma (03/09). Portfólio tem plano guardado sem construção autorizada; célula de cursos não existe; margem depende de venda. | **PARA ELE** (pergunta 1 da caixa): as duas estrelas entram como o andar de cima da Meta 1, desenhadas e sem fonte hoje, ou ficam de fora até terem sujeito. |
| 19 | Uma Meta Crucialmente Importante por ciclo de 12 semanas, "de X para Y até Z", com 1 a 3 medidas de direção semanais e compromissos com dono. | Doc 1 §1, §5; Doc 2 Parte VI; Doc 3 §8, §22 a §25 | É exatamente o formato do placar (`/admin/placar/`, cartão `alunos-na-plataforma`), cujo alvo e data são pendência dele (registro `20260903-028`, que recomendou 60 a 90 dias). | **JÁ EXISTE** o placar; **PARA ELE** o Y e a data (pergunta 2). As medidas de direção candidatas já estão no plano atual §4.1 (pedidos de entrada por semana; liberações em 48 h; primeira ação real em 7 dias). |
| 20 | Nota composta de 0 a 100 ("Scale Health 84/100") no cabeçalho de toda tela, com pesos por dimensão. | Doc 2 Parte XXIX; Doc 3 §6, §137, §155; Doc 4 §35 | Regra do plano atual e do validador dos cartões: número composto nunca no andar zero, e só aparece com os componentes ao lado (o índice esconde qual parte se mexeu). O Doc 3 §44 concorda consigo mesmo: "não usar cor sem número e contexto". | **PARA ELE** (pergunta 3): é regra de desenho da sessão anterior, não decisão dele, e os documentos dele põem a nota no lugar mais visível. |
| 21 | Reunião semanal de 60 minutos com pauta em 8 passos, "modo reunião" dentro do painel, e no fim o sistema grava decisões, tarefas, donos e datas. | Doc 1 §7; Doc 2 Parte XVI; Doc 3 §96 a §105 | A cadência do plano atual §4.2: toda segunda, pauta fixa, cada compromisso é registro tipo `nota` com `vence_em_dias: 7`, veredito calculado. Quem participa: o mantenedor, a professora, o robô da sessão. | **JÁ DESENHADO**, e o "modo reunião" do Doc 3 é a tela que faltava: a pauta guiada que termina escrevendo os registros no livro e as tarefas na fila (pelos caminhos que existem: PR com registro; `ci/fila.py criar`). Sem tabela nova de `review_session`: a reunião É os registros que ela produz. |
| 22 | Restrição dominante atual ("uma seta gigante"), com cartão: linha de base, valor atual, alvo, impacto estimado, confiança, evidência, dono, os cinco passos da Teoria das Restrições. E a IA só pode propor "suspeita"; humano promove a "confirmada". | Doc 1 §8 a §10, §33; Doc 2 Parte VII; Doc 3 §9, §26 a §30; Doc 4 Parte X | O plano atual §3 andar 3 termina com "o gargalo desta semana é X, porque Y", sem cartão e sem tela. | **NOVA, e é a melhor peça dos quatro documentos.** Entra como cartão `restricao-atual` (regra de cálculo sobre as taxas de passagem da jornada que existe: cadastro → pedido → liberação → primeira entrada → fórum), com "suspeita" calculada e "confirmada" só por registro tipo `decisao` dele. |
| 23 | Os "12 indicadores do CEO" (novos compradores, crescimento, CAC, CAC marginal, payback, margem, LTV/CAC, conversão do core, ativação D7, resultado profissional, receita de indicação, aprendizados validados por ciclo). | Doc 1 §32; Doc 2 Parte XVII; Doc 3 §10; Doc 4 §54, §213 | Nove dos doze dependem de venda ou de anúncio (congelados) ou de células que não existem (cursos, portfólio, indicação). Sobram hoje, com fonte: ativação (primeira ação em 7 dias, quando a célula de cursos nascer; hoje "entrou pela primeira vez") e aprendizados validados por ciclo (calculável do livro: registros tipo `medicao` que respondem a experimentos). | **MANTIDA a ideia, traduzido o conteúdo:** o placar de doze nasce com os doze cartões, e cada um diz "sem dados até X" onde não há fonte. Ver §4, item 2. |
| 24 | Laboratório de experimentos: cartão (problema, hipótese, métrica primária, guardas, variante, público, prazo, resultado, decisão), estados, backlog priorizado por ICE+, atribuição de variante por pessoa, aprendizado extraído. | Doc 1 §11, §12; Doc 2 Parte VIII; Doc 3 §31 a §35; Doc 4 Parte XIII | O plano atual §7 já mapeou: experimento = registro tipo `medicao` com campos de experimento; resultado = registro que `responde_a`; "abertos, vencidos, decididos" calculados. Atribuição de variante por pessoa (teste A/B no site) não existe e depende de tráfego que ainda não é medido. | **JÁ DESENHADO** o cartão de experimento como registro; **NOVA** a tela do laboratório (lista calculada do livro) e a "velocidade de aprendizado validado" como cartão. Teste A/B com variante por pessoa fica desenhado, sem fonte, até haver contagem de visitas (decisão dele em aberto desde 25/08, `PLANO-AREA-ADMIN.md` §4.6b). |
| 25 | Alocação de capital com fórmula (contribuição esperada × confiança × encaixe estratégico ÷ capital × payback × complexidade), carteira 60/30/10, portas de escala em 8 perguntas, capacidade por recurso (inclusive "capacidade da fundadora"). | Doc 1 §21 a §23; Doc 2 Partes XII, XIII, XXI; Doc 3 §51 a §53, §69 a §73; Doc 4 Partes XVI, XX, XXI | Portões de escala já estavam no plano atual §7.1 (registro com evidência por portão; motor verde só com todos). Capital em dinheiro depende de venda e anúncio. Capacidade de gente (horas da professora por semana) é medição digitada. | **MANTIDA a parte que tem sujeito:** portões como registros; capacidade como cartão de medição digitada (autoridade `mantenedor`). A alocação de capital em reais fica desenhada, sem fonte, com a venda. A "carteira 60/30/10" vira uma vista calculada do livro e da fila: quantos registros e tarefas de cada frente (`site`, `comunidade`, `curso`, `vender`, `fabrica`) nos últimos 30 dias, que é um número que a casa já tem. |
| 26 | Regra dos três cliques: número → diagnóstico → ação. "Se este número mudar, alguém faz algo diferente? Se não, sai da primeira tela." Toda tela termina numa ação. Fato e hipótese nunca se misturam; toda afirmação da IA traz evidência, confiança, explicações alternativas e próximo passo. Estado vazio honesto ("dados insuficientes: precisa de X, tem Y"). Dado velho marcado como velho. | Doc 3 §2, §125, §126, §132, §150, §151; Doc 4 §233, §237 a §239, Parte LXXII | Compatível com as quatro leis do painel do dono (verde só com prova; "não consigo contar" ≠ zero; frescor computado; a página depõe sobre si mesma). | **NOVA como régua de desenho de toda tela**, e vira teste-guarda onde der (todo cartão no andar 0 tem `acao`, o link de "o que fazer"; tile sem `acao` reprova). |
| 27 | Três latências organizacionais: sinal → decisão, decisão → execução, experimento encerrado → aprendizado incorporado. | Doc 3 §166 a §169 | Não existe, e é calculável HOJE do livro e da fila: `pendencia` (sinal) → `resposta` (decisão) → `TAR` reivindicada (execução) → `armadilha` ou `medicao` (aprendizado), cada um com data. | **NOVA**, e é o único indicador dos documentos que já tem fonte completa no dia em que este confronto foi escrito. Entra como três cartões de tipo `confianca` sobre a própria gestão. |
| 28 | Laços de crescimento (resultado → caso → conteúdo → audiência → aluno; aluno → indicação → aluno), com taxa de amplificação e tempo de ciclo. | Doc 1 §17, §18; Doc 2 Parte IX; Doc 3 §14, §62 a §64 | Indicação não existe em célula nenhuma (plano atual §6: "não existe em lugar nenhum"). Conteúdo e audiência são de fora do site. | **DESENHADO, SEM FONTE.** Cartões nascem com `sem_fonte_porque`; o laço de indicação depende de um evento que só uma célula futura emitirá. |
| 29 | "Toda revisão trimestral mata alguma coisa" (a seção obrigatória de parar de fazer). Pré-mortem e time vermelho antes de grande iniciativa. | Doc 2 Partes XXIII, XLI; Doc 3 §111, §143 | Sem equivalente formal. A casa tem o hábito (alternativas recusadas nominalmente em toda decisão; bancas de auditoria antes de planos grandes; `armadilhas/`), mas não como passo obrigatório da cadência. | **NOVA**, barata: a pauta do fechamento de ciclo ganha o passo "o que paramos de fazer", que produz um registro tipo `decisao`; e todo plano novo passa por uma banca (já é prática) cujo parecer entra em `docs/consultorias/`. |
| 30 | Qualidade de dados: regras (compra sem pessoa, matrícula sem pagamento, id duplicado, data impossível), nota de confiança composta, conciliação diária, fila de eventos mortos com "inspecionar, tentar de novo, descartar com motivo". | Doc 2 Parte XXIV; Doc 3 §88 a §90; Doc 4 Partes XXVI, XLVIII | O plano atual §3 andar 4 e §5.2 já pedem cobertura, frescor, conciliação como sonda, confiança por indicador, linhagem, e fila de exceção fail-closed para fato financeiro. As sondas do sistema imunológico existem para outras coisas. | **JÁ DESENHADO**; nasce com a `metricas`. O que o Doc 4 acrescenta e entra: as regras de qualidade como ARQUIVOS (uma por regra, como os cartões), e a fila de eventos mortos visível no painel com as três ações. |
| 31 | Previsão com três cenários e faixas; simulador ("se o CAC subir 20%"). | Doc 2 Parte XXXI; Doc 3 §112 a §114; Doc 4 Parte XXXI | Nada. Depende de história de venda que não existe. Os próprios documentos põem isto por último. | **DESENHADO, SEM FONTE.** Nenhum PR nasce disto antes de haver doze meses de coorte. |
| 32 | IA analista, IA estrategista, IA cientista de experimentos, IA de sucesso do aluno, IA time vermelho, IA orquestradora; um copiloto lateral em toda tela ("pergunte ao Revenue Brain"). | Doc 2 Parte XXVII; Doc 3 §17, §141 a §144; Doc 4 Partes XXXII, XXXIII | A casa já tem: o robô que rascunha resposta no fórum (Haiku; falta a chave da Anthropic, pendência dele), os robôs de despacho (que analisam, consolidam e geram tarefas pela fila), o sino das armadilhas (o "auditor de dados" da fábrica). O contrato de saída da IA (afirmação, evidência, confiança, alternativas, próximo passo) casa com o registro tipo `nota` com `evidencia`. Os documentos põem a IA por último (Doc 4 §218). | **MANTIDA a ordem (por último)** e **JÁ EXISTE** a fundação. Não nascem seis agentes com nome: nasce, quando chegar a vez, UM robô analista que escreve registros tipo `nota` com o contrato de saída dos documentos, pela mesma chave que o fórum vai usar. |
| 33 | Modo da empresa: FIND, PROVE, SCALE, COMPOUND; fase atual "PROVE". | Doc 2 Partes I e III; Doc 3 §6 | Sem venda, a escola está em FIND por definição (o próprio Doc 2 §4: "existe um motor funcionando?" é a pergunta de FIND). | **MANTIDA a régua;** o cabeçalho diz "achando" até a primeira venda repetida três ciclos, e a fase é calculada dos portões (plano atual §7.2), nunca digitada. |
| 34 | O nome: "Meshcraft Scale OS", "Command Center", "Revenue Brain", "Growth Lab", "M-ROS". | Todos | O plano atual chama de "painel de gestão do negócio (Meshcraft 10X)". A casa fala português com o dono (painel leigo, zero sigla, `feedback_painel_leigo`). | **PARA ELE** (pergunta 4): o nome do sistema é dele. As telas, em qualquer caso, ficam em português sem sigla: "a restrição desta semana", "o laboratório", "o que mudou". |

---

## §2 O que os quatro documentos assumem sobre gente e que a casa não tem

Vale escrever num lugar só, porque atravessa dezenas de itens:

| O documento fala de | A casa tem |
|---|---|
| CEO, seis donos de área, vendedores, analistas, "Anderson" e "Lívia" como fundadores com capacidade medida em horas | O mantenedor (leigo, único administrador), a professora (Lívia), e os robôs. Nenhum dos dois tem "horas por semana" registradas em lugar nenhum. |
| Reuniões com vários participantes marcando "feito / parcial / não feito" | Uma pessoa lendo o painel; robôs que reportam por registro; a professora, se ele quiser (pergunta 3). |
| Uma "organização" que precisa saber "onde pressionar" | Um dono que precisa saber o que fazer na segunda-feira, e robôs que pegam tarefa no balcão. |

A consequência para o desenho: toda peça que diz "owner" vira `autoridade` (a
célula dona do número, ou `mantenedor`), e toda peça que diz "equipe marca" vira
"registro no livro". Não é redução: é o tamanho real do sujeito.

---

## §3 O que já existe na casa com outro nome (o mapa, para não reconstruir)

| Nos documentos | Aqui | Estado em 03/09/2026 |
|---|---|---|
| Task Engine, Kanban, locks, batches, conflict group, READY | `fila/` + `ci/fila.py` + `ci/reservar.py` + `celulas.yml`/`toca` + `RUNBOOK-LOTES.md` | No ar desde 29/08; 106 tarefas na fila |
| Robot Operations, NOC de agentes, agent performance | `/admin/caixa/robos/` (quadro + ao vivo + esperas); `ci/telemetria.py` + `ci/termometro.py` | No ar |
| Review / Exception | registro tipo `pendencia` com `se_eu_nao_decidir`, `recomendacao`, `reversivel`, `impacto` | No ar |
| Approval Inbox, Executive Inbox | a caixa "precisa de você" (calculada) em `/admin/painel/` | No ar |
| Decision Memory, Decision Card, review job | registros tipo `decisao` + `responde_a` + `vence_em_dias`; `docs/decisoes/DECISAO-*.md` | No ar (o vencimento é cobrado pelo painel ao abrir) |
| Validated Learnings | `armadilhas/` (uma por arquivo) + sino + índice gerado | No ar (272 entradas) |
| Metric Registry | `painel/cartoes/` | No ar (2 cartões); faltam 4 campos (§1 item 10) |
| Audit log | auditoria append-only da `admin` com trigger | No ar |
| Incident Center, timeline, post-mortem | registro tipo `incidente`; `alarme-main.yml`; `ci/reversao.py`; `armadilhas/` como post-mortem | No ar |
| Event registry, contract registry, JSON Schema validation, idempotency | `contracts/eventos/*.json` (schema por versão, `additionalProperties: false`), `ci/contract_freeze.py`, consumo idempotente por `event_id` como lei | No ar (16 contratos de evento) |
| Change log com plano de volta | PR + `ci/portao_de_deploy.py` + rollback medido em 76 s | No ar |
| Data confidence, "não inventar precisão" | a distinção `None` / `0` / `contavel` da jornada; "não comprovado" no livro; a aba Operação do painel conta o que tem prova | No ar |
| Saved views, filtros na URL | `/admin/escola/alunos/?estado=…` (a jornada já leva à lista filtrada) | Parcial, no ar |
| Mapa de rotas, "toda porta existe" | `painel/mapa-do-site.json` + `ci/mapa_do_site.py` | No ar |
| Founder bottleneck ("fundador vira restrição") | medido, não desenhado: "o degrau mais lento é a assinatura do mantenedor" (painel da Caixa, 28/08); mediana de 22 min e média de 264 min por merge esperando humano (PLANO-10X) | Conhecido; a Lei 4 tirou o humano do caminho crítico do merge |
| Weekly review, MBR, QBR | cadência do plano atual §4.2 (segunda-feira; pós-lançamento como `medicao`) | Desenhado, sem tela |
| Current Constraint | "o gargalo desta semana é X" (plano atual §3 andar 3) | Desenhado, sem cartão e sem tela |
| Experiment card | registro tipo `medicao` com campos de experimento (plano atual §7) | Desenhado, sem tela |
| Scale gates, três modos | plano atual §7.1 e §7.2 | Desenhado |
| Cohort engine, snapshots D0..D365 | plano atual §5.5, célula `metricas` | Desenhado; célula não existe |
| Event store imutável, DLQ, fail-closed financeiro | plano atual §5.2, célula `metricas` | Desenhado; célula não existe |
| Next Best Action, roteador automação/humano/robô | plano atual §9 (degrau 9); `mensageria/apps/jornadas` | Desenhado; as jornadas existem (boas-vindas ligada) |
| Learning funnel, at-risk students, outcome stages O0..O6 | marcos do plano atual §5.4; `/admin/escola/jornada/` (8 paradas) | A jornada existe; marcos além de "entrou" dependem da célula de cursos (não existe) |

---

## §4 O que é novo de verdade e entra no plano reformulado

Seis peças que a sessão anterior não tinha e que os documentos trazem
prontas para traduzir:

1. **A restrição desta semana como cartão e como bloco da capa** (§1 item 22).
   Calculada das taxas de passagem entre as paradas da jornada que existe.
   "Suspeita" é cálculo; "confirmada" é registro de decisão dele.
2. **O placar de doze, honesto.** Os doze cartões nascem; cada um sem fonte
   diz por quê e o que precisa existir para acender ("sem dados até o site
   vender", "sem dados até a célula de cursos nascer", "sem dados até existir
   indicação"). A régua de doze é do documento; a honestidade é da casa.
3. **A régua de desenho de toda tela** (§1 item 26): três cliques, "se este
   número mudar alguém faz algo diferente?", fato ≠ hipótese, estado vazio
   dizendo o que falta, dado velho marcado. Vira campo `acao` obrigatório no
   cartão do andar 0 e teste-guarda.
4. **As três latências da gestão** (§1 item 27): sinal → decisão, decisão →
   execução, experimento → aprendizado. Já calculáveis do livro e da fila.
   São os primeiros cartões de tipo `confianca` sobre a própria gestão.
5. **O modo reunião** (§1 item 21): a pauta guiada de segunda-feira dentro de
   `/admin/`, que termina escrevendo registros e tarefas pelos caminhos que
   existem. Sem tabela nova.
6. **Atribuição declarada pela própria pessoa** ("como você conheceu a
   escola?", Doc v3 §47; Doc 3 §106): é a única forma de atribuição que não
   depende de pixel nem de anúncio, cabe no formulário de pedido de entrada
   (uma pergunta a mais, opcional), e é a semente das coortes por canal. É
   mudança no contrato da `alunos` (Rito de Contrato, com ele presente).

E quatro campos novos no cartão de métrica (§1 item 10): `direcao`, `unidade`,
`frescor_maximo`, `dimensoes`.

---

## §5 O que sobra para o mantenedor (a caixa única)

1. **As duas estrelas-guia** (resultado profissional do aluno; margem mensal):
   entram como o andar de cima da Meta 1, desenhadas e sem fonte, ou ficam de
   fora até terem sujeito.
2. **O Y e a data da Meta 1** (pendência aberta desde o registro
   `20260903-028`). Os documentos propõem ciclo de 12 semanas.
3. **Quem lê o painel além dele**: só ele; ele e a professora com os mesmos
   poderes (uma linha no env); ou ele e a professora só lendo (lei nova na
   `admin`: papel só-leitura, com auditoria).
4. **A nota composta de 0 a 100 no topo**: fica de fora (regra atual), entra
   só com os componentes ao lado, ou entra como os documentos propõem.
5. **O nome do sistema**: "Meshcraft Scale OS" (dos documentos) ou "painel de
   gestão" (da casa). As telas ficam em português sem sigla em qualquer caso.

O que NÃO volta a ele, porque já está decidido e registrado: menores (18+),
equipe de vendas (não existe), CRM (é a plataforma), venda (congelada), onde
moram os fatos (célula `metricas`), onde moram as telas (`/admin/`), onde
moram tarefas e decisões (fila e livro, em arquivo).
