---
schema_version: 2
armadilha: 387
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão deste repositório impede uma sessão de assumir a bancada de outra. A notificação de "parou no limite de turnos" chega da mesma forma esteja o agente vivo ou morto, o `git status` sujo de uma bancada alheia não carrega etiqueta nenhuma dizendo "prova por mutação em voo", e nada no CI olha quem está escrevendo numa pasta enquanto ela é lida. O que existe é o gesto de três medições deste arquivo, feito por quem pensa em assumir uma bancada, antes de tocar nela
sinal:
  - stopped at its .* turn limit
  - esgotou os turnos
  - assumir a bancada
  - a tarefa tem dono vivo
  - git status sujo
---

# "Esgotou os turnos" é hipótese, não fato: meça antes de assumir a bancada de outro robô

**Data:** 07/09/2026 · **Onde:** a bancada de um sub-agente `despacho` na
célula `encomendas`, durante a rodada de prova por mutação do motor de oferta
· **Custo evitado:** a prova do `[INV-ENC-J5]` invalidada no meio da corrida,
o `test_ci_db` derrubado e recriado três vezes sob as medições do primeiro
robô, e um `git merge origin/main` forçado no ramo dele. Só não virou perda
real porque o segundo robô percebeu sozinho e parou antes de escrever.

## Sintoma

A maestro recebe uma notificação dizendo que um sub-agente parou no limite de
turnos ("stopped at its N-turn limit"), com resultado parcial. Ela despacha um
segundo robô para terminar o trabalho, na MESMA bancada e no MESMO ramo. O
primeiro robô estava vivo o tempo todo: o `ListAgents` mostrava `running` no
mesmo instante em que a maestro despachou o segundo, e essa informação já
estava na tela dela.

## Causa

**A notificação de "parou no limite de turnos" marca um ponto de parada do
laço, não a morte do agente.** Ele pode continuar depois daquele ponto. A
maestro leu a notificação como fato ("ele morreu") quando ela só é hipótese
("ele parou de falar agora"), e confiou nela em vez de medir o que o
`ListAgents` já mostrava na própria tela.

**O estrago, quando o segundo robô entrou na bancada do primeiro:**

1. Leu um `git status` sujo — o `motor.py` com uma linha comentada de
   propósito, no meio de uma rodada de prova por mutação do `[INV-ENC-J5]` —
   achou que era lixo esquecido e reverteu com `git checkout`, invalidando a
   prova que o primeiro robô estava correndo naquele instante.
2. Rodou `pytest` três vezes contra o mesmo banco de teste sem `--reuse-db`,
   derrubando e recriando o `test_ci_db` embaixo das medições em curso do
   primeiro robô.
3. Apagou os `__pycache__` durante a execução dele.
4. Fez `git merge origin/main` no ramo do primeiro robô.

Nada disso é malícia: é a leitura honesta de uma bancada que parecia
abandonada. O erro de raiz é ter pulado a medição.

**O corolário, que vale para qualquer robô:** `git status` sujo numa bancada
alheia pode ser prova por mutação em voo, não lixo esquecido. A pergunta certa
antes de reverter alguma coisa que você não escreveu é "quem escreveu isto, e
está escrevendo agora?" — nunca "isto parece esquecido".

## Solução

**Antes de assumir a bancada de outra sessão, prove que ela morreu. Não
presuma pela notificação.**

1. `ListAgents` — se o agente aparece `running`, ele está vivo. Ponto. Uma
   notificação de "parou no limite de turnos" não muda essa leitura.
2. O balcão da fila: `python ci/fila.py listar --ao-vivo` e o evento
   `*-reivindicada.json` da tarefa dizem QUEM a pegou. Se o dono não é você, a
   tarefa tem dono.
3. `git ls-remote origin 'refs/reservas/*'` mostra a reserva da bancada; o
   corpo dela traz `criado_em` e `expira_em`.
4. Só depois de medir as três, e só se as três apontarem para morte, assuma a
   bancada.

Isto não substitui a `armadilhas/355` ("o despacho que parece morto está
vivo, não redispare") nem a `armadilhas/357` (a trava do balcão tranca a
tarefa, não a pasta) — é a mesma família de erro, do lado de quem assumiria a
bancada em vez de quem redispararia o despacho. As três medições acima são o
gesto concreto que falta nas duas.
