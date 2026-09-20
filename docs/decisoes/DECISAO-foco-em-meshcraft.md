# Só o meshcraft.top recebe trabalho novo

Decisão expressa do mantenedor em 19/09/2026: todo o trabalho deste repositório
é do site `meshcraft.top`. O site `basileiatoutheou.org` fica de lado, e nada
novo se constrói nem se altera nele além do que já existia nessa data. Ele
volta ao trabalho quando o mantenedor disser, sem data marcada.

## O que está congelado é o site, não a plataforma

Esta casa é multissítio: os dois domínios são servidos pelos MESMOS serviços, e
o conteúdo de cada site vive no banco, não no repositório. Congelado quer dizer
nenhuma página, nenhum conteúdo, nenhuma funcionalidade e nenhuma campanha para
`basileiatoutheou.org`. Conserto em código compartilhado continua valendo,
porque esse código é do `meshcraft.top` também.

## O que não está congelado, e por quê

A rota do webhook do Mercado Pago em `infra/traefik/dynamic/plataforma.yml` é a
única do sistema presa a um host, e o host é `basileiatoutheou.org`. O
`painel/mapa-do-site.json` registra o fato na porta `/api/pagamentos/`. Essa
rota é encanamento do pagamento do `meshcraft.top`, não conteúdo do site
congelado: ela continua manutenível. Tirá-la de lá é tarefa própria, avisada
antes, porque muda a URL cadastrada no Mercado Pago, que é serviço externo.

O golden `test_regressao_site_nao_registrado_landing_byte_identica`, em
`services/funil/tests/test_i18n_http.py`, compara byte a byte a landing dos
sites monolíngues, classe a que o domínio antigo pertence. Ele continua verde
sem esforço nenhum enquanto esta decisão for obedecida, e fica vermelho se
alguém mexer na renderização daquele site.

## Como isto se aplica a uma tarefa

Tarefa pedida para o domínio congelado não é executada. O agente registra a
recusa no livro de ocorrências e oferece o equivalente no `meshcraft.top`.
Referência a `basileiatoutheou.org` em documento antigo, como
`00-LEIA-PRIMEIRO.md` e `RUNBOOK-FASE-D.md`, é resíduo de molde e nunca
permissão.

## Por que esta lei entra na dívida em vez de ganhar portão

O que a lei proíbe é gasto de esforço, e o conteúdo do site congelado mora no
banco, fora do alcance de qualquer portão que leia o diff. Um portão que
reprovasse a palavra `basileiatoutheou.org` no diff não veria a única forma
provável de desobediência (publicar pelo editor) e reprovaria manutenção
legítima da rota de pagamento. Portão que erra nos dois sentidos ensina a
ignorar portão, então a dívida fica declarada em `ci/leis-sem-mecanismo.txt`,
com este motivo.

**Quem faz valer:** julgamento, com a dívida declarada em `ci/leis-sem-mecanismo.txt`.
