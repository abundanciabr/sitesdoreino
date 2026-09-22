# Levantamento de operação e publicação do quiz

## Escopo e fonte

Este despacho analisou apenas a célula `quiz`, o contrato de evento autorizado,
os workflows em `.github/workflows/` e os documentos da própria célula. A
constituição proíbe ler `infra/` e as demais células
(`constituicoes/AGENTS.quiz.md:10-18`). Portanto, o script `infra/semear-quiz.sh`
foi identificado pelo workflow, mas seu conteúdo e qualquer estado da VPS não
foram auditados.

Cada achado abaixo recebe uma classificação:

- **Confirmado no sistema**: existe no código ou foi medido por comando/teste.
- **Explicação simplificada**: tradução operacional de um comportamento já
  confirmado, sem acrescentar capacidade.
- **Não identificado no código analisado**: não há prova no escopo permitido.

## Caminhos públicos

### Rotas

- **Confirmado no sistema**: o Django declara `healthz`, `telemetry/`,
  `<slug>/` e `<slug>/resultado` em
  `services/quiz/config/urls.py:6-28`. Como produção usa
  `SCRIPT_NAME=/quiz`, os caminhos divulgáveis são `/quiz/healthz`,
  `/quiz/telemetry/`, `/quiz/<slug>/` e
  `/quiz/<slug>/resultado`. A própria configuração explica que o prefixo não
  deve ser repetido no urlconf (`services/quiz/config/urls.py:8-17`).
- **Confirmado no sistema**: `/quiz/healthz` retorna JSON `{"status":"ok"}`;
  a prova focal também cobre a forma pública com prefixo
  (`services/quiz/apps/core/views.py:4-8`,
  `services/quiz/tests/test_superficie_publica.py:200-213`).
- **Confirmado no sistema**: o host precisa existir como `Site` ativo no
  cadastro local. Host desconhecido responde 404 com `site desconhecido`
  (`services/quiz/apps/core/middleware.py:10-18`, `31-41`). Não existe host
  padrão de fallback.
- **Explicação simplificada**: o mesmo slug pode existir em sites diferentes,
  porque a unicidade é por `site` e `slug`, não global
  (`services/quiz/apps/quiz/models.py:23-34`).
- **Confirmado no sistema**: o formulário HTML mostra perguntas, opções e os
  campos e-mail, nome e telefone; e-mail é obrigatório
  (`services/quiz/apps/quiz/templates/quiz/formulario.html:33-64`).
- **Confirmado no sistema**: o POST calcula a pontuação no servidor, grava uma
  submissão e redireciona para o resultado com `?lead=<uuid>`
  (`services/quiz/apps/quiz/views.py:173-259`). O cliente envia IDs de opções,
  nunca o score (`services/quiz/apps/quiz/models.py:69-83`).
- **Confirmado no sistema**: a tela de resultado mostra o diagnóstico e só
  exibe o botão quando destino e rótulo estão presentes
  (`services/quiz/apps/quiz/templates/quiz/resultado.html:18-28`,
  `services/quiz/apps/quiz/models.py:86-128`).
- **Confirmado no sistema**: telemetria aceita somente
  `view_quiz`, `view_question`, `click_option` e `abandon`; o endpoint devolve
  204 no sucesso, 400 para payload inválido, 401 para cookie de sessão ausente
  ou inválido, 413 para corpo acima do limite e 503 quando o Redis falha
  (`services/quiz/apps/quiz/tasks.py:28-35`,
  `services/quiz/apps/quiz/views.py:293-332`).
- **Explicação simplificada**: o quiz é uma página HTML com POST-redirect-GET,
  não uma API JSON de consulta. A lição da célula confirma que não há contrato
  REST, Alpine ou polling (`services/quiz/LICOES.md:98-104`).

### Proteções visíveis na borda

- **Confirmado no sistema**: há middleware CSRF ativo, cookie próprio
  `quiz_csrf`, alcance limitado ao prefixo da célula e suporte ao
  `X-Forwarded-Proto` do Traefik (`services/quiz/config/settings.py:30-56`,
  `76-92`).
