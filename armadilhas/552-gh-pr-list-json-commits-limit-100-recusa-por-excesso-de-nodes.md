---
schema_version: 2
armadilha: 552
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/metricas_da_fabrica.py
sinal:
  - "exceeds 500,000 nodes"
guarda:
  tipo: nenhum
  motivo: "e um limite do proprio backend GraphQL do GitHub, fora deste repositorio; nao ha portao local que troque a chamada por conta propria sem saber de antemao quantos commits o PR tem"
licao: "gh pr list --json commits --limit 100 e recusado pelo GitHub com 'exceeds 500,000 nodes' quando os PRs da pagina tem muitos commits somados (a API pede TODOS os commits de TODOS os PRs listados de uma vez). Para ler so a cauda de commits de UM PR, use gh api graphql com commits(last: N), nao gh pr list --json commits."
---

# 552: `gh pr list --json commits --limit 100` é recusado por exceder o limite de nós do GraphQL

**Data:** 27/09/2026 · **Onde:** uso de `gh` na obra Appmax · **Custo
evitado:** achar que o `gh` está com defeito ou que o PR é grande demais
para ser lido, quando o problema é pedir os commits de até 100 PRs na mesma
chamada.

## Sintoma

```
$ gh pr list --json commits --limit 100
GraphQL: Something went wrong while executing your query.
This may be the result of a timeout, or it could be a bug in our API.
Please include `xxxx` when reporting this issue. (This request exceeds
500,000 nodes; reduce the number of nodes requested.)
```

## Causa

`gh pr list --json commits` traduz para uma única consulta GraphQL que pede,
para CADA PR retornado pela listagem (até `--limit`), TODOS os seus
commits. O custo em "nós" do GraphQL cresce com o produto (PRs na página) ×
(commits por PR); numa listagem de até 100 PRs, um punhado de PRs com
histórico longo (rebases, merges de `main`, etc.) já é suficiente para
estourar o teto de 500.000 nós que o GitHub aplica a qualquer consulta,
independentemente de quota de rate limit. `ci/metricas_da_fabrica.py` já
evita isso por desenho: comenta o mesmo limite e trata `commits` como
amostra, nunca como total, exatamente por essa razão.

## Solução

Quando o que se precisa é a cauda de commits de UM PR específico, não peça
commits pela listagem: use `gh api graphql` direto, pedindo só os últimos N
commits daquele PR:

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $numero:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$numero) {
        commits(last: 20) {
          nodes { commit { oid messageHeadline } }
        }
      }
    }
  }' -F owner=abundanciabr -F repo=<repo> -F numero=<N>
```

Isso pede nós proporcionais a um PR só, não a toda a página listada.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026; uso de `gh pr list` e
`gh api graphql` durante a revisão de PRs.
