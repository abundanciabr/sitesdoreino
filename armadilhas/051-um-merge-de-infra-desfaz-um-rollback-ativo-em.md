<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.16  ·  referencias antigas "ARMADILHAS §5.16" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.16 Um merge de `infra/` DESFAZ um rollback ativo — em silencio, sem alarme

**Sintoma (previsto, mecanico — ainda nao medido numa emergencia real):** voce
dispara o `rollback.yml`, a producao volta para a versao boa e o incidente para.
Minutos ou horas depois, alguem mergeia um PR que toca
`infra/docker-compose.yml` ou `infra/traefik/**` — e a celula **volta sozinha
para a versao quebrada**. Nenhum alarme dispara; o run do `deploy-infra` fica
VERDE, porque do ponto de vista dele nada falhou.
**Causa:** o pin do rollback e **efemero de proposito** (RITOS §4 item 3 —
"estado manual jamais persiste como fonte de verdade"): a variavel
`<CELULA>_TAG` e exportada so para aquele `docker compose up`. E
`.github/workflows/deploy-infra.yml` termina com `docker compose up -d` **sem
argumento nenhum**, sobre TODOS os servicos e sem a variavel. Cada servico volta
ao default `${<CELULA>_TAG:-main}` — que, durante um incidente, e exatamente a
versao que voce acabou de tirar do ar.
**Solucao (enquanto nao houver mecanismo):** enquanto um rollback estiver
ATIVO, trate `infra/` como congelado — nao mergeie PR que toque
`infra/docker-compose.yml`, `infra/traefik/**` ou `infra/sites.json` antes de a
correcao definitiva entrar por `deploy-celula`. Se um merge de infra acontecer
mesmo assim, **redispare o rollback** (`gh workflow run rollback.yml -f
celula=<X> -f alvo=<sha> -f motivo=...`): e idempotente e custa ~76s.
**Correcao definitiva (issue `mecanizar:`, ainda NAO feita):** duas saidas
plausiveis, ambas decisao de arquitetura — (a) persistir o pin num `.env` de
`/opt/plataforma/` que o compose le sozinho, e entao `deploy-celula` precisa
reprovar ALTO ao tentar deployar uma celula pinada (senao o pin vira armadilha
no sentido contrario: correcao que nao sobe); ou (b) `deploy-infra` passar a
listar servicos em vez de `up -d` pelado, preservando quem estiver fora do
`:main`. Nao escolher e a opcao pior: hoje a janela existe e nao esta guardada
por nada.
**Origem:** auditoria do proprio despacho de rollback (23/08/2026) — o despacho
documentou a efemeridade como virtude e nao sinalizou este lado dela.
