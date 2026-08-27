# LIÇÕES — célula `notificacoes`

O que já custou tempo *dentro desta célula*. O que vale para qualquer célula
mora em `armadilhas/` (leia o `INDICE.md` e abra só a entrada que casa com a
sua tarefa).

## Esta célula é BURRA de propósito — não conserte isso

Ela não faz leque, não pergunta nada a ninguém e não decide quem deve ser
avisado. Uma carta que chega no fio já vem endereçada a UMA pessoa, e vira UMA
linha. Se você se pegar escrevendo aqui um laço sobre votantes, uma chamada HTTP
para a Caixa, ou uma regra do tipo "quem comentou também recebe" — pare: isso é
da célula que PUBLICA, e foi decidido assim pelo mantenedor no Rito de Contrato
de 26/08/2026 (`docs/decisoes/DECISAO-fase-2-do-sininho.md` §1).

O ganho não é elegância: é que o custo por carta não muda quando dez células
estiverem publicando.

## A célula nasceu sem tela e sem contrato — e isso foi lei, não pendência

Até a Fase 4 (27/08/2026), `freeze: not-applicable` no
`ci/manifesto-de-contratos.json` e `config/urls.py` com uma rota só:
`tests/test_healthz.py` reprovava qualquer rota nova como fronteira fabricada
dentro de um despacho, porque consumir esta célula era Rito de Contrato
(RITOS §3), e o Rito ainda não tinha acontecido.

**Isso mudou no PR que trouxe este arquivo até aqui.** `freeze` virou
`required`, `contracts/notificacoes.openapi.yaml` existe, e a célula publica
`GET /resumo`, `GET /avisos` e `POST /marcar-lidas` sob `api/notificacoes/`
— ver as seções abaixo. O guarda de `test_healthz.py` **mudou junto** (mesmo
espírito da nota em `DECISAO-notificacoes` §2 sobre o guarda do `Aviso`
transacional): ele agora prova que a célula publica EXATAMENTE o que o Rito
autorizou, nem uma rota a mais — o princípio (não fabricar fronteira fora do
Rito) sobreviveu; só o que ele mede mudou.

## A porta de consulta (Fase 4): `openapi_extra` à mão, nunca `response=Schema`

`apps/core/api.py` declara as três rotas com handlers que recebem `request`
puro e devolvem `JsonResponse` — nenhuma delas usa `ninja.Schema` tipado com
`response=`. Não é estilo, é o formato do CONTRATO: `contracts/notificacoes.openapi.yaml`
não tem `components.schemas` — toda forma é inline nos paths (padrão de
`alunos`/`leads`). `response=MinhaSchema` faz o django-ninja criar um
componente NOMEADO com `$ref` — a primeira tentativa desta célula usou isso e
o `contrato-check` reprovou na hora (`$ref: '#/components/schemas/...'` onde o
congelado tem o objeto inline). `catalogo` é o contra-exemplo: o contrato DELE
tem `components.schemas` (`Site`/`Offer`/`Product`), então lá `response=Schema`
é o padrão certo. **Antes de copiar o padrão de outra célula, confira se o
contrato dela tem `components.schemas` ou tudo inline** — as duas formas
convivem na plataforma, e usar a errada só aparece rodando `contrato-check`.

## `/avisos` lê DUAS tabelas — `Notificacao` E `NotificacaoArquivada`

O arquivamento move o lido-e-velho para fora do caminho quente, mas
`NotificacaoArquivada` existe (em vez de simplesmente apagar a linha)
justamente para que "nada se perde: o histórico continua consultável"
(`DECISAO-notificacoes` §5.2, docstring do model). `/avisos` é a ÚNICA porta
de consulta que a Fase 4 abriu — se ela lesse só a tabela quente, um aviso
lido sumiria da vida da pessoa 30 dias depois de ela o ter lido. O merge das
duas fontes (cursor opaco que codifica tabela+id, para não colidir PKs de
sequências independentes) está em `apps/notificacoes/consultas.py`, com o
raciocínio completo no docstring do módulo. Continua O(1): sempre duas
consultas com `LIMIT`, nunca uma por tabela extra que nascer.

## `site_id` no contrato de leitura — dívida anotada, não bug

