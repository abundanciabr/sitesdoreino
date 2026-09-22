# Levantamento da operação do Crivo

Data da leitura: 22/09/2026.

Escopo: código real da célula `quiz`, seus testes, seed e constituição. Este
arquivo é um levantamento para o manual. Não é uma especificação nova e não
altera o comportamento do sistema.

## Fonte de autoridade da célula

- **Confirmado no sistema**: a constituição define o Crivo como motor de
  perguntas, respostas, pontuação, resultado e qualificação. Ele não conhece
  cartão de crédito, expõe páginas públicas em `/quiz/*`, não consome outra
  célula e emite `quiz.completado.v1` por outbox e relay. A pontuação deve ser
  calculada no servidor e o evento deve ser transacional. Fonte:
  `constituicoes/AGENTS.quiz.md:6-25`.
- **Explicação simplificada**: o quiz faz a triagem e entrega um resultado;
  checkout e cadastro de pessoa ficam fora dele.
- **Confirmado no sistema**: a resolução de Host para site é local, consultando
  `Site`, e Host não cadastrado gera 404. O próprio código registra que a célula
  não chama o catálogo. Fontes: `services/quiz/apps/core/middleware.py:4-43`;
  `services/quiz/apps/quiz/models.py:6-20`;
  `services/quiz/tests/test_smoke.py:61-65`.

## Experiência do visitante

- **Confirmado no sistema**: a jornada pública é GET do formulário, respostas
  em etapas, coleta de e-mail, nome e telefone, POST para calcular o resultado,
  redirecionamento com `?lead=<id>` e GET da tela de resultado. Fontes:
  `services/quiz/config/urls.py:26-28`;
  `services/quiz/apps/quiz/templates/quiz/formulario.html:33-63`;
  `services/quiz/apps/quiz/views.py:173-258`;
  `services/quiz/apps/quiz/views.py:260-275`;
  `services/quiz/tests/test_smoke.py:68-93`.
- **Explicação simplificada**: a pessoa responde uma pergunta por vez,
  informa o e-mail e recebe uma classificação com próximo passo.
- **Confirmado no sistema**: as perguntas são renderizadas no mesmo HTML. O
  JavaScript apenas esconde e mostra os `fieldset`; sem JavaScript, o formulário
  continua contendo todas as perguntas. O navegador recebe `Continuar` para
  avançar e `Ver resultado` no último passo. Fonte:
  `services/quiz/apps/quiz/templates/quiz/formulario.html:37-63`;
  teste `services/quiz/tests/test_telemetria.py:87-101`.
- **Confirmado no sistema**: e-mail é obrigatório no servidor; pergunta ausente
  devolve 422 com a mensagem `responda todas as perguntas`; opção que não
  pertence à pergunta gera 404. Fontes:
  `services/quiz/apps/quiz/views.py:183-213`;
  `services/quiz/apps/quiz/templates/quiz/formulario.html:42-58`.
- **Confirmado no sistema**: o formulário inclui CSRF, há middleware de CSRF e
  o fluxo normal atrás do proxy HTTPS passa; POST sem token ou de origem externa
  é recusado e não grava submissão. Fontes:
  `services/quiz/apps/quiz/templates/quiz/formulario.html:35-36`;
  `services/quiz/config/settings.py:22-56,76-84`;
  `services/quiz/tests/test_superficie_publica.py:215-288`.
- **Confirmado no sistema**: a URL pública é `/quiz/<slug>/` quando o prefixo
  de produção está ativo, o resultado usa `/quiz/<slug>/resultado` e a forma
  dobrada `/quiz/quiz/<slug>/` é recusada. Fontes:
  `services/quiz/config/urls.py:8-28`;
  `services/quiz/tests/test_superficie_publica.py:153-200`.
- **Não identificado no código analisado**: indicador visual de progresso,
  estado de carregamento ou confirmação visual antes do envio. O template
  contém somente a alternância de etapas, os dois botões e os campos citados:
  `services/quiz/apps/quiz/templates/quiz/formulario.html:37-63`.

## Montagem do quiz

