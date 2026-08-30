---
schema_version: 2
armadilha: 213
estado: guardada
degrau: 3
confianca: estrutural
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_mira_do_alarme.py
sinal:
  - `Permission to .* denied to github-actions\[bot\]`
---

# O socorro automático mirava no commit da vez, e a única coisa que o impediu de acertar o inocente foi não ter permissão

**Sintoma.** Duas coisas que parecem separadas e são o mesmo incidente:

```
remote: Permission to abundanciabr/sitesdoreino.git denied to github-actions[bot].
fatal: unable to access 'https://github.com/...': The requested URL returned error: 403
##[error]Process completed with exit code 128.
```

...e, algumas linhas ACIMA disso no mesmo log, um commit de reversão já montado
contra um merge que não tinha nada a ver com a quebra.

**Medido em 30/08/2026.** O `alarme-main` concluiu `failure` **oito** vezes
seguidas, entre 12:13 e 12:31 UTC. O vermelho começou em `caaeb2e8` (PR #580);
as outras sete execuções eram merges sem relação nenhuma. Nas oito o job
`reverter` rodou, e nas oito ele preparou a reversão do commit **daquele push**.
Na execução `33311082356` (PR #585, a escrita do fórum) o diff local já estava
pronto quando o push bateu no 403:

```
15 files changed, 90 insertions(+), 1251 deletions(-)
 delete mode 100644 services/forum/tests/test_escrever.py
 delete mode 100644 services/forum/apps/forum/migrations/0002_pagina_publica_so_a_escola_fala.py
```

**Causa — dois defeitos que se escondiam um no outro:**

1. **A mira.** O job revertia `github.sha`. Isso só está certo quando a `main`
   acabou de ficar vermelha; numa `main` que **já estava** vermelha, cada merge
   novo herda o vermelho de quem quebrou e vira o réu. Pior: o ramo se chamava
   `reverter/${SHA:0:12}`, então a recusa "já existe PR de reversão" nunca
   casava — uma sequência de oito vermelhos abriria **oito** PRs, sete contra
   inocentes, todos etiquetados `pousar`, e a pista os mergearia sozinha.
2. **A permissão.** O `PISTA_TOKEN` ia para o `gh`, mas quem empurra o ramo é o
   `git`, com a credencial que o `actions/checkout` guardou — a do
   `GITHUB_TOKEN`, e o job declarava `permissions: contents: read`. **A cura
   automática nunca funcionou uma vez sequer, desde que foi escrita.**

O defeito 2 escondeu o defeito 1: enquanto o push morria em 403, ninguém via que
o alvo estava errado. Foi sorte, e sorte não é mecanismo — a única coisa entre a
automação e o apagamento do fórum era uma permissão faltando.

**Solução (30/08/2026, TAR-025).**

- `ci/mira_do_alarme.py` calcula o culpado do histórico do PRÓPRIO workflow: o
  commit da execução mais **antiga** da sequência vermelha que chega até agora,
  e essa sequência precisa começar logo depois de um `success`. Qualquer outra
  coisa — janela inteira vermelha, `cancelled` ou execução em andamento na
  fronteira, `main` já verde — é **RECUSA**, nunca um chute: fica sem cura
  automática, com a issue chamando gente. Exit 0 achou · 3 recusa fundamentada ·
  2 não consegui medir.
- A mira é provada com **históricos montados à mão**, inclusive o real deste
  incidente, sem rede (`ci/tests/test_mira_do_alarme.py`). Regredir a mira para
  o comportamento antigo derruba 9 testes, com `MIRA=86a5f59e` — o inocente —
  na saída.
- Efeito colateral que vale mais que o principal: com o ramo nomeado pelo
  CULPADO, as oito execuções calculam o mesmo nome e a recusa 3 as reduz a UM
  PR. **"Um PR por incidente" só passou a ser verdade agora.**
- `permissions: contents: write` no job. A escalada por job vale mesmo com o
  padrão do repositório em `read` (`default_workflow_permissions: read`) — este
  repositório já a exerce em três lugares que funcionam: `issues: write` (abriu
  a issue #587), `packages: write` (o `deploy-celula` publica no ghcr) e
  `pull-requests: write` (a `conferencia-do-toca` comenta).
- **O pouso automático virou condicional, e a condição é medida.** `PONTA=sim`
  (o culpado é o commit mais novo que o alarme viu) ⇒ etiqueta `pousar`:
  reverter é desfazer a última coisa, a operação mais segura que existe em Git.
  `PONTA=nao` ⇒ o PR nasce pronto, **sem** a etiqueta: outros merges já
  construíram por cima, e cirurgia no meio da história não se mergeia sem
  ninguém ter olhado. O trabalho caro fica feito de qualquer jeito, e quem
  olhar pede pouso com um comando — ninguém espera pelo mantenedor.

**A regra que fica, maior que o caso:** **automação que só falha em silêncio
nunca foi testada.** Um job que morre em 403 toda vez parece "não fez nada" e é
na verdade "fez a coisa errada e foi barrado por acidente". Quando um mecanismo
de emergência nunca disparou de verdade, ele não é uma garantia — é uma
hipótese; e a pergunta a fazer antes de dar permissão a ele é *"se isto tivesse
funcionado da primeira vez, o que teria acontecido?"*.

**Categoria** (`RETROSPECTIVA-FASE-D`): garantia sem mecanismo · falso-verde ·
fail-closed na borda. **Origem:** TAR-025, aberta a partir da `main` vermelha de
30/08/2026.