`contracts/notificacoes.openapi.yaml` **não tem `site_id` em rota nenhuma** —
as três operações só recebem `destinatario_id`, sempre descrito como "Id da
PLATAFORMA da pessoa" (nunca "do site"). Isso tensiona com a Lei 9 da
`CONSTITUICAO.md` ("`site_id` acompanha toda entidade pública"), que continua
cumprida do lado da ESCRITA — toda `Notificacao`/`ContadorDeNaoLidos` grava o
site de origem — mas não tem como ser respeitada do lado da LEITURA sem um
parâmetro que o contrato congelado simplesmente não desenhou.

A implementação escolhida (Fase 4, PR desta entrada) é a única compatível com
o contrato como está: `resumo_de_nao_lidos`/`pagina_de_avisos`/
`marcar_todas_como_lidas` filtram só por `destinatario_id`, somando/percorrendo
qualquer `site_id` que a pessoa já tiver tocado (hoje, sempre um só — um site
em produção). **Isto não é uma correção que uma sessão futura deve aplicar por
conta própria**: mudar o formato de `/resumo`/`/avisos`/`/marcar-lidas` para
exigir `site_id` é mudança de CONTRATO (RITOS §3, sessão com o mantenedor) —
o mesmo caminho que abriu a Fase 4. Fica registrado aqui para não virar
"esqueceram do site_id" na leitura de alguém que não viu esta conversa.

## Rodar os testes desta célula, do zero

## O contador é uma CÓPIA, e cópia diverge

`ContadorDeNaoLidos` existe porque o sino aparece em toda página e `COUNT(*)`
numa tabela que só cresce fica lento exatamente quando o produto der certo
(`DECISAO-notificacoes` §5.2). O preço é um modo de falha que a versão lenta não
tinha: o número na tela deixar de bater com a caixa.

Duas regras que não são estilo:

1. **A linha e o contador nascem na mesma transação.** Um contador somado "logo
   depois" diverge no primeiro erro de rede e nunca mais volta sozinho.
2. **`F("nao_lidos") + 1`, nunca ler-somar-gravar.** Duas cartas chegando ao
   mesmo tempo para a mesma pessoa leriam o mesmo valor e gravariam o mesmo
   `+1`; uma das somas se perderia, sem erro nenhum.

Guarda das duas: `tests/test_inv_contador_bate_com_a_tabela.py`.

## O `ator_id` vem do ENVELOPE, não do `data`

É a única adaptação desta célula à receita R4 v1, e está declarada no ponto de
chamada de `consume_eventos.py` em vez de escondida. O Rito de Contrato pôs o
`ator_id` no nível de cima do envelope de propósito: assim qualquer célula lê
"quem fez isto" sem conhecer o formato do assunto. Um handler que só recebesse
`data` obrigaria o `ator_id` a descer para dentro de cada assunto — o desenho
que o rito recusou.

Use `.get("ator_id")`, nunca `[...]`: o contrato declara o campo **nulável**
(fato de máquina não tem gente), e estourar ali trocaria "não havia ator" por "a
célula caiu".

## Arquivar é mover de tabela, e nunca toca no contador

`NotificacaoArquivada` é tabela separada, não uma coluna `arquivada`: uma coluna
deixaria as linhas velhas engordando o índice que a página do sino percorre em
toda visita. E `arquivar_lidas()` **não** mexe no contador — quem sai da conta é
o LIDO, no momento da leitura. Se o arquivamento descontasse também, descontaria
duas vezes, e um contador que anda sozinho para baixo some com avisos da cara da
pessoa sem nada indicando o que houve.

## Rodar os testes desta célula, do zero

```bash
docker run -d --rm --name notif-pg-dev -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=notificacoes_db -p 55450:5432 postgres:17
cd services/notificacoes
DATABASE_URL=postgres://dev:dev@localhost:55450/notificacoes_db \
REDIS_STREAMS_URL=redis://localhost:6379/0 DJANGO_SECRET_KEY=ci python -m pytest -q
```

Os guardas do consumidor **não** precisam de Redis: eles chamam
`processar_envelope()` direto, que é onde mora a decisão. Redis de verdade só
faria a suíte demorar e falhar por motivo alheio.