- **Confirmado no sistema**: um quiz pertence a um `Site`, tem slug, título e
  estado ativo; o par site e slug é único. Fonte:
  `services/quiz/apps/quiz/models.py:6-35`.
- **Confirmado no sistema**: a montagem operacional observada é o comando
  `seed_quiz`. Ele exige `--host`, `--site-id`, `--site-name` e
  `--destino-do-botao`; aceita slug e um arquivo opcional de variação. Fonte:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:187-223`.
- **Confirmado no sistema**: o seed roda dentro de transação, cria ou encontra
  site, quiz e versão original, planta perguntas, opções e faixas, e atualiza
  faixas existentes para preencher o CTA. Fonte:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:228-272`.
- **Confirmado no sistema**: o seed é idempotente no cenário testado: a segunda
  execução mantém um quiz, três perguntas, nove opções e três faixas, sem
  criar submissão duplicada. Fonte:
  `services/quiz/tests/test_botao_por_faixa.py:180-191`.
- **Confirmado no sistema**: o comando recusa slug que colide com caminhos
  isentos ou com `telemetry`, e a mensagem informa o problema e pede outro
  slug. Fontes:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:69-95`;
  `services/quiz/tests/test_superficie_publica.py:337-371`;
  `services/quiz/tests/test_telemetria.py:353-386`.
- **Não identificado no código analisado**: tela administrativa, CRUD web ou
  outro editor para montar o quiz. A operação de montagem encontrada está
  concentrada no comando de seed e nos modelos citados acima.

## Perguntas e opções

- **Confirmado no sistema**: cada `Question` pertence a uma versão, tem ordem e
  texto; a ordem é única dentro da versão. Cada `Option` pertence a uma
  pergunta, tem ordem, texto e inteiro de pontos; a ordem é única dentro da
  pergunta. Fonte:
  `services/quiz/apps/quiz/models.py:53-84`.
- **Confirmado no sistema**: o seed original contém três perguntas e três
  opções por pergunta, com pontos 0, 5 e 10. A variação em JSON exige uma lista
  não vazia de perguntas, opções com texto e pontos inteiros. Fontes:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:11-35`;
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:124-146`.
- **Confirmado no sistema**: a página não envia pontos para o navegador. Ela
  envia apenas o id da opção; no POST o servidor busca a opção dentro da
  pergunta e soma `opcao.points`. Fontes:
  `services/quiz/apps/quiz/templates/quiz/formulario.html:39-44`;
  `services/quiz/apps/quiz/views.py:193-213`;
  `services/quiz/tests/test_telemetria.py:87-101`;
  `services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py:32-68`.
- **Explicação simplificada**: o visitante escolhe respostas, mas não escolhe
  quanto elas valem.
- **Confirmado no sistema**: opção de outra pergunta ou de outro quiz não é
  aceita e nenhuma submissão é gravada nesse caso. Fonte:
  `services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py:51-68`.
- **Não identificado no código analisado**: validação operacional que impeça
  uma pergunta sem opções fora do caminho do seed de variação. O seed de
  variação recusa essa entrada, mas não há uma restrição equivalente visível no
  modelo `Question`: `services/quiz/apps/quiz/management/commands/seed_quiz.py:124-130`;
  `services/quiz/apps/quiz/models.py:53-67`.

## Pontuação, faixas e CTA

- **Confirmado no sistema**: a pontuação começa em zero e é a soma dos pontos
  das opções escolhidas. A faixa é selecionada por `min_score <= score <=
  max_score`; se nenhuma cobrir o valor, o resultado usa `sem_faixa`. Fontes:
  `services/quiz/apps/quiz/views.py:193-217`;
  `services/quiz/apps/quiz/models.py:101-127`.
- **Confirmado no sistema**: o seed original cria as faixas `iniciante` de 0 a
  9, `intermediario` de 10 a 19 e `avancado` de 20 a 30, com título,
  descrição, destino e rótulo de botão. Fonte:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:41-67,250-268`.
- **Confirmado no sistema**: o CTA pertence à faixa, não à página. A tela de
  resultado mostra o destino e rótulo da faixa selecionada; faixa sem destino
  não produz link. Fontes:
  `services/quiz/apps/quiz/templates/quiz/resultado.html:18-26`;
  `services/quiz/tests/test_botao_por_faixa.py:66-111`.