- **Confirmado no sistema**: POST sem token, origem de outro site e POST HTTPS
  atrás do proxy são cobertos pela suíte pública
  (`services/quiz/tests/test_superficie_publica.py:215-288`).
- **Confirmado no sistema**: o endpoint de telemetria é exceção explícita ao
  CSRF e valida o cookie assinado da sessão antes de publicar
  (`services/quiz/apps/quiz/views.py:293-315`).

## Seed e publicação

### Seed local

- **Confirmado no sistema**: o comando real é
  `py -3.12 manage.py seed_quiz`. Exige `--host`, `--site-id`, `--site-name`
  e `--destino-do-botao`; `--slug` tem padrão `crivo` e `--variacao` é opcional
  (`services/quiz/apps/quiz/management/commands/seed_quiz.py:187-214`).
- **Confirmado no sistema**: o seed cria ou reutiliza `Site`, quiz, versão,
  perguntas e opções; as faixas usam `update_or_create` para convergir dados
  antigos sem botão. A operação é transacional e idempotente
  (`services/quiz/apps/quiz/management/commands/seed_quiz.py:216-271`).
- **Confirmado no sistema**: o destino do botão é dado opaco fornecido pelo
  operador. O comando não inventa checkout nem oferta
  (`services/quiz/apps/quiz/management/commands/seed_quiz.py:195-208`,
  `services/quiz/apps/quiz/models.py:95-110`).
- **Confirmado no sistema**: são recusados o slug `telemetry` e slugs que
  começam pelos caminhos isentos de resolução de site, como `healthz` e
  `static`; o erro informa o motivo e pede outro slug
  (`services/quiz/apps/quiz/management/commands/seed_quiz.py:69-95`).
- **Confirmado no sistema**: variações são lidas de um arquivo JSON informado
  em `--variacao` e têm validação de estrutura, peso, perguntas, opções e
  faixas (`services/quiz/apps/quiz/management/commands/seed_quiz.py:98-184`).
- **Explicação simplificada**: `--site-id` é a costura manual entre o cadastro
  local do quiz e o identificador usado pelo catálogo. O código não consulta o
  catálogo nem verifica se os IDs continuam iguais
  (`services/quiz/apps/quiz/models.py:6-20`,
  `services/quiz/LICOES.md:28-40`).

### Publicação de conteúdo

- **Confirmado no sistema**: existe o workflow `semear-quiz`, disparado
  manualmente por `workflow_dispatch`, com `host` obrigatório e padrão
  `meshcraft.top` (`.github/workflows/semear-quiz.yml:45-62`).
- **Confirmado no sistema**: o workflow só aceita a branch `main`, confere que
  `infra/semear-quiz.sh` existe e passa na sintaxe, envia `HOST_QUIZ` por
  ambiente e executa o script pela conexão SSH da ação
  (`.github/workflows/semear-quiz.yml:71-110`).
- **Confirmado no sistema**: uma conexão SSH bem-sucedida não basta. O workflow
  exige a sentinela `PRONTO: o Crivo existe em ` na saída do seed
  (`.github/workflows/semear-quiz.yml:112-138`).
- **Não identificado no código analisado**: o conteúdo de
  `infra/semear-quiz.sh`, a consulta que gera a sentinela, o host real, o
  segredo SSH e o resultado de uma execução na VPS. A constituição da célula
  proíbe ler `infra/` (`constituicoes/AGENTS.quiz.md:10-18`).
- **Confirmado no sistema**: publicação de código é separada do seed. O
  workflow `deploy-celula` reage a push na `main`, detecta células tocadas e
  passa pelo job `portao-de-deploy` antes da publicação
  (`.github/workflows/deploy-celula.yml:16-19`, `67-181`).
- **Explicação simplificada**: mergear código não semeia um quiz novo. Para
  conteúdo, é necessário o workflow manual de seed, com um host escolhido no
  disparo.

### Evento após o envio

- **Confirmado no sistema**: a submissão e o evento de outbox são gravados na
  mesma transação; o relay é chamado após o commit
  (`services/quiz/apps/quiz/views.py:219-253`).
- **Confirmado no sistema**: o relay publica em Redis antes de preencher
  `published_at`; falha deixa o evento pendente para nova tentativa
  (`services/quiz/apps/quiz/tasks.py:38-70`).
