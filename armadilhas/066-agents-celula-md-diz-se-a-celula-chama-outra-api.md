<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §7 — Coordenação (humano, painéis, outros agentes)
     ID historico: §7.5  ·  referencias antigas "ARMADILHAS §7.5" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 7.5 `AGENTS.<celula>.md` diz se a célula chama outra API — leia Fronteiras E Comunicação juntas

**Sintoma:** a receita genérica (`CAMINHO-DOURADO.md` §3, CONV-SITE) manda toda
célula pública chamar a API do catálogo para resolver Host→Site — mas seguir a
receita ao pé da letra, sem checar a constituição da célula, pode implementar uma
dependência de rede que a célula nunca deveria ter.
**Causa:** as duas seções de `AGENTS.<celula>.md` são redundantes de propósito:
toda vez que uma célula realmente consome a API de outra, isso aparece **nas duas**
— `Fronteiras → SOMENTE LEITURA` lista o `.openapi.yaml` da célula consumida, E
`Comunicação → Consome` nomeia a célula. Compare `AGENTS.checkout.md` (`SOMENTE
LEITURA: contracts/catalogo.openapi.yaml, contracts/pagamentos.openapi.yaml`;
`Consome: catalogo (ofertas/preços), pagamentos (intents)`) com `AGENTS.quiz.md`
(`SOMENTE LEITURA: contracts/eventos/quiz.completado.v1.json` — só isso; `Consome:
nada`). Ausência dos dois ao mesmo tempo não é esquecimento do autor do documento,
é a célula deliberadamente isolada — mesmo que a receita genérica a liste como
usuária de CONV-SITE.
**Solução:** antes de implementar qualquer chamada de rede a outra célula (mesmo
uma convenção "óbvia" como CONV-SITE), leia as duas seções de
`AGENTS.<sua-celula>.md` juntas. Se a constituição não autoriza (nem em Fronteiras
nem em Comunicação), a receita genérica não vale sozinha — é desvio consciente
(Lei 2 do `CAMINHO-DOURADO.md`: precisa de issue `arquitetura:`), não improviso.
No caso do quiz, a solução foi um cadastro `Site` **local** à célula (seedado via
R9), em vez do `CatalogoClient` que a receita sugere — ver
`services/quiz/LICOES.md` para o raciocínio completo e o alerta para o mantenedor
revisar essa leitura.
**Origem:** despacho do quiz (PR do Crivo), ao decidir a resolução de site.
