# Levantamento técnico da frente de eventos do quiz

Data da leitura: 22/09/2026.

Escopo: código de services/quiz, contrato contracts/eventos/quiz.completado.v1.json, testes da célula, configurações e comandos locais. O manual final não foi editado.

## Síntese

- **[Confirmado no sistema]** A conclusão do quiz grava uma Submission local e um OutboxEvent na mesma transação. O relay publica quiz.completado.v1 no Redis Stream eventos.quiz.completado. Fontes: services/quiz/apps/quiz/views.py:219-253, services/quiz/apps/quiz/tasks.py:38-70.
- **[Confirmado no sistema]** O quiz não consome API, banco ou código de outra célula. A fronteira declarada é emitir quiz.completado.v1 via outbox e relay. Fonte: constituicoes/AGENTS.quiz.md:10-19.
- **[Explicação simplificada]** Leads e UTMs saem do quiz como dados do evento. Quem quiser transformá-los em cadastro ou timeline precisa ser um consumidor externo do stream. Esse consumidor não está no escopo de leitura desta célula.

## Contrato quiz.completado.v1

- **[Confirmado no sistema]** O envelope exige event, version, event_id, occurred_at e data; event é quiz.completado, version é 1, event_id é UUID e occurred_at é data e hora. Fonte: contracts/eventos/quiz.completado.v1.json:5-12.
- **[Confirmado no sistema]** data exige site_id, quiz_slug, result_key, score e lead. Também aceita version_key com 1 a 100 caracteres e utm como objeto de textos. Fonte: contracts/eventos/quiz.completado.v1.json:13-36.
- **[Confirmado no sistema]** lead exige email e pode carregar name e phone; o contrato não define lead_id. Fonte: contracts/eventos/quiz.completado.v1.json:27-35.
- **[Confirmado no sistema]** O contrato é fechado contra propriedades adicionais no envelope e em data. Fonte: contracts/eventos/quiz.completado.v1.json:5-16.
- **[Explicação simplificada]** O evento leva o fato completo da conclusão, com os dados de contato fornecidos no quiz, e não um identificador opaco de uma célula de leads.
- **[Não identificado no código analisado]** Não foi identificado um consumidor externo, sua política de confirmação Redis, ou sua deduplicação por event_id dentro do escopo permitido. O código do quiz apenas publica.

## Submissão, pontuação e lead local

- **[Confirmado no sistema]** O servidor recalcula a pontuação buscando cada opção pela pergunta e somando Option.points; o valor enviado pelo navegador não participa do cálculo. Fonte: services/quiz/apps/quiz/views.py:193-216; modelo: services/quiz/apps/quiz/models.py:69-75.
- **[Confirmado no sistema]** Uma opção pertencente a outra pergunta é rejeitada com Http404 e nenhuma submissão é criada. Fonte: services/quiz/apps/quiz/views.py:207-213; guarda: services/quiz/tests/test_inv_pontuacao_servidor_e_outbox.py:51-68.
- **[Confirmado no sistema]** Submission é um snapshot local com UUID, quiz, versão, session_id, site_id, pontuação, resultado, respostas, e-mail, nome, telefone, UTM e data. Fonte: services/quiz/apps/quiz/models.py:132-153.
- **[Confirmado no sistema]** A mesma sessão não gera segunda conversão para o mesmo quiz, por restrição única em (quiz, session_id) e get_or_create. Fontes: services/quiz/apps/quiz/models.py:155-162, services/quiz/apps/quiz/views.py:219-234; guarda: services/quiz/tests/test_telemetria.py:142-155.
- **[Confirmado no sistema]** O objeto lead do evento é montado da submissão e contém e-mail, além de nome e telefone quando preenchidos. Fonte: services/quiz/apps/quiz/views.py:235-251.
- **[Confirmado no sistema]** O parâmetro lead da URL de resultado é o UUID da Submission local. A view confere UUID, quiz e site_id; não é chamada a uma API de leads. Fonte: services/quiz/apps/quiz/views.py:260-275.
- **[Explicação simplificada]** Neste código, “lead” significa os dados de contato capturados e o UUID da submissão do quiz. Não há criação de registro em outro banco feita pela célula quiz.
- **[Não identificado no código analisado]** Não foi identificado o processo externo que transforma o lead do evento em cadastro na célula de leads, nem um contrato que forneça um lead_id de retorno.

## UTM e identidade do site

