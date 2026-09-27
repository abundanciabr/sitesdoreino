---
schema_version: 2
armadilha: 547
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/mergear.py
sinal:
  - "BASE ATUALIZADA.*a main entrou no"
guarda:
  tipo: nenhum
  motivo: "o conserto de prioridade (dar a vez ao PR que ja levou update-branch duas vezes seguidas) muda o algoritmo de integrar_abertos; esta entrada so descreve o sintoma medido antes do conserto, ja em curso no PR 2266 (tarefa 891), fora do alcance de uma entrada de licao"
licao: "integrar_abertos so chama integrar() quando o PR NAO esta BEHIND; se estiver BEHIND com checks verdes, so pede update-branch e segue, nunca integra na mesma passada. Com a main mergeando a cada 6-7 min e checks de ~8 min, o PR nunca pega a janela MERGEABLE-e-verde ao mesmo tempo: volta a BEHIND antes. PRs 2229 e 2242 tiveram 4 ciclos verdes sem pousar."
---

# 547: a pista só integra quem não está BEHIND, e um PR com checks longos morre de fome

**Data:** 27/09/2026 · **Onde:** `ci/mergear.py::integrar_abertos`, PRs #2229
e #2242, obra Appmax · **Custo evitado:** achar que um PR verde e mergeável
está preso por acaso, quando o próprio algoritmo de prioridade nunca dá a
ele a janela para integrar.

## Sintoma

`ci/mergear.py::integrar_abertos` varre os PRs abertos ordenados por
`createdAt` e, para cada um, só chama `integrar()` (o passo que efetivamente
mergeia) quando ele **não** está `BEHIND`. Quando está `BEHIND` com
`mergeable == MERGEABLE` e os checks obrigatórios já verdes, a função só
dispara `update-branch` e segue (`continue`) — a integração fica para uma
próxima passada.

Com a `main` recebendo merge a cada 6 a 7 minutos e um PR cujos checks
obrigatórios (`ci-celula` de pagamentos ou checkout, mais admin) levam cerca
de 8 minutos para ficar verdes, o ciclo nunca fecha: assim que os checks
terminam, a `main` já andou de novo entre o início e o fim da rodada, então
na próxima varredura o PR volta a aparecer `BEHIND` e recebe outro
`update-branch`, reiniciando o relógio dos checks. Os PRs #2229 e #2242
passaram por quatro ciclos com checks obrigatórios verdes sem receber
nenhuma tentativa de `integrar()`.

## Causa

`integrar_abertos` (`ci/mergear.py`) trata "atualizar a base" e "integrar"
como dois ramos exclusivos da mesma passada: o `if BEHIND and MERGEABLE and
checks_obrigatorios_verdes(pr): update-branch; continue` sempre volta para o
próximo item da lista sem chamar `integrar()` neste PR na mesma rodada. Um
PR só chega a `integrar()` quando a leitura do momento já o mostra
não-`BEHIND`. Quanto mais lento o check obrigatório em relação à cadência de
merges da `main`, menor a chance de a leitura cair exatamente nessa janela.

## Solução

Não é conserto de leitura: é prioridade de fila. O PR #2266 (tarefa 891)
resolve dando prioridade, dentro da mesma varredura, ao PR que já recebeu
`update-branch` duas vezes seguidas sem conseguir integrar, para que ele
ganhe a próxima checagem antes de qualquer PR novo. Ao investigar um PR
verde que não pousa, confira quantas vezes seguidas ele recebeu "BASE
ATUALIZADA" no log da varredura antes de supor falha de rede ou de checks.

## Origem

PRs #2229 e #2242, obra Appmax, medição de 27/09/2026; conserto em #2266
(tarefa 891); `ci/mergear.py::integrar_abertos`.