- **Confirmado no sistema**: há uma tarefa periódica a cada minuto, executada
  pelo worker `python manage.py run_huey`
  (`services/quiz/apps/quiz/tasks.py:190-201`,
  `services/quiz/config/settings.py:60-74`).
- **Explicação simplificada**: a resposta HTTP do quiz pode terminar mesmo que
  o Redis esteja indisponível, porque a submissão fica na outbox e o relay
  tenta novamente (`services/quiz/apps/quiz/tasks.py:73-81`).
- **Não identificado no código analisado**: o worker efetivamente ativo na
  produção e os valores reais de `REDIS_STREAMS_URL` e `HUEY_REDIS_URL`.
  O código só prova a configuração e o caminho de retry
  (`services/quiz/LICOES.md:87-96`).

## Configuração necessária

- **Confirmado no sistema**: `DJANGO_SECRET_KEY` e `DATABASE_URL` são
  obrigatórios no import das configurações; a ausência levanta
  `ImproperlyConfigured` com o nome da variável
  (`services/quiz/config/settings.py:13-20`, `58`).
- **Confirmado no sistema**: `SCRIPT_NAME` define o prefixo público da célula;
  sem ele o valor fica nulo (`services/quiz/config/settings.py:20-24`).
- **Confirmado no sistema**: `HUEY_REDIS_URL` tem fallback local no import para
  não derrubar o web; `REDIS_STREAMS_URL` é lida apenas no ponto de uso
  (`services/quiz/config/huey.py:5-14`,
  `services/quiz/apps/quiz/tasks.py:41-46`).
- **Confirmado no sistema**: `ALLOWED_HOSTS` é `*`, mas a aceitação efetiva do
  site depende do `Site` ativo resolvido pelo host
  (`services/quiz/config/settings.py:26-28`,
  `services/quiz/apps/core/middleware.py:31-41`).
- **Explicação simplificada**: a variável de banco aponta para a única base da
  célula; a constituição nomeia esse banco como `quiz_db` e o papel como
  `quiz_user` (`constituicoes/AGENTS.quiz.md:15-19`). O valor real não está no
  repositório analisado.

## Erros, diagnóstico e estados de entrada

- **Confirmado no sistema**: e-mail ausente retorna 422 com
  `e-mail é obrigatório`; pergunta faltante retorna 422 com
  `responda todas as perguntas` (`services/quiz/apps/quiz/views.py:181-192`).
- **Confirmado no sistema**: opção que não pertence à pergunta levanta 404 com
  `opção inválida para esta pergunta` (`services/quiz/apps/quiz/views.py:193-218`).
- **Confirmado no sistema**: lead ausente ou inválido no resultado retorna 404;
  versão sem faixa ativa também não produz resultado válido
  (`services/quiz/apps/quiz/views.py:260-292`).
- **Confirmado no sistema**: o seed falha alto para arquivo de variação ausente,
  JSON inválido, estrutura incompleta, peso inválido e botão sem destino ou
  rótulo correspondente (`services/quiz/apps/quiz/management/commands/seed_quiz.py:98-184`).
- **Confirmado no sistema**: a suíte de relay guarda que falha do Redis não
  quebra o POST e mantém o evento pendente
  (`services/quiz/tests/test_inv_relay_outbox.py:91-127`).
- **Não identificado no código analisado**: uma tela própria de erro 404/500,
  um painel público de diagnóstico, comando de verificação do estado real da
  VPS ou procedimento de correção fora do pipeline. No escopo lido, o sistema
  usa as respostas HTTP do Django e as sentinelas dos workflows.

## Privacidade e dados pessoais

- **Confirmado no sistema**: o formulário coleta e-mail, nome e telefone
  (`services/quiz/apps/quiz/templates/quiz/formulario.html:48-60`).
- **Confirmado no sistema**: `Submission` armazena e-mail, nome, telefone,
  respostas, score, resultado, `site_id`, UTM e horário
  (`services/quiz/apps/quiz/models.py:132-161`).
- **Confirmado no sistema**: o evento `quiz.completado` inclui o lead e UTM no
  payload da outbox (`services/quiz/apps/quiz/views.py:220-252`).
