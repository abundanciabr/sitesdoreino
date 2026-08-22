# LICOES.md — mensageria

Decisões e armadilhas específicas desta célula. Formato: `Decisão/Sintoma →
Causa/Razão → Solução`. O que vale para qualquer célula vai no `ARMADILHAS.md`
da raiz, não aqui.

## O handler do R4 recebe só `envelope["data"]` — sem `event_id`

**Contexto:** a receita R4 (`CAMINHO-DOURADO.md`) chama `handler(envelope["data"])`
dentro de `consume_eventos.py` — o `event_id` fica só no envelope, nunca chega ao
handler. A idempotência por `event_id` (INV desta célula: "reentrega ⇒ 1 envio")
acontece **inteiramente** na camada de fora, via `EventoProcessado.objects.create()`
(unique em `event_id`) — se isso falhar com `IntegrityError`, o handler nem roda.
**Decisão:** o handler usa uma SEGUNDA chave de idempotência, de negócio
(`order_id` + `tipo` + `canal`, unique em `EnvioRegistrado`), como defesa em
profundidade — cobre também o caso de uma task do Huey ser reexecutada e cair de
novo no handler. As duas camadas são independentes e a segunda não substitui a
primeira: se algum dia o `event_id` deixar de estar disponível fora do handler,
ainda assim não duplica envio.
**Origem:** Despacho mensageria/envios (R4+R8).

## Falha de provedor precisa estourar, não ser engolida

**Sintoma que teria acontecido:** se `processar_envio()` capturasse a exceção do
provedor e não relançasse, o `@huey.task(retries=5, retry_delay=30)` nunca saberia
que precisa reagendar — a task terminaria "com sucesso" tendo, na prática, falhado
silenciosamente.
**Solução:** `processar_envio()` registra a tentativa/erro no `EnvioRegistrado` e
depois **relança** (`raise`) — é a exceção escapando da função que o decorator do
Huey usa como sinal de retry. Ver `test_provedor_fora_do_ar_...` em
`tests/test_retry_provedor.py`, que prova isso (a exceção `ConnectionError`
precisa aparecer em `pytest.raises`, não ser engolida).
**Origem:** Despacho mensageria/envios (R8).

## Cobertura de teste do `consume_eventos.py` (o loop do Redis Stream em si)

**Corrigido em parte, e a parte que faltava escondia um bug.** O texto original
dizia que o arquivo "segue a receita R4 ao pé da letra e não tem teste automatizado
próprio", e que a garantia estava coberta pelas duas camadas abaixo. As duas camadas
existem e continuam válidas — mas **nenhuma delas alcançava a lógica de dedup dentro
do `handle()`**, e era exatamente lá que morava o descarte silencioso (ver a última
lição deste arquivo). Hoje `processar_envelope()` vive fora do `handle()` e é testada
direto, sem Redis: `test_inv_mensageria_evento_atomico.py`. O que continua sem teste é
só o loop `xreadgroup`/`xack` em si.

A garantia de "reentrega ⇒ 1 envio" está coberta em duas camadas testáveis sem Redis:

1. `EventoProcessado` — unicidade de `event_id` testada direto no modelo
   (`test_event_id_repetido_estoura_integridade`).
2. Os handlers — chamados 2x manualmente, testando o `get_or_create` por
   `order_id+tipo+canal` (`test_handler_chamado_duas_vezes_gera_um_unico_envio`).

Se uma sessão futura quiser um teste de integração do loop inteiro, `fakeredis`
(ou um Redis real via `docker compose -f docker-compose.dev.yml up -d redis`) é o
caminho — não existe ainda.

## Extensão pendente: template por site (`TEMPLATES_POR_SITE`)

`apps/eventos/handlers.py` já tem o ponto de extensão (`TEMPLATES_POR_SITE`, hoje
vazio) para customizar assunto/corpo por `site_id`, com fallback automático para o
template padrão da plataforma — satisfaz o invariante multissítio estruturalmente,
mas nenhum site pediu override ainda. Quando pedir, é só popular o dict (ou trocar
por uma tabela, se a lista crescer) — a função `_resolver_template()` já resolve
o fallback.

## Eventos ainda não consumidos: `pedido.criado.v1` e `quiz.completado.v1`

`constituicoes/AGENTS.mensageria.md` lista esses dois eventos na seção "Escuta",
mas o despacho desta sessão (mensageria/envios) pediu explicitamente só os três
do fluxo de pagamento: `pagamento.aprovado`, `pix.expirado`, `pagamento.recusado`.
Ficam de fora por escopo, não por esquecimento — próximo despacho.

## Dedup de evento e efeito do evento vivem na MESMA transação

**Onde:** `apps/eventos/management/commands/consume_eventos.py::processar_envelope()`.

**O bug (esteve em `main` até o PR desta lição):** o `create()` do `EventoProcessado`
rodava solto dentro do `handle()` — sem savepoint algum — e **commitava** antes de o
handler rodar. Se o handler falhasse por motivo transitório (SMTP fora, deadlock,
conexão caída), o evento já estava marcado como processado.