- **[Confirmado no sistema]** Na primeira chegada, a query captura chaves iniciadas por utm_, remove esse prefixo, ignora valores vazios, limita cada valor a 200 caracteres e para após oito chaves. Fonte: services/quiz/apps/quiz/views.py:58-66.
- **[Confirmado no sistema]** A UTM fica no cookie assinado da sessão do quiz por sete dias. Uma visita posterior preserva a UTM original quando a query não está mais presente. Fontes: services/quiz/apps/quiz/views.py:21, 74-135, 140-155.
- **[Confirmado no sistema]** A UTM preservada vai para Submission.utm e para data.utm no evento de conclusão. Fontes: services/quiz/apps/quiz/views.py:217-251; modelo: services/quiz/apps/quiz/models.py:149-152.
- **[Confirmado no sistema]** A telemetria não aceita UTM enviada pelo navegador como fonte de verdade. O servidor remove metadata.utm recebido e repõe a UTM do cookie assinado. Fonte: services/quiz/apps/quiz/views.py:313-326; guarda: services/quiz/tests/test_telemetria.py:158-187.
- **[Confirmado no sistema]** site_id é salvo na submissão, no evento de conclusão e na telemetria. O modelo Site local usa esse valor como chave primária, e o middleware resolve o host para esse cadastro local. Fontes: services/quiz/apps/quiz/models.py:6-20, 132-152, 177-193; services/quiz/apps/core/middleware.py:17-36.
- **[Não identificado no código analisado]** Não existe verificação no código lido de que o site_id local continua igual ao identificador usado por catálogo ou leads. A própria célula registra essa sincronização como responsabilidade do seed manual em services/quiz/apps/quiz/models.py:7-14.

## Outbox e relay de conclusão

- **[Confirmado no sistema]** A submissão e o outbox são criados dentro de transaction.atomic; o evento só nasce quando a submissão é nova. Fonte: services/quiz/apps/quiz/views.py:219-253.
- **[Confirmado no sistema]** Depois do commit, transaction.on_commit chama o relay. Se Redis falhar, a resposta continua sendo redirecionada e o outbox permanece com published_at vazio. Fontes: services/quiz/apps/quiz/views.py:252-253, services/quiz/apps/quiz/tasks.py:73-81; guarda: services/quiz/tests/test_inv_relay_outbox.py:108-126.
- **[Confirmado no sistema]** O relay busca até 200 eventos pendentes, publica primeiro no stream eventos.<evento> e só depois marca published_at. Fonte: services/quiz/apps/quiz/tasks.py:38-70.
- **[Confirmado no sistema]** O envelope publicado usa event, version, event_id, occurred_at e data, e o teste lê a mensagem real do Redis e valida contra o contrato congelado. Fontes: services/quiz/apps/quiz/tasks.py:55-68, services/quiz/tests/test_inv_relay_outbox.py:57-87.
- **[Confirmado no sistema]** O relay é idempotente em relação aos eventos já marcados como publicados; a segunda chamada não duplica a mensagem. Guarda: services/quiz/tests/test_inv_relay_outbox.py:71-87.
- **[Confirmado no sistema]** Há rede de segurança periódica a cada minuto no Huey, executando relay_outbox no worker python manage.py run_huey. Fontes: services/quiz/apps/quiz/tasks.py:195-201, services/quiz/config/settings.py:60-74.
- **[Confirmado no sistema]** REDIS_STREAMS_URL só é lida no ponto de publicação. HUEY_REDIS_URL tem valor padrão local no import do Huey. Fontes: services/quiz/apps/quiz/tasks.py:42-53, 84-92, 142-147; services/quiz/config/huey.py:6-15.
- **[Explicação simplificada]** O navegador não fica dependente de Redis para terminar o quiz. O banco guarda a submissão e o outbox; a publicação pode acontecer logo após o commit ou na tarefa periódica.
- **[Não identificado no código analisado]** Não foi identificado limite de tentativas, fila de erro ou painel de eventos mortos para quiz.completado no produtor quiz.

## Telemetria e Redis Streams

