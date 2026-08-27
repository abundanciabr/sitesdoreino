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

## `site_id` é obrigatório em toda rota — decisão do mantenedor, 27/08/2026

A Fase 4 nasceu (Rito de Contrato de 27/08/2026, PR #274) com as três rotas
recebendo só `destinatario_id` — nenhuma tinha `site_id`. Isso durou poucas
horas: ao ver a implementação em andamento, o mantenedor decidiu (pergunta
estruturada, opção recomendada) que **"cada site mostra só os avisos que
vieram dele"** — nunca um apanhado de todo site que a pessoa já tiver
tocado. É a Lei 9 da CONSTITUICAO ("`site_id` acompanha toda entidade
pública") aplicada também à LEITURA, não só à escrita — que já cumpria a Lei
9 desde a gênese (toda `Notificacao`/`ContadorDeNaoLidos` sempre gravou o
site de origem). O contrato foi emendado por Rito próprio (PR #282, só
`contracts/`, label `contrato`) ANTES da implementação da Fase 4 mergear:
`site_id` virou parâmetro obrigatório em `/resumo`/`/avisos` e campo
obrigatório no corpo de `/marcar-lidas`.

**Consequência prática:** toda função de `consultas.py`/`services.py` recebe
`site_id` E `destinatario_id`, e filtra pelas duas — nunca só uma.
`marcar_todas_como_lidas` até SIMPLIFICOU com a mudança: como `(site_id,
destinatario_id)` é a chave única de `ContadorDeNaoLidos`, no máximo UMA
linha do contador pode casar por chamada, então o `GROUP BY site_id` que essa
função teve por poucas horas (de quando só existia `destinatario_id`) deixou
de fazer sentido e foi removido. Os índices tiveram que mudar junto — ver a
seção seguinte.

## Índice "óbvio" pode estar errado — meça com EXPLAIN, não suponha

A migração `0002_indices_da_porta_de_consulta` liderou os índices de
`Notificacao`/`NotificacaoArquivada` só por `destinatario_id`, apostando
(certo, NA HORA) que a Fase 4 não filtraria por `site_id`. A aposta durou até
a emenda da seção acima — e a partir dali o índice deixou de casar com a
consulta real, **sem que nenhum teste existente notasse**: com o volume de
dados de teste de costume (poucas dezenas de linhas), o Postgres troca de
plano sem custo perceptível, e `assertNumQueries` (`tests/test_api.py`, seção
CUSTO) mede QUANTAS consultas, não QUANTAS LINHAS cada uma lê por dentro.

A prova que pegou isso foi `EXPLAIN ANALYZE` com dado SEMEADO DE PROPÓSITO
para expor a diferença — uma pessoa com linhas em 5 sites (1.500 linhas, 300
no site pedido) mais 500 pessoas de ruído no site pedido. Sem esse volume E
essa distribuição, os dois índices (o errado e o certo) têm o MESMO plano,
porque tabela pequena não sente a diferença — é fácil "confirmar" um índice
rodando `make ci` e ele parecer certo mesmo estando errado. A migração
`0003_indices_corrigidos_para_site_id_obrigatorio` tem a medição completa
(os números de `Rows Removed by Filter`, antes e depois) no comentário de
topo; `tests/test_indices_da_porta_de_consulta.py` mantém essa medição viva
como guarda automático — falha se o plano voltar a descartar linha depois do
índice.

**A mesma investigação também provou o oposto para outra tabela — e vale
saber os dois lados.** O índice extra que a 0002 tinha acrescentado em
`ContadorDeNaoLidos` (`contador_por_pessoa`, só `destinatario_id`) nunca foi
necessário: o `UniqueConstraint contador_um_por_pessoa` **da gênese**
(`site_id`, `destinatario_id`, PR #248) já era, sozinho, o índice ideal para
a pergunta que `/resumo` faz — o Postgres o escolhe direto, sem descartar
linha nenhuma. "Adicionar um índice para garantir" também é uma suposição, e
também precisa ser medida: às vezes a resposta é "não, o que já existe
serve", e um índice a mais que o planejador nunca escolhe só custa em todo
`INSERT`, para sempre, sem benefício nenhum. O índice extra foi removido na
`0003`.

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