- **Confirmado no sistema**: destino e rótulo precisam existir juntos; o banco
  aplica a regra e o seed também a valida para faixas de variação. Fontes:
  `services/quiz/apps/quiz/models.py:109-127`;
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:164-182`;
  `services/quiz/tests/test_botao_por_faixa.py:113-143`.
- **Confirmado no sistema**: o destino do botão é obrigatório no comando de
  seed e não é uma constante de checkout dentro da célula. O teste prova que a
  ausência do argumento recusa antes de criar quiz ou faixa. Fontes:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:194-209`;
  `services/quiz/tests/test_botao_por_faixa.py:193-217`.
- **Explicação simplificada**: a faixa explica o resultado e encaminha a pessoa
  para o próximo passo plantado pelo operador.
- **Não identificado no código analisado**: uma guarda que obrigue faixas a
  cobrir todo o intervalo possível sem sobreposição. A seleção usa a primeira
  faixa que satisfaz os limites, e o seed define os valores conhecidos, mas não
  há `CheckConstraint` de cobertura ou exclusividade de intervalos nas linhas
  observadas. Fontes:
  `services/quiz/apps/quiz/views.py:215-216`;
  `services/quiz/apps/quiz/models.py:101-127`.

## Sessões, versões e reenvio

- **Confirmado no sistema**: cada visita recebe UUID e a seleção da versão é
  determinística pelo UUID. Só entram versões ativas com peso maior que zero;
  o peso participa do corte proporcional. Sem versão elegível, a abertura
  devolve 404. Fontes:
  `services/quiz/apps/quiz/views.py:39-55,97-137`;
  `services/quiz/tests/test_telemetria.py:67-85`.
- **Confirmado no sistema**: a visita guarda, em cookie assinado
  `quiz_session`, o mapa por slug com `session_id`, versão, site e UTM. O cookie
  dura sete dias, é HttpOnly, SameSite Lax e limitado ao prefixo da célula.
  Fontes:
  `services/quiz/apps/quiz/views.py:19-21,69-84,140-159`;
  `services/quiz/config/settings.py:50-55`.
- **Confirmado no sistema**: a UTM é capturada na chegada e uma visita seguinte
  não troca a UTM apenas porque a query sumiu. A versão e a UTM aparecem no
  snapshot da submissão. Fontes:
  `services/quiz/apps/quiz/views.py:58-67,97-137,217-232`;
  `services/quiz/tests/test_telemetria.py:103-140`.
- **Confirmado no sistema**: `Submission` guarda quiz, versão, sessão, site,
  score, faixa, respostas, lead, UTM e data; existe unicidade por quiz e
  `session_id`. O reenvio da mesma sessão não cria nova submissão nem novo
  outbox. Fontes:
  `services/quiz/apps/quiz/models.py:132-166`;
  `services/quiz/tests/test_telemetria.py:142-156`.
- **Confirmado no sistema**: o snapshot de respostas usa o formato
  `{question_id: option_id}`, o que permite auditoria posterior sem confiar no
  estado atual do navegador. Fonte:
  `services/quiz/apps/quiz/models.py:147-150`.
