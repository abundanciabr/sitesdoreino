---
schema_version: 2
armadilha: 509
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: distinguir "o commit do trabalho chegou ao remoto" de "so o commit de anuncio de sessao chegou" exige comparar o worktree local com o ramo remoto no momento do pouso; as muralhas medem o diff que existe, e um diff vazio nao tem o que reprovar.
sinal:
  - "\"files\":\\s*\\[\\]"
gatilho:
  - ci/mergear.py
  - ci/pr.py
licao: "Checks verdes nao provam que o PR tem conteudo: um diff vazio passa em tudo. Antes de gh pr ready, confira gh api .../pulls/<N>/files -q '.[].filename'. gh pr view --json files pode devolver vazio sem erro. Gatilho: subagente relata um commit que ficou so no worktree, sem push."
---

# 509: checks verdes não provam que o PR tem conteúdo

**Data:** 21/09/2026 · **Onde:** `ci/mergear.py`, `gh pr ready` · **Custo
evitado:** um PR inteiro (TAR-595) integrado vazio, tendo que ser refeito num
segundo PR.

## Sintoma

O PR #1859 ("rascunho: ligar-a-appmax") tinha os 8 checks obrigatórios verdes.
A maestro rodou `gh pr ready 1859`, viu o semáforo verde e deixou a integração
automática pousar. O merge entrou limpo:

```
$ gh pr view 1859 --json state,mergedBy,mergeCommit
{"mergeCommit":{"oid":"d78fcc183cba85c74c6cb64f6b4c98e8edec64ef"},"mergedBy":{"login":"abundanciabr"},"state":"MERGED"}
$ gh api repos/abundanciabr/sitesdoreino/pulls/1859/files -q '.[].filename'
$
```

A segunda chamada não devolveu nenhuma linha. O ramo `agent/infra/ligar-a-appmax`
só tinha o commit de anúncio de sessão; o commit com `infra/ligar-a-appmax.sh` e
os testes existia apenas no worktree local do construtor e nunca foi empurrado.

## Causa

Cada muralha do pouso (`ci-celula-gate`, testes, portões de texto e de contrato)
mede o DIFF que chegou ao ramo. Um diff vazio não contém nada que viole
nenhuma regra, então toda muralha responde verde honestamente — elas não
verificam "este PR contém o trabalho que ele anuncia", só "o que está aqui
obedece a lei". `gh pr view --json state,mergedBy,mergeCommit` também não
acusa nada: o estado é `MERGED` de verdade, o merge commit existe de verdade.
Só a lista de arquivos do PR (`files`) denuncia o vazio, e ninguém a consultou
antes de tirar o rascunho.

## Solução

Antes de `gh pr ready` ou de qualquer decisão de pouso, confira a lista de
arquivos do PR pela API, não pelo estado dos checks:

```bash
gh api repos/abundanciabr/sitesdoreino/pulls/1859/files -q '.[].filename'
```

Lista vazia com PR fora de rascunho é o sinal de que o commit do trabalho
não chegou ao remoto. `gh pr view --json files` é insuficiente sozinho: ele
pode devolver `[]` sem nenhum código de erro, o que engana duas vezes quem
confia no campo errado.

O conserto aplicado foi levar o commit do worktree local para um ramo novo
(`agent/infra/ligar-a-appmax-de-verdade`) e abrir o PR #1866, que pousou com
os arquivos de verdade. Nada foi revertido na main porque o PR #1859 vazio
não alterou nada.

## Evidência

PR #1859 (merge `d78fcc183cba85c74c6cb64f6b4c98e8edec64ef`, zero arquivos por
`gh api .../pulls/1859/files`) e PR #1866 (merge
`c9a14a09d97f78a0735df4e32e5ca447d1737f53`, com `infra/ligar-a-appmax.sh` e
`ci/tests/test_ligar_a_appmax.py`), conferidos em 21/09/2026.
