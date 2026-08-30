---
schema_version: 2
armadilha: 228
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o portão JÁ reprova as duas metades — `auditar_manifesto` recusa contrato em disco com a célula declarada `not-applicable`, e `checar_celula` recusa `required` sem exportador. O que não existe é um estado "congelado, implementação a caminho"; criá-lo seria mudar `ci/contract_freeze.py`, e a decisão de haver ou não esse terceiro estado é do mantenedor, não de uma sessão
sinal:
  - `Unknown command: 'export_openapi'`
  - "está declarada como 'not-applicable' mas contracts/<celula>.openapi.yaml existe"
  - `exportar contrato vivo de '<celula>': exit code 1`
---

# Congelar o contrato ANTES da porta de máquina trava o `make ci` da célula — e não existe estado intermediário no manifesto

**Sintoma.** Um plano de célula agenda o Rito de Contrato cedo (o contrato é PR 4
da escada) e a implementação da porta de máquina tarde (PR 16). O PR do contrato
acrescenta `contracts/<celula>.openapi.yaml` e vira a linha do manifesto para
`freeze: required`, como o plano manda. O PR fica verde — e o PRÓXIMO PR que
tocar `services/<celula>` morre no `make ci`:

```
  contrato/gamificacao  ERROR  exportar contrato vivo de 'gamificacao': exit code 1
  stderr (67 bytes):
    Unknown command: 'export_openapi'
```

**Causa.** O manifesto de contratos (`ci/manifesto-de-contratos.json`) tem
exatamente DOIS estados, e nenhum deles descreve "o contrato está congelado, a
implementação vem depois":

| estado | com o arquivo em `contracts/` | sem o arquivo |
|---|---|---|
| `not-applicable` | **ERROR** — contradição (`auditar_manifesto`) | SKIP declarado |
| `required` | roda o exportador da célula | ERROR |

Ou seja, assim que o `.openapi.yaml` entra em disco, a linha É OBRIGADA a virar
`required` — e `required` significa "existe um `manage.py export_openapi` nesta
célula que imprime o schema vivo". Antes do `config/api.py`, não existe.

O que confunde: **o PR do contrato passa**. `ci/ci.py --apenas muralhas` não roda
o freeze (só `--apenas freeze` roda), e o job `ci-celula` deriva as células do
diff — um PR que só toca `contracts/` + `ci/` não aciona célula nenhuma. A conta
chega no PR seguinte da célula, longe de quem a causou.

**Solução — a ordem que o fórum já provou.** A porta de máquina vem PRIMEIRO, o
congelamento depois:

1. PR na célula: `config/api.py` + o management command `export_openapi`
   (cópia do padrão de `identidade`/`forum` — Lei 3) + os testes de 401.
2. PR do Rito de Contrato: `contracts/<celula>.openapi.yaml` + o flip do
   manifesto para `required`, medido antes de abrir.

Foi literalmente isso que o fórum fez, e a mensagem do commit `6b76739` deixou
escrito: *"este PR só pode mergear DEPOIS do #552 (a porta de máquina) ... sem
eles o manifesto exigiria um freeze que não tem o que exportar, e a célula
ficaria ERROR no próximo PR dela."*

E a razão de a inversão não se resolver "juntando os dois PRs": **a cerca
proíbe** — `ci/cerca-de-celula.sh` recusa `contracts/` mudando junto com
`services/` (Rito de Contrato, RITOS.md §3). Um PR só nunca pode congelar e
implementar ao mesmo tempo. Por isso a ordem da escada não é detalhe de gosto:
ela é a única variável livre.

**Se você já congelou fora de ordem** (foi o caso da `gamificacao` em
30/08/2026, TAR-040): a linha do manifesto não pode voltar para
`not-applicable` — com o arquivo em disco isso é ERROR. O conserto é subir a
porta de máquina na fila, para que ela seja o próximo PR daquela célula. Até lá,
`make ci` da célula termina em ERROR no `contrato-check`, e isso bloqueia
qualquer PR que a toque.

**Como o plano errou sem ninguém perceber:** o §6 do
`PLANO-CELULA-GAMIFICACAO.md` colocou "contrato" no degrau 4 e "porta de
máquina" no degrau 16, e a gênese da célula repetiu a promessa em dois lugares
que hoje estão na `main` — o comentário do `Makefile` ("nasce `not-applicable` e
vira `required` no PR 4") e o `reason` do próprio manifesto. Três documentos
concordando entre si, e nenhum deles é o portão. **Concordância entre documentos
não é medição** (é a família do "falso-verde" da RETROSPECTIVA-FASE-D): quem
escreve uma escada de entrega que passa por `contracts/` roda
`python ci/contract_freeze.py <celula>` com o manifesto hipotético antes de
cravar a ordem — leva trinta segundos e é a única coisa que responde.

**Origem:** TAR-040 (Sessão B / Rito de Contrato da `gamificacao`), 30/08/2026,
ao medir o flip do manifesto antes de abrir o PR. Parente de `armadilhas/088` e
`armadilhas/076` — a mesma família: **célula nova exige registro em lugares que
o despacho dela não pode tocar, e o sintoma aparece longe de quem o causou.**
