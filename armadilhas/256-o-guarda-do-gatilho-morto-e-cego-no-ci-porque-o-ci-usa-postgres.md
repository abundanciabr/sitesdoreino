---
schema_version: 2
armadilha: 256
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: é o achado em si — o detector da armadilhas/246 fica VERDE no CI, porque o modo de falha só existe em SQLite e o ci-celula.yml roda Postgres; um portão novo custaria mais que o dano, já que produção também é Postgres
---

# O guarda da `armadilhas/246` fica verde no CI, porque o CI roda Postgres

**Sintoma:** não há sintoma. É esse o problema.

Você escreve uma migration com `AlterField` numa tabela que tem gatilho
(a auditoria da célula `admin`, append-only pela `0001_initial`), **esquece** o
`RunPython(refazer_o_gatilho)` que a `armadilhas/246` manda pôr, e todos os
portões ficam verdes: `ci-celula` PASS, `muralhas` PASS, o PR pousa.

**Causa.** A `246` está certa e o detector dela também
(`services/admin/tests/test_liberar_e_recusar.py::test_a_auditoria_e_append_only_no_BANCO`,
que tenta um `UPDATE` de verdade e exige que o banco recuse). O que não casa são
os bancos:

| Banco | O que o `AlterField` faz | O teste pega? |
|---|---|---|
| SQLite (máquina de quem desenvolve, se o `DATABASE_URL` apontar para lá) | reconstrói a tabela e **os gatilhos morrem** | **sim** |
| Postgres (`ci-celula.yml`, e a produção) | `ALTER TABLE` preserva o gatilho | **não há o que pegar** |

Medido em 31/08/2026, na migration que virou a
`0013_verbo_de_corrigir_ideia`: com o `RunPython` REMOVIDO de propósito e
`DATABASE_URL` apontando para Postgres, `pytest -k append_only` deu
**`1 passed`**. O guarda não morde ali — e é no Postgres que todo PR desta casa
é medido.

**E não é hipótese: uma já passou.** A `0012_verbos_da_economia`, mergeada na
`main` horas antes desta entrada, faz um `AlterField` nesta mesma tabela **sem
o retoque**, e atravessou todos os portões. Quem rodar aquela migração em SQLite
fica com a auditoria adulterável, sem aviso nenhum. Não precisa de PR de
conserto: como o retoque **desinstala e instala de novo**, a primeira migração
seguinte que o traga (a `0013`) devolve o gatilho — mas isso é sorte de
calendário, não mecanismo, e é por isso que esta entrada existe.

**Por que isto NÃO é um portão faltando.** O dano real é limitado ao ambiente
local: produção é Postgres, e lá o gatilho sobrevive. Um portão que rodasse a
suíte inteira uma segunda vez em SQLite custaria minutos em todo PR para
proteger uma máquina de desenvolvimento. A escolha declarada é `guarda: nenhum`.

**O que fazer, então:** continue aplicando o retoque da `246` — ele é barato,
está no molde da `0011_verbos_de_arquivar_e_apagar` (que reusa as funções da
`0001_initial` em vez de copiar o SQL) e é o que mantém os dois bancos com o
mesmo comportamento. Só não conte com o CI para lembrar você: **aqui a lição
vale porque foi lida, não porque alguém a impõe** — é o vermelho honesto do B10,
e é a razão de esta entrada existir ao lado da `246` em vez de dentro dela.

**Relacionado:** `armadilhas/246` (o caso), `armadilhas/079` (append-only é
mecanismo, não disciplina), `docs/decisoes/RETROSPECTIVA-FASE-D.md` §2 (garantia
sem mecanismo).

**Origem:** despacho da correção de texto na Caixa (TAR-085, 31/08/2026), ao
aplicar o retoque da `246` numa migration nova e ir conferir se o CI teria
cobrado por ele.
