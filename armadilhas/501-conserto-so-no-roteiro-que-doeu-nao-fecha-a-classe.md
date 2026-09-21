---
schema_version: 2
armadilha: 501
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_paridade_das_chaves_do_gateway.py
sinal:
  - não consegui falar com o Docker Compose aqui
  - RAIZ: unbound variable
gatilho:
  - infra/semear-*.sh
  - infra/docker-compose.yml
  - ci/tests/test_paridade_das_chaves_do_gateway.py
licao: Consertar só o roteiro que doeu não fecha a classe. O Compose interpola o arquivo inteiro antes de qualquer subcomando: todo roteiro que rode `docker compose` em /opt/plataforma exporta ALUNOS_API_TOKEN e TOKEN_CATALOGO antes. Depois de três consertos avulsos o guarda varre `infra/semear-*.sh` por glob, e exige a linha `RAIZ=`, sem a qual o bloco morre em `unbound variable` com o teste verde.
---

# Conserto só no roteiro que doeu não fecha a classe

`infra/docker-compose.yml` exige `ALUNOS_API_TOKEN` e `TOKEN_CATALOGO` na forma
`${VAR:?mensagem}` desde `67ccf0ed` (15/09/2026). O Compose interpola o arquivo
INTEIRO antes de decidir qual subcomando rodar, e por isso um `docker compose
ps` inofensivo reprova em /opt/plataforma quando essas duas não estão no
ambiente, mesmo com a plataforma inteira no ar. A mensagem que aparece acusa o
Docker, e não a variável: o diagnóstico honesto custou uma noite em 19/09.

A casa consertou esse mesmo defeito TRÊS vezes, e nas três só no caminho que
doeu naquele dia:

- `8e1b6221` (17/09), `infra/deploy-celula-na-vps.sh`, depois de 2 dias e 6
  deploys vermelhos.
- `c0d75dd8` (19/09, TAR-486), `infra/reverter-celula-na-vps.sh`, depois de
  quatro smokes reais vermelhos. Nasceu daí o guarda de paridade.
- `98c0dffc` (20/09), `infra/semear-quiz.sh`, depois de dois disparos mortos
  em três segundos (runs 35479761568 e 35479784690).

Entre o segundo e o terceiro conserto, o guarda existia e estava verde. Ele
media DOIS arquivos por uma lista escrita à mão, e quem escreveu o quarto
chamador não tinha por que saber que precisava se acrescentar àquela lista.

## O que fecha a classe, e o que não fecha

Fecha: trocar a lista fixa por um glob. Desde a TAR-524
`ci/tests/test_paridade_das_chaves_do_gateway.py` varre `infra/semear-*.sh`, e
um semeador NOVO nasce reprovando enquanto não tiver o contrato. Ninguém
precisa lembrar de nada.

Não fecha: escrever mais um teste por arquivo consertado. Foi o que a casa fez
três vezes, e foi exatamente o que deixou a porta aberta na quarta.

## A cláusula que só apareceu na quarta vez

`_bloco_do_contrato` RECORTA o trecho do roteiro de verdade e injeta, na frente
dele, a linha `RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"`. A injeção é
necessária para apontar o teste a um diretório de mentira, mas ela esconde um
buraco: um roteiro que abra `$RAIZ/env/admin.env` sem nunca definir `RAIZ` roda
VERDE aqui e morre na VPS com `RAIZ: unbound variable`, porque os roteiros
todos usam `set -u`. Os seis semeadores estavam nesse estado: usavam `cd
/opt/plataforma` cru. Por isso o guarda ganhou a cláusula 5, que exige a
definição de `RAIZ` antes da leitura.

A lição geral: quando um teste PRECISA injetar contexto para rodar o trecho
recortado, ele deixa de medir aquele contexto. O que foi injetado vira o
próximo buraco, e precisa de cláusula própria.

## O que continua aberto, medido em 20/09/2026

Fora dos sete semeadores, outros **31** roteiros de `infra/*.sh` chamam
`docker compose` sem exportar as chaves. Medido assim, na raiz do repositório:

```bash
for f in infra/*.sh; do grep -qE '^[^#]*\bdocker compose\b' "$f" && ! grep -q ALUNOS_API_TOKEN "$f" && echo "$f"; done
```

Entre eles `provisionar-admin.sh`, `restaurar-backup.sh`,
`canario-fase-3-outbox.sh` e `conferir-as-fichas.sh`. Eles não entraram na
TAR-524 porque o mandato daquela entrega cobria os semeadores, e alargar
escopo sem mandato é outro pecado. Quem for tocar qualquer um deles: o bloco
está em `infra/semear-quiz.sh`, e o glob do guarda aceita ser ampliado para
`infra/*.sh` no dia em que os 31 tiverem o contrato.

## A categoria da retrospectiva

Consertar o sintoma no lugar onde ele apareceu. As três correções estavam
certas e nenhuma delas estava completa, porque nenhuma perguntou "quem mais faz
isto?". A pergunta tem resposta mecânica: um glob, um `git grep`, e o guarda
para de depender de memória humana.