- **Confirmado no sistema**: versões extras entram por JSON com `key`, `weight`,
  perguntas, opções e, opcionalmente, faixas próprias. Sem faixas próprias, a
  variação copia as faixas da versão original. Fontes:
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:98-186`;
  `services/quiz/tests/test_telemetria.py:353-383`.
- **Não identificado no código analisado**: tela ou comando separado para
  arquivar uma versão, publicar uma versão em data futura ou alterar o peso com
  histórico de auditoria. O que existe é o estado `active`, o `weight` e a
  atualização do seed: `services/quiz/apps/quiz/models.py:37-50`;
  `services/quiz/apps/quiz/management/commands/seed_quiz.py:119-124`.

## Telemetria da experiência

- **Confirmado no sistema**: o navegador emite `view_quiz`, `view_question`,
  `click_option` e `abandon`; usa `sendBeacon` no abandono quando disponível e
  `fetch` nos demais casos. Fonte:
  `services/quiz/apps/quiz/templates/quiz/formulario.html:76-136`.
- **Confirmado no sistema**: o endpoint de telemetria valida tamanho do corpo,
  JSON, cookie assinado, tipo de evento, elemento e metadados; injeta a UTM da
  sessão e publica no Redis. Sem cookie responde 401; sem banco na ingestão, a
  drenagem posterior persiste `TelemetryEvent`. Fontes:
  `services/quiz/apps/quiz/views.py:291-331`;
  `services/quiz/apps/quiz/models.py:177-201`;
  `services/quiz/tests/test_telemetria.py:158-211`.
- **Confirmado no sistema**: o comando `funil` cruza visualização, hesitação,
  abandono, tempo e conversão por versão e UTM; sem dados informa `nada medido`.
  Fontes:
  `services/quiz/apps/quiz/management/commands/funil.py:24-120`;
  `services/quiz/tests/test_telemetria.py:263-351`.
- **Não identificado no código analisado**: painel web para visualizar esse
  funil. A superfície encontrada é o comando de gestão `funil`.

## Evento de conclusão

- **Confirmado no sistema**: a submissão e `OutboxEvent` são criados na mesma
  transação; o payload carrega `site_id`, slug, faixa, score, versão, lead e
  UTM. O relay é disparado após commit. Fontes:
  `services/quiz/apps/quiz/views.py:220-256`;
  `services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py:71-121`.
- **Confirmado no sistema**: o envelope do outbox é validado nos testes contra
  `contracts/eventos/quiz.completado.v1.json`, e o relay publica antes de marcar
  `published_at`. Fontes:
  `services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py:98-121`;
  `services/quiz/tests/test_inv_relay_outbox.py:57-127`.
- **Explicação simplificada**: concluir o quiz registra o resultado uma vez e
  deixa um evento durável para o restante da plataforma.

## Provas executadas

### Leitura e contexto

Comandos executados:

```text
python ci/sessao.py --celula quiz --tarefa levantamento-frente-operacao --sem-container --contexto --raiz . --caminho services/quiz/ --caminho docs/quiz/levantamentos/frente-operacao.md --sintoma "quiz experiência visitante montagem perguntas opções pontuação faixas CTA sessões versões"
python ci/indice_de_armadilhas.py
```

Resultados observados:

```text
CONTEXTO DIRECIONADO
Leituras obrigatórias: CLAUDE.md, AGENTS.md, CONSTITUICAO.md, RITOS.md, docs/decisoes/RETROSPECTIVA-FASE-D.md, constituicoes/AGENTS.quiz.md, services/quiz/LICOES.md
PASS indice-de-armadilhas: INDICE.md, GUARDAS.json, SINAIS.json, GATILHOS.json regenerado(s) (462 entradas)
```

### Testes do quiz

Primeira tentativa com o Python global não coletou os testes porque faltavam
`django` e `redis`. Essa tentativa ficou registrada para não confundir ausência
de ambiente com falha de produto:

```text
python -m pytest -q tests/test_smoke.py tests/test_inv_pontuacao_servidor_e_outbox.py tests/test_botao_por_faixa.py tests/test_telemetria.py tests/test_superficie_publica.py
5 errors during collection
ModuleNotFoundError: No module named 'django'
ModuleNotFoundError: No module named 'redis'
```

Com o ambiente de quiz existente, SQLite temporário e Redis isolado nos bancos
14 e 15:

```text
python -m pytest -q tests/test_smoke.py tests/test_inv_pontuacao_servidor_e_outbox.py tests/test_botao_por_faixa.py tests/test_telemetria.py tests/test_superficie_publica.py
44 passed in 0.78s

python -m pytest -q
66 passed in 1.18s
```

Os testes completos da célula passaram. O banco SQLite temporário usado na
prova foi `C:\Users\davia\AppData\Local\Temp\quiz-levantamento.sqlite3`;
Redis foi isolado por `redis://localhost:6379/15` e Huey por
`redis://localhost:6379/14`.
