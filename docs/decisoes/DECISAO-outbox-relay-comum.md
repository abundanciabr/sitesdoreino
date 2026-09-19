# DECISAO: relay de outbox comum versionado por celula

Data: 2026-09-08

## Decisao

O mecanismo comum de publicacao de outbox fica no pacote Python
`outbox-relay`, com versao explicita por celula. O piloto adota a versao
`0.3.1` em `alunos` e `identidade`.

## Responsabilidade do pacote

O pacote seleciona os pendentes pela interface ORM ja existente, monta o
envelope protegido, publica em `eventos.<nome-do-evento>` via Redis Streams e
marca `published_at` somente depois do `xadd` confirmado pela biblioteca do
transporte. Em banco que oferece `SELECT ... FOR UPDATE SKIP LOCKED`, a selecao
dos pendentes acontece dentro de transacao e pula linhas ja travadas por outro
relay, para que dois workers nao publiquem o mesmo pendente em paralelo.

## Responsabilidade dos adaptadores locais

Cada celula continua dona do modelo, das migracoes, das transacoes de negocio,
da decisao de emitir eventos, da configuracao do Redis, do Huey e do
agendamento. O adaptador local informa ao pacote apenas modelo, URL, relogio e
tamanho do lote.

## Distribuicao e fixacao

A fonte canonica mora em `packages/outbox-relay`. A versao adotada viaja como
wheel em `services/<celula>/vendor/` e o `requirements.txt` da propria celula
aponta para a wheel `outbox_relay-0.3.1-py3-none-any.whl`. O Dockerfile copia
`vendor/` antes do `pip install` para que a imagem instale a mesma versao
declarada.

## Semantica de falha

Falha antes ou durante o transporte nao marca o evento. Falha depois de `xadd`
e antes do `save()` permite reentrega com o mesmo `event_id`. Reentrega e
idempotencia do efeito continuam sendo responsabilidade do consumidor da
celula que escuta o evento.

## Reversao

Uma celula reverte trocando sua linha fixada e sua wheel vendorizada, sem
alterar a outra. Eventos pendentes continuam na tabela local da celula e usam
o mesmo envelope logico.
