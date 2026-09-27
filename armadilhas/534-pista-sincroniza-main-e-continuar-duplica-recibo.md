---
schema_version: 2
armadilha: 534
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/pr.py
  - painel/registros/*
sinal:
  - "Merge branch 'main' into"
guarda:
  tipo: nenhum
  motivo: "_registro_que_cita so dedup quando o diff entre o registro anterior e o HEAD atual fica dentro de painel/registros e fila/eventos da mesma tarefa; a pista trazendo commits de OUTROS PRs para dentro do ramo e o proprio motivo do diff sair desse conjunto, e ensinar a funcao a ignorar isso e mudanca de codigo, fora do alcance desta entrada"
licao: "A pista atualiza a base de ramos abertos com alta frequencia; cada sync muda a arvore e reinicia os checks. ci/pr.py --continuar chamado depois disso pode nao achar o registro anterior (arvore mudou) e escrever um SEGUNDO recibo para o mesmo fato (registros 100 e 105, mesmo PR 2156). Meca uma unica vez com ci/esperar.py; nao repita --continuar so porque os checks reiniciaram."
---

# 534: a pista sincroniza a main nos ramos abertos e `--continuar` pode gerar recibo duplicado

**Data:** 27/09/2026 · **Onde:** `ci/pr.py`, PR #2156 (TAR-795), obra
Appmax · **Custo evitado:** dois registros do livro para o mesmo fato,
exigindo remendo manual para não contar a entrega em dobro.

## Sintoma

`painel/registros/20260927-100-painel-decisoes-e-frentes-da-obra-appmax-tar-795.js`
e `painel/registros/20260927-105-painel-decisoes-e-frentes-da-obra-appmax-tar-795.js`
têm o mesmo título, o mesmo `tarefa: "TAR-795"` e citam o mesmo PR #2156,
diferindo só na "árvore" e no "commit" da evidência:

```
100: árvore 325c097f3e4c1f9e8b8a412576cb5063c32d34c7; commit 4512a9ac...
105: árvore d231c5175e590071d0619a7591b9f4f93a8643f0; commit a875091a...
```

Entre uma chamada de `ci/pr.py` e a próxima, a árvore do ramo mudou sem
nenhuma edição da sessão: foi a pista sincronizando a main no ramo aberto.

## Causa

`ci/pr.py::abrir` procura, antes de reservar um número novo, um registro que
já cite o mesmo PR **e** a mesma árvore (`_registro_que_cita(raiz, numero,
arvore)`). Se a árvore mudou, ele tenta um segundo caminho: acha um
registro que cite o PR com QUALQUER árvore e confere se o diff entre o
commit daquele registro antigo e o `HEAD` atual fica restrito ao próprio
arquivo de registro e aos eventos da fila da mesma tarefa
(`diferenca - permitidos`). A sincronização da pista traz para o ramo os
commits de main que aconteceram nesse intervalo — inclusive de outros PRs
já integrados — então o diff quase sempre extrapola esse conjunto
permitido, a dedup falha, e o código segue para reservar um número novo e
escrever um segundo recibo idêntico em conteúdo.

## Solução

Depois de abrir o PR com `ci/pr.py`, meça o desfecho **uma única vez**:

```bash
python ci/esperar.py --checks <N> --so-desfecho
python ci/esperar.py --entrega <N> --so-desfecho
```

Não chame `ci/pr.py --continuar` de novo só porque os checks reiniciaram
depois de uma sincronização da pista — isso é esperado (§2.5 do RITOS.md) e
não significa que a chamada anterior falhou. Se `--continuar` já gerou um
segundo registro para o mesmo fato, isso não se desfaz reescrevendo o
arquivo: registre a duplicidade em um registro `nota` novo, apontando para
qual dos dois é o fato original, e deixe ambos no histórico.

## Origem

PR #2156, TAR-795, obra Appmax, sessões de coordenação de 27/09/2026;
`ci/pr.py::abrir`, função `_registro_que_cita`.
