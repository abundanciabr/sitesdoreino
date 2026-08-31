---
schema_version: 2
armadilha: 251
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: ci/tests/test_pista_a_fila_anda.py::test_o_pr_que_a_pista_ATUALIZOU_pousa_na_MESMA_passagem
  motivo: roda o laço real do pouso.yml com dublês e afirma o desfecho — o PR atualizado pousa na mesma passagem
sinal:
  - `a base tinha envelhecido; atualizei este PR e devolvi para a fila`
---

# A pista reinicia o PR mais antigo a cada passagem, e ele nunca pousa

**Sintoma.** Você pediu pouso, tudo está verde, e horas depois o PR continua
aberto com a etiqueta `pousar`. No PR, o mesmo comentário repetido:

```
🛬 pista de pouso — a base tinha envelhecido; atualizei este PR e devolvi
   para a fila. A próxima passagem tenta de novo. Você não precisa fazer nada.
```

Medido em 31/08/2026: **nove** desses no mesmo PR, sem um único pouso. Outro PR
na mesma fila estava preso havia mais de uma hora. E nada ficava vermelho: a
pista continuava pousando OUTROS PRs, então a fila parecia andar.

**Causa — uma corrida que o PR não tem como vencer.** Três coisas verdadeiras ao
mesmo tempo:

1. a política estrita exige estar **em dia com a `main` no instante do merge**;
2. a pista, ao achar um PR atrasado, o **atualizava e o devolvia à fila** — e
   atualizar **reinicia os checks** (2 a 3 min na célula mais lenta);
3. num dia movimentado a `main` anda muito: **108 merges em uma hora** foi a
   medição do dia, ou seja, um a cada 33 segundos.

Nos 2 ou 3 minutos que os checks levam, a `main` andou 4 ou 5 vezes. O PR fica
velho de novo **antes** de ficar verde, e nunca alcança os dois estados ao mesmo
tempo. Pior: a fila é atendida **do mais antigo para o mais novo**, então a
pista reinicia justamente quem já esperava há mais tempo, enquanto PRs
recém-chegados (que ainda estão em dia) pousam por cima. É inanição clássica, e
ela se agrava sozinha conforme o dia fica movimentado.

O comentário dentro do próprio `pouso.yml` previa metade disto em 29/08/2026 —
"o mesmo PR podia envelhecer a cada passagem e segurar a fila indefinidamente".
A cura daquele dia (`continue` no lugar de `break`) resolveu **um PR travar os
outros**, e deixou de pé **o PR atualizado nunca chegar**.

**Solução — a pista não larga a vez de quem ela mesma acabou de atualizar.**
Depois do `gh pr update-branch`, ela **espera os checks daquele PR** e confere de
novo, na mesma volta, em vez de seguir para o próximo:

```bash
if ! gh pr update-branch "$alvo"; then ... continue; fi
esperas_restantes=$((esperas_restantes - 1))
if ! esperar_os_checks "$alvo" "$TETO_DA_ESPERA"; then continue; fi
# confere DE NOVO o MESMO PR, na mesma volta
```

Três limites que fazem parte da cura, e não são enfeite:

- **teto por espera** (`TETO_DA_ESPERA`), senão um check pendurado vira refém da
  passagem inteira — é a `armadilhas/161` aplicada aqui dentro;
- **orçamento por passagem** (`esperas_restantes=2`), senão cinco voltas lentas
  seguram o grupo de concorrência por meia hora;
- **fail-soft na leitura dos checks**: resposta que não é número (o GitHub ainda
  montando a lista, o `gh` mudando de formato) faz a espera desistir e seguir
  para a conferência, que é o juiz de verdade. Insistir ali daria a um enfeite o
  poder de travar a fila.

**A emenda é estreita de propósito.** A decisão 3 do cabeçalho do `pouso.yml`
("não espera os checks de um PR") continua valendo para todo o resto: a pista só
espera por um PR que **ela própria** acabou de atualizar, porque só nesse caso
ela é a causa da espera.

**Como saber se voltou:** o comentário do sintoma, repetido no mesmo PR. Um só é
normal (a `main` andou mesmo); três é a doença.
