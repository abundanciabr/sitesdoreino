---
schema_version: 2
armadilha: 202
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: ci/contrato_aditivo.py
sinal:
  - "passou a ser OBRIGAT[ÓO]RIO \\(quebra quem j[áa] envia sem ele\\)"
  - "contrato-aditivo *FAIL"
---

# Campo novo num contrato congelado nasce OBRIGATÓRIO por descuido — e o `contrato-aditivo` reprova o PR do Rito

**Sintoma.** Um PR de Rito de Contrato (RITOS.md §3) que só ACRESCENTA — nada
renomeado, nada removido — reprova no check `muralhas` com uma frase que fala
de remoção:

```
  contrato-aditivo      FAIL   a mudança de contrato REMOVE algo sem a etiqueta 'contrato-remocao'

--- FAIL quebras -----------------------------------------------------
  - contracts/<celula>.openapi.yaml: `<Componente>.<campo>` passou a ser
    OBRIGATÓRIO (quebra quem já envia sem ele)
```

Você olha o diff e não há um `-` sequer nas linhas que importam: o componente
ganhou uma propriedade e uma entrada em `required`. A palavra "REMOVE" no
resumo é o que atrasa o diagnóstico — o achado real está na seção de baixo, e
ele não é sobre remoção, é sobre **obrigatoriedade nova**.

**Causa.** `ci/contrato_aditivo.py` trata `required` como promessa ao
consumidor nos DOIS sentidos: campo que entra em `required` é uma exigência que
não existia, e quem já fala com aquela superfície não a cumpre. É a regra
expandir-e-contrair aplicada ao contrato inteiro, sem distinguir corpo de
requisição de corpo de resposta — e não distinguir é deliberado: o mesmo
componente pode aparecer nos dois lados amanhã, e a análise que decidisse "aqui
é resposta, então pode" precisaria estar certa para sempre.

E o campo nasce obrigatório **sem ninguém escolher isso**: num `ninja.Schema`,
`campo: list[X]` sem default é `required` no schema exportado. A anotação sem
valor padrão é a forma mais curta de escrever — então é a que sai primeiro.

**Solução: dê um default, e dê o default CERTO.**

```python
# ERRADO — nasce em `required`, e o portão reprova
changespecs: "list[ChangeSpecAssinado]"

# ERRADO de outro jeito — emite `"default": []` no schema (armadilhas/075)
changespecs: "list[ChangeSpecAssinado]" = []

# CERTO
from ninja import Field
changespecs: "list[ChangeSpecAssinado]" = Field(default_factory=list)
```

`default_factory` não emite a chave `"default"` no JSON Schema, então o
contrato exportado fica limpo — é a mesma cura que a `armadilhas/075` prescreve
para a outra metade do problema (lá o sintoma era o freeze reprovando por uma
chave `"default"` que o congelado não tinha; aqui é o aditivo reprovando por um
`required` que o congelado não tinha). **As duas mordem o mesmo gesto** —
"acrescentar um campo opcional" — em portões diferentes, e é fácil consertar uma
e levar a outra na volta seguinte.

**A pergunta de triagem, antes de escrever a anotação:** *"o consumidor de
ontem, que não conhece este campo, continua correto?"* Se sim, o campo é
opcional e o default expressa isso. Se não, não é campo novo: é mudança de
contrato que quebra, e aí o caminho é a etiqueta `contrato-remocao` com a
autorização explícita — nunca fazer o portão calar.

**Como conferir antes de gastar uma volta de CI** (o portão roda em segundos e
não precisa de banco):

```bash
BASE_REF=origin/main bash ci/contrato-aditivo.sh
```

**Origem:** TAR-023, 30/08/2026 — a 4ª emenda ao contrato da `sugestoes` (a
ficha do ChangeSpec assinado, PR #581). O freeze estava PASS, os 11 portões
locais estavam PASS, e o achado só apareceu no CI porque `contrato-aditivo`
compara contra `origin/main` — rodá-lo antes do push custaria 3 segundos.