- **Confirmado no sistema**: a telemetria registra eventos de navegação e
  opções em stream Redis com limite aproximado de 100.000 mensagens; o lead
  completo permanece na submissão (`services/quiz/apps/quiz/tasks.py:28-35`,
  `services/quiz/apps/quiz/models.py:177-182`).
- **Não identificado no código analisado**: política de privacidade, aviso de
  tratamento, consentimento explícito, prazo de retenção, anonimização,
  exclusão sob solicitação ou rotina de apagamento dos dados de `Submission`.
  A busca ficou restrita a `services/quiz/`, `docs/quiz/` e ao contrato do
  evento autorizado; nenhum desses arquivos apresentou esse mecanismo.

## Limites do que o sistema faz e não faz

| Faz | Não faz ou não foi provado |
| --- | --- |
| Publica páginas HTML do quiz por host e slug. | Não expõe API REST JSON. |
| Calcula score no servidor e mostra uma faixa. | Não consulta o catálogo para resolver o host. |
| Emite `quiz.completado.v1` por outbox e relay Redis. | Não cria pedido, pagamento ou matrícula. |
| Guarda snapshot local da submissão. | Não comprova sincronização contínua do `site_id` com o catálogo. |
| Aceita telemetria limitada por cookie assinado. | Não apresenta mecanismo de privacidade ou retenção no código analisado. |
| Permite seed idempotente por host no workflow manual. | Não foi provada uma execução real na VPS neste despacho. |

Fontes de fronteira: `constituicoes/AGENTS.quiz.md:5-28`,
`services/quiz/LICOES.md:28-40`.

## Comandos de prova executados

Os comandos abaixo foram executados no worktree próprio. Os valores de ambiente
usados para testes foram `DJANGO_SECRET_KEY=ci-apenas-nunca-em-producao`,
`DATABASE_URL=sqlite:///:memory:`, `REDIS_STREAMS_URL=redis://localhost:6379/0`
e `HUEY_REDIS_URL=redis://localhost:6379/1`.

1. `python ci/economia_da_fabrica.py brief --tipo diagnostico --objetivo "levantar operacao publica, seed, publicacao e limites do quiz" --celula quiz --alvo docs/quiz/levantamentos/frente-operacao-publicacao.md`
   Resultado: brief compilado, com objetivo, célula e prova exigida.
2. `py -3.12 manage.py seed_quiz --help`
   Resultado: uso exibido; argumentos obrigatórios confirmados, incluindo
   `--destino-do-botao`.
3. `py -3.12 -m pytest -q`
   Resultado: `66 passed in 0.88s`.
4. `py -3.12 -m pytest -q tests/test_smoke.py tests/test_superficie_publica.py tests/test_botao_por_faixa.py`
   Resultado: `27 passed in 0.55s`.
5. `py -3.12 -m black --check apps config tests`
   Resultado: `30 files would be left unchanged`.
6. `make ci` pelo PowerShell
   Resultado: `ERROR` antes dos testes. O `make` local executou a receita POSIX
   `[ -f ... ]` no `cmd.exe`, que respondeu `-f foi inesperado neste momento`.
   A suíte oficial foi medida diretamente com Python 3.12, o interpretador
   declarado no workflow (`.github/workflows/ci-celula.yml:37-39`).
7. Tentativa de instalar `services/quiz/requirements.txt` com Python 3.14
   Resultado: `ERROR`, pois `psycopg-binary==3.2.3` não tem distribuição para
   Python 3.14. A prova foi repetida com o Python 3.12 disponível no host.

## Conclusão operacional

**Confirmado no sistema**: para publicar um quiz de um site, o operador precisa
de um código já na `main`, de um `host` ativo e dos identificadores corretos, e
deve disparar `semear-quiz` com esse host. O workflow confirma a branch, executa
o seed pela infraestrutura autorizada e só aceita a sentinela `PRONTO:`.

**Não identificado no código analisado**: prova de que qualquer quiz está hoje
publicado, prova de execução do worker na VPS e cobertura de privacidade para os
dados coletados. Esses pontos exigem consulta ao ambiente de produção ou decisão
do mantenedor, fora da fronteira deste despacho.
