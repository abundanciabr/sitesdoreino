---
schema_version: 2
armadilha: 490
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - services/*/apps/core/management/commands/export_openapi.py
  - ci/contract_freeze.py
sinal:
  - "contracts/.*\\.openapi\\.ya?ml"
guarda:
  tipo: sino
  dono: ci/contract_freeze.py
  detector: revisão de código no exportador
licao: "Se o exportador de OpenAPI le o proprio contracts/<celula>.openapi.yaml para montar components.schemas, o freeze compara a saida com a fonte de que ela mesma derivou: nunca reprova. Guarda cuja medicao deriva do artefato que deveria conferir esta cego, mesmo dando PASS todo dia. schemas nascem do codigo, nunca do YAML congelado."
---

# O portão de contrato que lê o próprio congelado nunca reprova

**Data:** 18/09/2026 · **Onde:** `services/*/apps/core/management/commands/export_openapi.py`, `ci/contract_freeze.py` ·
**Custo evitado:** um guarda de contrato verde para sempre, sem guardar nada

## Sintoma

Uma célula com `components.schemas` no contrato congelado tem um exportador
que, para montar essa seção da saída, abre e lê o próprio
`contracts/<celula>.openapi.yaml` em vez de derivar os schemas do código
(models, serializers). O portão de freeze compara a saída do exportador com o
arquivo congelado e sempre dá PASS, célula muda o código real e o contrato
publicado, o teste continua verde.

## Causa

`ci/contract_freeze.py` mede divergência comparando a saída do exportador
vivo com o congelado. Essa comparação só tem poder de detectar mudança
quando as duas pontas nascem de fontes independentes: o congelado é o
registro histórico, e o vivo precisa nascer do código atual. Se o exportador
lê o congelado para montar parte da própria saída, uma das pontas foi
derivada da outra. A partir daí a diferença entre as duas é zero por
construção, não porque o contrato bateu: o guarda mede a si mesmo.

## Solução

Todo `export_openapi.py` de célula declara `components.schemas` lendo o
código vivo (classes de serializer, `Model._meta`, o que a célula já usa para
gerar o resto do schema), nunca abrindo `contracts/<celula>.openapi.yaml` ou
qualquer arquivo que o próprio freeze compare contra a saída. Ao revisar um
exportador novo ou mudado, pergunte: "se eu apagar o arquivo congelado, o
exportador ainda produz a mesma saída?" Se a resposta for não, o exportador
está lendo o que deveria estar sendo conferido, e o guarda está cego.

Esta lição é transversal: vale para qualquer guarda (não só OpenAPI) cuja
entrada de medição venha do mesmo artefato que ele deveria auditar. A metade
específica da célula `leads`, onde este padrão foi medido, está em
`services/leads/LICOES.md` (PR #1733).

## O que NÃO é a causa

Não é o `ci/contract_freeze.py` estar com bug de comparação: ele compara
exatamente o que recebe. O defeito nasce antes, na escolha de onde o
exportador busca `components.schemas`.
