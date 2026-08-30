# Workflow novo de `pull_request_target` NÃO roda no PR que o cria — e o silêncio parece "ainda vai rodar"

**Sintoma:** você acrescenta um workflow com gatilho `pull_request_target`, abre
o PR, e o check dele **não aparece em lugar nenhum**. Nenhum erro, nenhum run
cancelado, nenhuma linha vermelha — só ausência:

```
$ gh pr checks 574
ci-celula (admin)     pending
muralhas              pending
detectar              pass
painel-no-navegador   pending
```

Quatro checks, e o seu não está entre eles. A leitura natural — *"os outros
ainda estão pendentes, o meu deve estar na fila"* — está errada: ele nunca vai
aparecer, por mais que você espere. E esperar por um check que não existe é a
espera muda que a `armadilhas/161` já nomeou.

**Causa:** `pull_request_target` roda **a definição da branch base**, nunca a do
PR. É a mesma propriedade que o `.github/workflows/pouso.yml` documenta como
decisão de segurança (*"um PR não consegue alterar o juiz que vai julgá-lo"*) —
e ela tem um corolário que quase ninguém lembra na hora: enquanto o arquivo
existir **só** no ramo do PR, ele não existe para o GitHub. O gatilho procura o
workflow na `main`, não acha nada, e não há nada para reportar.

A assimetria é o que morde: um workflow novo de `pull_request` **roda** no PR
que o cria (ali o GitHub usa a definição do PR). Então a intuição construída
com `on: pull_request` — "abro o PR e vejo meu workflow rodando" — está certa
para um gatilho e errada para o outro, sem nada na tela distinguindo os casos.

**Solução — a prova vem da mão, e vem de fora:** um workflow assim só pode ser
provado ao vivo *depois* do merge. Antes dele, prove as duas metades separadas:

1. **a regra**, por teste sem rede (histórias montadas à mão), com evidência
   vermelho→verde de verdade — sabote o código de propósito e cole a saída crua
   do vermelho;
2. **o efeito real**, rodando o MESMO script que o workflow chama, à mão, contra
   o PR de verdade:

   ```bash
   python ci/conferencia_do_toca.py --pr 574 --comentar
   ```

   O comentário que aparece no PR é a prova de ponta a ponta. O que fica sem
   prova é uma linha só de YAML (o gatilho), e é honesto dizer isso no PR em vez
   de deixar implícito que tudo foi medido.

E **não anuncie no PR que "o check vai aparecer"** — ele não vai. Escreva que
este workflow começa a valer no PR SEGUINTE, senão a próxima sessão gasta uma
rodada procurando um run que nunca existiu.

**Onde mais isto morde:** qualquer gatilho que roda a definição da base —
`pull_request_target`, `workflow_run`, `schedule`, `workflow_dispatch`. Neste
repositório, quando esta entrada foi escrita: `pouso.yml` (`workflow_run`,
`pull_request_target`, `schedule`) e `conferencia-do-toca.yml`
(`pull_request_target`).

**Como foi achado:** TAR-015, 30/08/2026 — a conferência do `toca` declarado
contra o diff real (PR #574). O `gh pr checks` acima é a medição, não a
suposição: quatro checks no PR e nenhum deles o novo.
