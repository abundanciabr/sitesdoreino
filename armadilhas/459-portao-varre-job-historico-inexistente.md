---
schema_version: 2
armadilha: 459
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/estado_da_entrega.py
  - ci/mergear.py
  - .github/workflows/deploy-celula.yml
guarda:
  tipo: teste
  detector: ci/tests/test_estado_da_entrega.py
sinal:
  - "o portão expira após 300 segundos consultando jobs históricos"
  - "publicar-dados-admin não existe nas execuções antigas"
licao: A busca histórica não pode exigir um job criado depois do SHA que está sendo conferido. O workflow histórico do próprio SHA precisa decidir os jobs exigidos; caso contrário, o portão percorre todas as páginas antigas, não encontra o job novo e transforma uma prova válida em timeout.
---

# O portão procurou um job que ainda não existia

Em 09/09/2026, o portão do PR 1510 consultou dezenas de execuções do
`deploy-celula` porque exigia `publicar-dados-admin` em toda a história. Esse
job foi criado depois dos deploys antigos. A consulta do endpoint isolado
respondia, mas o conjunto de chamadas ultrapassava o limite de 300 segundos.

A busca agora localiza os deploys das células. Para cada SHA encontrado,
`consultar_publicacao` lê o workflow histórico e aplica somente os jobs que já
existiam naquele SHA. O teste-guarda reproduz uma página cheia de execuções
sem o job novo e exige uma única consulta de jobs.
