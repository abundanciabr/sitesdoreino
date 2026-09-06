# A vacina do deploy confere se o commit chegou, não se a célula subiu — ancestralidade não é cobertura

**Sintoma.** Um `deploy-celula` é cancelado pela cadeira musical
(`armadilhas/188`). A vacina acorda sozinha, decide **não repetir**, e o
resumo do run sai verde. Dias, horas ou minutos depois, o código daquele
merge continua fora do ar, e nada mais vai avisar: três telas verdes na
frente do mantenedor, e a célula que ele acabou de mergear nunca chegou à
VPS.

Medido em 05-06/09/2026, com números reais:

```
PR #1145 (mensageria)  merge 00:27:27  sha 497f0cb9
  -> deploy-celula (run 34001330286): cancelled  (cadeira musical, armadilhas/188)
  -> vacina-do-deploy (run 34001432997): success, decidiu NÃO repetir

PR #1146 (admin/coortes)  sha 37b05b7c
  -> deploy-celula (run 34001431199): success — jobs: detectar, portao-de-deploy, deploy (admin)

PR #1147 (armadilhas)  sha 24aeb1c3
  -> deploy-celula (run 34001540532): success — jobs: detectar, portao-de-deploy, deploy (admin)

git merge-base --is-ancestor 497f0cb9 37b05b7c  ->  SIM, é ancestral
```

Os dois deploys posteriores carregam o commit da `mensageria` (a
ancestralidade é verdadeira) e terminaram verdes. Mas **nenhum dos dois tem
o job `deploy (mensageria)`** — só `deploy (admin)`, porque nenhum dos dois
commits tocou os `paths:` daquela célula. A `mensageria` do PR #1145 nunca
subiu, e a vacina achou que já tinha subido.

**Causa.** É legítima, e mora no desenho do `deploy-celula.yml`: as células a
construir num run saem de uma DETECÇÃO do diff (job `detectar`, via
`ci/ci.py --detectar-celulas --base "$BASE"`), que vira uma `matrix`. Célula
que o commit não tocou não entra na matrix, e está certo que não entre — não
faz sentido reconstruir as 16 células a cada merge.

O erro é da **vacina**, não do `deploy-celula`. `ci/rerun_de_deploy.py` (a
decisão que a `armadilhas/188` mecanizou na TAR-017) responde "preciso
repetir?" medindo só uma coisa: o SHA de algum deploy posterior é ancestral
do SHA cancelado? Se sim, ela conclui que "repetir só avançaria o que já está
publicado" e para por aí. Essa pergunta prova que o **código** chegou a algum
lugar; não prova que a **célula que o run cancelado ia construir** foi
construída em algum desses deploys posteriores. Ancestralidade de commit e
cobertura de célula são perguntas diferentes, e num monorepo de 16 células
com matrix dinâmica por diff elas quase nunca coincidem — só coincidem
quando, por acaso, algum deploy posterior toca os mesmos `paths:` da célula
cancelada.

**Esta é o furo da própria cura da `armadilhas/188`, não uma repetição
dela.** A 188 resolveu "cancelado sem SHA nenhum republicado depois" —
aquele caso em que a decisão certa é sempre repetir. O caso de hoje é mais
raro e mais enganoso: **houve**, sim, deploy posterior verde, com o SHA certo
por dentro, e mesmo assim a célula ficou de fora. É exatamente o cenário que
faz a vacina parecer ter funcionado.

**Diagnóstico que funciona, hoje, à mão** (não há mecanismo ainda — ver
`TAR-210`):

```bash
gh run view <id-do-deploy-posterior> --json jobs \
  --jq '.jobs[] | "\(.name): \(.conclusion)"'
# deploy verde que NÃO lista o job `deploy (<sua célula>)` não subiu a sua
# célula, mesmo carregando o seu commit por ancestralidade.
```

Só apareceu porque alguém foi olhar os JOBS de cada deploy em vez da cor do
resumo — a mesma disciplina que descobriu a `armadilhas/173`.

**Segunda metade do mesmo incidente, mesma entrada.** Redisparar à mão
(`gh run rerun 34001330286`) foi cancelado de novo em 31 segundos: o
`concurrency` do `deploy-celula.yml` é `group: deploy` com
`cancel-in-progress: false`, e o GitHub guarda **um** run pendente por grupo
— um terceiro que chegue expulsa quem esperava. Num dia de muitos merges,
redisparar no meio da fila é jogar o run direto de volta na cadeira musical
da 188. **Régua:** confira a esteira antes de redisparar
(`gh run list --workflow=deploy-celula.yml --json status`) e dispare só
quando não houver run em espera ou em execução.

**Solução (não construída aqui — `TAR-210`, caminho CODEOWNERS, sem
mandato).** A vacina precisa saber QUAIS células o run cancelado tinha na
matrix (o job `detectar` daquele mesmo run já sabe) e, para cada deploy
posterior candidato a ancestral, conferir se existe `deploy (<célula>)` com
`conclusion: success` para **cada uma** delas. Faltando uma célula, a decisão
continua sendo repetir, mesmo com o SHA já publicado por outro caminho. O
teste-guarda existe: reproduzir o cenário exato de hoje (cancelado da
`mensageria`, seguido de dois deploys verdes só de `admin`) e provar que a
vacina de hoje diz "não precisa repetir" (vermelho) e a vacina corrigida diz
"repetir" (verde).

**Origem.** 05-06/09/2026, maestro conferindo o desfecho do PR #1145 depois
do pouso automático, ao notar que o resumo verde da vacina não batia com o
que a `mensageria` deveria mostrar no ar. `git merge-base --is-ancestor` e a
listagem de jobs de cada run confirmaram o furo. **Categoria**
(`RETROSPECTIVA-FASE-D`): falso-verde (o mecanismo antifalso-verde participa
do falso-verde) · garantia sem mecanismo (a cobertura de célula não tinha
guarda nenhuma, só a leitura atenta dos jobs).

**Vizinhas.** `armadilhas/188` (a cadeira musical que a vacina cura — esta
entrada é o buraco que sobra depois da cura) · `armadilhas/173` (concorrência
expulsando o pendente) · `armadilhas/354` (o `--checks` do `ci/esperar.py`
recebe o número do PR, não uma contagem — outro caso de "o robô mediu a
coisa errada com um número plausível").
