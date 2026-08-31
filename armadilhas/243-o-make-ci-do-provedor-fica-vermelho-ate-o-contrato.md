---
schema_version: 2
armadilha: 243
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: nao ha o que mecanizar — o vermelho E o comportamento correto do portao; o que faltava era saber de antemao que ele viria, e isso e conhecimento, nao regra
sinal:
  - "FAIL seguranca/[a-z]+"
  - "congelado: <ausente>"
---

# O `make ci` do provedor fica VERMELHO até o contrato mergear, e isso é o portão funcionando

**Sintoma.** Você segue o Rito de Contrato à risca: PR 1 só com `contracts/`, PR 2
com o código da célula que implementa. Roda o `make ci` da célula no degrau 2 e
leva um FAIL que parece um defeito seu:

```
--- FAIL seguranca/catalogo ------------------------------------------
  GET /sites/{site_id}/menu
    congelado: <ausente>
    código:    exige credencial
  PUT /sites/{site_id}/menu
    congelado: <ausente>
    código:    exige credencial

RESULTADO  FAIL
```

**Causa.** O ramo do degrau 2 nasce de `origin/main`, e o contrato do degrau 1
ainda não mergeou: na árvore desse ramo, `contracts/<celula>.openapi.yaml` é o
ANTIGO. O freeze compara o que a célula EMITE com o que está no disco, e a
célula emite duas operações que o congelado não tem. O FAIL é literalmente o
portão dizendo a verdade.

**Solução: não é conserto, é ORDEM.** O degrau 2 só fica verde depois que o
degrau 1 entra na `main`. O caminho é este, e ele fecha em uma sessão:

1. Escreva o código do provedor primeiro, na sua bancada, e exporte o OpenAPI
   vivo (`python manage.py export_openapi`).
2. **Monte o contrato do PR 1 A PARTIR desse documento exportado**, nunca de
   cabeça: assim o congelado é, por construção, o que o código emite. Rode o
   freeze uma vez com os dois na mesma árvore e guarde a saída PASS.
3. Separe: PR 1 leva SÓ `contracts/` (com a label `contrato`); PR 2 leva SÓ o
   código, num ramo criado de `origin/main`.
4. Peça pouso do PR 1. Quando ele mergear, traga a `main` para dentro do ramo
   do PR 2 e o `make ci` fica verde sozinho.

**O que torna isso seguro, e é a metade que ninguém sabe de antemão:** um PR que
toca **só** `contracts/` não toca célula nenhuma (`celulas.yml` não lista
`contracts/` em `caminhos:` de ninguém). Logo o `ci-celula` é pulado, o
`ci-celula-gate` abençoa o pulo, e **o freeze não roda no PR 1** — ele não teria
como passar, já que o código ainda não existe. É por isso que a escada
provedor-depois-do-contrato passa pelos portões sem exceção e sem afrouxar nada.

**O que NÃO fazer:** juntar contrato e código no mesmo PR para ver verde. A
`ci/cerca-de-celula.sh` recusa (é o Rito de Contrato, RITOS.md §3), e a recusa
está certa: contrato é decisão do mantenedor via CODEOWNERS, código não.

**Origem.** Despacho do menu do topo do site (TAR-069, 31/08/2026), escada de
cinco PRs: #704 (contrato), #714 (catálogo), #710 (funil), #713 (admin), #722
(fórum). O FAIL acima é a saída real do degrau 2 antes de o #704 mergear; depois
dele, `contrato/catalogo PASS idêntico ao congelado (562 linhas comparadas)`.
