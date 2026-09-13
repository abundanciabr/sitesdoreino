---
schema_version: 2
armadilha: 462
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/espera.py
  - ci/estado_da_entrega.py
guarda:
  tipo: teste
  dono: ci/tests/test_espera_http.py
  detector: ci/tests/test_jobs_historicos_graphql.py
licao: Revalide o GET com ETag durante a espera, aceite o corpo guardado somente em HTTP 304 e respeite o prazo do limite. Nos lotes do histórico, consulte os jobs em GraphQL preservando identidade, tentativa, cobertura e ordenação.
---

# Consultar deploys consome a cota mesmo quando nada mudou

O laço consultava o mesmo endpoint a cada 15 segundos e repetia esse ritmo
após rate limit. A pista também consultava os jobs de até oito runs em paralelo
na varredura histórica. O limite era compartilhado com outros consumidores.

Em 10/09/2026, duas medições reais de `gh api --include`, uma por run e outra
pela lista de runs do SHA, confirmaram HTTP 200 seguido de HTTP 304 com
`If-None-Match`. O saldo principal permaneceu 4469 no primeiro par e 2422 no
segundo. **O gh saiu com código 1 no 304 legítimo**, acompanhado de `gh: HTTP 304`.
O leitor precisa interpretar os cabeçalhos antes de rejeitar esse caso.

A espera mantém cache apenas durante seu próprio laço. Cada leitura chega ao
GitHub; somente o 304 autoriza reaproveitar o JSON. Erro de transporte, acesso,
JSON ou 304 sem cache continuam sendo erro. Os prazos de Retry-After e reset,
o recuo exponencial secundário e o teto limitam as novas consultas, mantendo a
voz. O cache não elimina consumo de outros processos nem limites secundários.

O histórico preserva a primeira consulta REST, todas as páginas e a ordem por
instante, tentativa e ID. Só os lotes especulativos passam a GraphQL. Em prova
real com oito runs, uma consulta `nodes(ids: ...)` retornou oito identidades e
tentativas corretas, quatro jobs por run, sem página seguinte, com custo 1.
Isso reduz oito chamadas de jobs a uma, sem prometer a mesma redução no fluxo
inteiro. A consulta usa `checkType: LATEST`; IDs de check run não são IDs de job.

O código entregue também foi exercitado contra o GitHub: `vigiar/chamar_gh`
mediu 200/304 com saldo 4455 constante e `consultar_jobs_em_lote` conferiu os
oito runs. Os testes locais cobrem cache, falhas, prazo, tentativas divergentes,
resposta parcial e ordenação, incluindo rerun antigo na segunda página.

A comparação real também cobriu o run `34433902392`, tentativa 2: GraphQL
`LATEST` e REST `jobs?filter=latest` devolveram os mesmos cinco jobs, nomes,
estados e conclusões, sem truncamento. As 23 sabotagens das guardas reprovaram,
incluindo troca de conta no Windows e intervalo preservado em 304 sem cabeçalho.

Fontes: [requisições condicionais e limites](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api),
[ações GraphQL](https://docs.github.com/en/graphql/reference/actions) e
[checks GraphQL](https://docs.github.com/en/graphql/reference/checks).
