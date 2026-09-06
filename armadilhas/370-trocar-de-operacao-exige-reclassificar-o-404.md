---
schema_version: 2
armadilha: 370
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o significado de um 404 e semantica de contrato, e nenhum portao barato le semantica; o que cura e a pergunta feita ANTES de trocar
sinal:
  - "404 .*aluno inexistente"
  - "categoria_de"
---

# 404 é resposta numa operação e falha na vizinha: trocar de porta exige reclassificá-lo antes de tudo

**Sintoma.** Um consumidor deixa de perguntar por uma operação e passa a perguntar
por outra da MESMA célula, porque precisa de um campo a mais. O código do
tratamento de erro viaja junto, sem ninguém reler. Aí ou todo mundo perde acesso,
ou todo mundo ganha — e nos dois casos em silêncio.

**Causa.** Duas operações vizinhas podem dar significados OPOSTOS ao mesmo código
HTTP, e as duas estarem certas no contexto delas. Medido em
`contracts/alunos.openapi.yaml`, 06/09/2026:

| operação | 404 significa |
|---|---|
| `getStudentStanding` (`/alunos/{email}/situacao`) | **não existe**: a porta responde `200 cadastrado` para quem ela não conhece, e o contrato diz por escrito que 404 aqui obrigaria cada consumidor a traduzir "erro" em "cadastrado" por conta própria |
| `listEnrollments` (`/alunos/{email}/matriculas`) | **RESPOSTA legítima**: "esta pessoa não tem matrícula nenhuma", que é exatamente o que quem pergunta precisa saber |

Quem troca a primeira pela segunda e mantém o `except` de antes trata "não tem
matrícula" como "não consegui perguntar". Numa porta fail-closed, isso fecha a
casa para quem tinha direito de entrar; numa fail-open, abre para quem não tinha.

**Solução: reclassifique o 404 ANTES de escrever qualquer outra linha.** Ao
trocar de operação, releia o `description` da nova no contrato congelado (é
pedra, e é lá que o significado está escrito) e responda em voz alta: *neste
lugar, 404 é um FATO sobre o mundo ou um FRACASSO da pergunta?* Só depois mexa
no tratamento de erro. E escreva um teste para cada um dos dois: o 404 que é
resposta, e o erro de transporte que é falha.

**Por que isto não tem portão.** É semântica de contrato. Um guarda que exigisse
"trate 404" não distinguiria as duas leituras, e um que proibisse a troca
proibiria trabalho honesto. O que cura é a pergunta feita na hora certa.

**Origem.** Despacho da TAR-227 (06/09/2026, PR #1201): a sala de aula deixou de
perguntar `categoria_de` (a categoria da pessoa) e passou a perguntar
`matriculas_de` (a lista, que traz o produto), porque com dois cursos no ar
"é aluno" deixou de ser resposta suficiente. A sabotagem que trata o 404 como
falha derrubou 5 testes, todos na frase da recusa.