**Aqui isso era pior do que em `alunos` e `leads`, e a diferença importa:** o caminho de
dedup desta célula chama `r.xack(...)` antes do `continue`. Ou seja, a reentrega
descartada era **removida do stream** — não ficava na PEL, não sobrava nada para
recuperar depois. Nas outras duas células a mensagem ao menos sobreviveria a uma
recuperação futura via `xautoclaim`; aqui, não.

E há uma janela de falha parcial concreta: `ao_pagamento_aprovado()` chama
`_registrar_e_enfileirar()` **duas vezes** — e-mail e depois WhatsApp, cada um na sua
própria transação. Bastava a segunda falhar para o WhatsApp nunca mais ser enviado, com
o e-mail já entregue e o evento marcado como visto.

Demonstração crua contra o código anterior:

```
--- depois da falha ---
EventoProcessado gravado? True
--- depois da reentrega ---
processar_envelope devolveu: False -> handle() faz r.xack() e descarta
Envios registrados: 0
Chamadas ao provedor: 0
```

**A estrutura correta são duas transações aninhadas** — a externa envolvendo registro e
efeito, a interna sendo savepoint só em volta do `create()`. O detalhe que fecha o
raciocínio: **com o fix, o `xack` do dedup volta a ser seguro.** `False` agora só
acontece quando o efeito daquele evento realmente commitou alguma vez; antes, `False`
também significava "marcado mas nunca feito", e era nesse caso que o ack destruía a
mensagem.

**A armadilha da correção óbvia:** mover o handler para dentro do `try` faria um
`IntegrityError` vindo dele ser lido como "já processado". Não é hipótese — a constraint
`uniq_envio_por_order_tipo_canal` é disputada por `get_or_create()` sob corrida. O
guarda desse caso colide na constraint real.

**Por que a reentrega não duplica envio:** esta célula já tem a segunda camada de
idempotência por chave de negócio (`EnvioRegistrado`, por `order_id+tipo+canal`). A
transação externa entra sem risco de duplicata — a camada de negócio absorve o retry.
É por isso que "refazer o evento inteiro" é seguro aqui.

**Consequência no loop do Redis (sabida, não corrigida aqui):** com a exceção propagando
para fora de `processar_envelope()`, o `xack` não roda e a mensagem fica na PEL. É o
comportamento desejado, mas a recuperação de mensagens presas (`xautoclaim`) não existe
nesta célula — hoje depende de o processo reiniciar. Vale igual para `alunos` e `leads`.

**Origem:** varredura das quatro células que consomem eventos, depois dos mesmos
consertos em `alunos` (PR #43) e `leads` (PR #46). Três das quatro tinham o mesmo bug,
todas herdado da receita R4 — `checkout` escapou por não usar a tabela de dedup.

## Entrypoint oficial do worker: `python manage.py run_huey` (fecha o lado-célula do H10.2)

**Contexto:** até este despacho o worker de produção subia por um bootstrap de 6
linhas embutido no `command:` do compose (ARMADILHAS §4.11), porque `manage.py
run_huey` não existia. Agora existe: `huey.contrib.djhuey` está em INSTALLED_APPS
e o comando faz o `django.setup()` + `autodiscover_modules("tasks")` sozinho.

**As duas regras que mantêm isso funcionando:**
1. **`settings.HUEY` DEVE ser a MESMA instância de `config/huey.py`** (o settings
   importa `from config.huey import huey as HUEY`). O djhuey aceita uma instância
   pronta; se alguém trocar por um dict de config, nasce uma SEGUNDA fila — o
   handler enfileira numa, o worker escuta a outra, e nenhum e-mail sai, sem erro
   nenhum. Teste-guarda: `tests/test_entrypoint_huey.py` (os 3 testes reprovavam
   contra o código anterior — vermelho→verde real).
2. **`config/huey.py` não pode ser fail-hard no import.** Com djhuey instalado, o
   `settings.py` importa esse módulo — ou seja, o container WEB também passa por
   ali no boot. Por isso `HUEY_REDIS_URL` é lido com `os.environ.get(...)` e
   default inofensivo (o pool do redis-py é preguiçoso, nada conecta no import);
   produção define o valor real em `infra/env/mensageria.env`, compartilhado
   pelos três containers da célula. Trade-off assumido: o worker não morre mais
   no boot se a var faltar — ele apontaria para localhost e ficaria surdo; a
   guarda contra isso é o env de produção ser um arquivo só para web+worker
   (faltou para um, faltou para todos, e o web denuncia).

**Prova viva (22/08/2026, local, Redis efêmero):** `run_huey` logou
`+ apps.eventos.tasks.enviar_notificacao` sob `The following commands are
available:` (o sinal do §4.11), e uma task enfileirada pelo caminho real foi
executada — `EnvioRegistrado` saiu de `pendente` para `enviado`/`resultado=ok`.

**O que NÃO mudou aqui:** o `command:` do `mensageria-huey` no compose ainda é o
bootstrap antigo — a troca para `python manage.py run_huey` é escopo do despacho
de infra do mesmo lote. O bootstrap antigo continua funcionando com este código.

**Origem:** despacho mensageria/entrypoint-huey (H10.2).
