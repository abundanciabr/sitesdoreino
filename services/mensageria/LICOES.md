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

O arquivo `apps/eventos/management/commands/consume_eventos.py` segue a receita R4
ao pé da letra e **não tem teste automatizado próprio** — testar o loop `xreadgroup`
de verdade pediria um Redis real ou `fakeredis` (nenhum dos dois estava no
orçamento deste despacho). A garantia de "reentrega ⇒ 1 envio" está coberta em
duas camadas testáveis sem Redis:

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