- **[Confirmado no sistema]** O navegador emite view_quiz, view_question, click_option e abandon para POST /telemetry/; abandono usa navigator.sendBeacon quando disponível. Fontes: services/quiz/apps/quiz/templates/quiz/formulario.html:66-137, services/quiz/config/urls.py:25-28.
- **[Confirmado no sistema]** O endpoint rejeita corpo acima de 4096 bytes, JSON inválido, sessão sem cookie assinado, tipo desconhecido, element_id acima de 120 caracteres e metadata que não seja objeto. Fonte: services/quiz/apps/quiz/views.py:291-331.
- **[Confirmado no sistema]** A ingestão publica diretamente no stream telemetry.quiz.events com MAXLEN aproximado de 100.000 itens. Não grava TelemetryEvent na requisição. Fontes: services/quiz/apps/quiz/tasks.py:28-35, 84-92; guarda: services/quiz/tests/test_telemetria.py:158-187.
- **[Confirmado no sistema]** O worker cria o grupo quiz-telemetria, recupera pendentes com XAUTOCLAIM, lê novas mensagens com XREADGROUP, converte mensagens válidas em TelemetryEvent e confirma com XACK. Fonte: services/quiz/apps/quiz/tasks.py:95-187.
- **[Confirmado no sistema]** Mensagens inválidas são descartadas e confirmadas para não prender o grupo. Falha no insert não confirma a mensagem; conflito de stream_id não duplica a linha por ignore_conflicts=True. Fontes: services/quiz/apps/quiz/tasks.py:142-187; guardas: services/quiz/tests/test_telemetria.py:213-251.
- **[Confirmado no sistema]** TelemetryEvent é append-only no banco quiz, com stream_id único, site_id, sessão, slug, versão, tipo, elemento, metadata e timestamps. Fonte: services/quiz/apps/quiz/models.py:177-200.
- **[Explicação simplificada]** Telemetria mede o caminho antes da conversão e pode ser perdida por limite do stream. A conversão não pode ser reconstruída só dela, porque o lead completo permanece na Submission e no evento de conclusão.
- **[Não identificado no código analisado]** Não foi identificado contrato versionado para os itens de telemetria, métrica de descarte, alerta operacional ou política de retenção além do MAXLEN aproximado.

## Limites entre células

- **[Confirmado no sistema]** A célula quiz declara Consome: nada, expõe páginas públicas, emite somente quiz.completado.v1 e usa quiz_db com o papel quiz_user. Fonte: constituicoes/AGENTS.quiz.md:15-19.
- **[Confirmado no sistema]** O contrato de evento é somente leitura para esta frente; não há alteração no arquivo de contrato neste despacho. Fonte: constituicoes/AGENTS.quiz.md:10-12, contracts/eventos/quiz.completado.v1.json.
- **[Confirmado no sistema]** Não há contrato REST JSON da célula quiz. As rotas lidas são páginas de formulário, resultado, telemetria e health check. Fontes: services/quiz/config/urls.py:3-28; services/quiz/Makefile no alvo mocks.
- **[Explicação simplificada]** O limite de responsabilidade é: quiz calcula e guarda o fato local; Redis transporta; consumidores externos decidem como usar o fato. O quiz não busca dados de leads para completar o evento e não consulta catálogo para publicar.
- **[Não identificado no código analisado]** Não foi identificado no código da célula qualquer chamada HTTP ou importação de implementação de leads, checkout ou catálogo para esse fluxo.

## Comandos de prova executados

1. Validação estrutural do contrato:

    python -c "import json; from jsonschema import Draft202012Validator; p='contracts/eventos/quiz.completado.v1.json'; s=json.load(open(p,encoding='utf-8')); Draft202012Validator.check_schema(s); print('schema valido: '+p)"

   Resultado: schema valido: contracts/eventos/quiz.completado.v1.json.

2. Build da imagem definida pelo Dockerfile da célula:

    docker build -t quiz-levantamento-local .

   Resultado: exit code 0, imagem criada com Python 3.12.14.

3. Prova de outbox, pontuação, telemetria, Redis real e contrato, no ambiente oficial da célula:

    docker run --rm --add-host host.docker.internal:host-gateway -e DJANGO_SECRET_KEY=prova-local -e DATABASE_URL=sqlite:///tmp/quiz.sqlite3 -e REDIS_STREAMS_URL=redis://host.docker.internal:6379/0 -e HUEY_REDIS_URL=redis://host.docker.internal:6379/1 -v <raiz-do-repositorio>:/workspace -w /workspace/services/quiz quiz-levantamento-local python -m pytest -q tests/test_inv_relay_outbox.py tests/test_inv_pontuacao_servidor_e_outbox.py tests/test_telemetria.py

   Resultado: 21 passed in 1.44s.

4. Tentativa no Python global da máquina:

    python -m pytest -q tests/test_inv_relay_outbox.py tests/test_inv_pontuacao_servidor_e_outbox.py tests/test_telemetria.py

   Resultado: coleta inicial sem django e redis; depois da instalação temporária, 15 passed e 6 failed por incompatibilidade de renderização entre Django 5.1.4 e Python 3.14, com erro Context.__copy__. A prova final foi repetida no Dockerfile oficial e passou integralmente.
