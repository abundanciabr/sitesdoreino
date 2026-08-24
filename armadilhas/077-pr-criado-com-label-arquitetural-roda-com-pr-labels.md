# PR criado JÁ com `--label arquitetural` mesmo assim reprova o orçamento: no log, `PR_LABELS:` vazio

**Sintoma:** você conta os arquivos antes, sabe que passou de 15, e abre o PR com a
label na mesma linha de comando:

```bash
gh pr create --label arquitetural --title ... --body-file ...
```

`gh pr view <N> --json labels` confirma que a label **está lá**. E o `muralhas`
reprova assim mesmo:

```
  orcamento-de-mudanca  FAIL   escopo estourou o orçamento de arquivos sem label 'arquitetural'
❌ ORÇAMENTO: 22 arquivos sem a label 'arquitetural'.
```

A prova de que não é o script errando está no cabeçalho do próprio step:

```
env:
  BASE_REF: origin/main
  PR_LABELS:            <-- vazio
```

**Causa:** `ci/orcamento-de-mudanca.sh` lê `PR_LABELS`, que
`.github/workflows/muralhas.yml` preenche com
`join(github.event.pull_request.labels.*.name, ',')` — ou seja, com o **payload do
evento**, congelado no instante em que o evento foi emitido. E `gh pr create --label`
não é atômico: cria o PR primeiro (dispara `opened`) e anexa a label depois. O
`opened` sai com `labels: []`, e é esse payload que o run inteiro enxerga.

É a mesma pedra que já se conhecia para "adicionar a label depois", só que ela morde
igual **quando a label vai no comando de criação** — a diferença de milissegundos não
salva ninguém.

**`gh run rerun` NÃO resolve:** o rerun reexecuta o mesmo run, com o **mesmo payload**
— `PR_LABELS` continua vazio. Rodar de novo mais vezes só gasta minuto de Actions.

**Solução:** force um evento **novo**, já com a label presente no PR. O `pull_request`
sem `types:` explícito escuta `opened`, `synchronize` e `reopened` — então qualquer um
destes dois serve:

```bash
# a) fechar e reabrir (dispara `reopened`; não perde comentário nem review)
gh pr close <N> && gh pr reopen <N>

# b) empurrar mais um commit (dispara `synchronize`) — só se você tiver o que commitar
git push
```

Confira que pegou lendo o env do step, não o veredito: no log do run novo tem de
aparecer `PR_LABELS: arquitetural`.

**A alternativa que NÃO se usa:** encolher o PR só para caber. Quando o escopo grande
é legítimo (gênese de célula, por exemplo — a `pagamentos` nasceu com 29 arquivos), o
rito é a label; fundir arquivos para caber no teto é pior que estourá-lo.

**Origem:** despacho EVO-10 (gênese da célula `sugestoes`), PR #108, 24/08/2026 — 22
arquivos, label anexada no `gh pr create`, `orcamento-de-mudanca` reprovado no
primeiro run e verde no run do `reopened`, sem uma linha de código mudar.
