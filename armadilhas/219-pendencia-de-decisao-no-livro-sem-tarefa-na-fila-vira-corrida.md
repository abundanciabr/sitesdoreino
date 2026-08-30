---
schema_version: 2
armadilha: 219
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: a caixa "precisa de você" é CALCULADA de painel/registros/ e não conversa com o balcão da fila — nada impede duas sessões de lerem a mesma pendência e as duas conduzirem a decisão com o mantenedor. A trava atômica que já existe (ci/reservar.py, usada por ci/fila.py pegar) só protege o que virou TAR. Mecanizar exigiria ou a pendência apontar uma TAR obrigatória, ou o próprio painel avisar "já reivindicada" — mudança em painel/logica.js + fila, por PR próprio.
sinal: null
---

# Pendência de decisão do dono registrada no livro SEM tarefa na fila vira corrida: dois robôs conduzem a MESMA sessão de decisão com o mantenedor, em paralelo

**Sintoma.** O mantenedor interrompe uma sessão no meio de uma rodada de
perguntas estruturadas com um "atenção — acho que isso já foi feito (ou está
sendo feito) por outro robô". Ao investigar (`gh pr list --search <tema>`,
`git branch -r`), aparece um PR aberto de OUTRA sessão registrando exatamente
a decisão que você está conduzindo agora — às vezes com as mesmas respostas,
porque o dono clicou nas duas caixas.

Medido em 30/08/2026, na gamificação: a sessão que escreveu o plano registrou
a pendência "falta a Sessão A de arquitetura" no livro (registro
`20260830-058`, `precisa_do_dono: true`) e, mais tarde na mesma conversa, o
dono respondeu "faz agora" — a sessão abriu a rodada de perguntas. Só que
OUTRA sessão já tinha visto a mesma pendência na caixa do painel, conduzido a
Sessão A inteira (7 decisões) e aberto o PR do registro (`#621`,
`20260830-061`). O dono respondeu as primeiras 4 perguntas em DUPLICATA — as
respostas até bateram, menos uma (o valor do quiz: 15 numa conversa, 10 na
outra), e foi preciso uma pergunta extra só para desempatar a divergência que
a corrida fabricou.

**Causa.** A caixa "precisa de você" do painel é uma VISTA calculada — ela
mostra a pendência para todo mundo e não tem conceito de "alguém já está
cuidando". A trava atômica da casa existe (`ci/reservar.py`, o balcão do
`ci/fila.py pegar`), mas só protege o que virou tarefa `TAR-NNN`. Uma
pendência de decisão que mora SÓ no livro é um convite aberto: qualquer
sessão (inclusive a própria que a registrou) pode "pegá-la" de memória — que
é exatamente o gesto que o RITOS §5 proíbe para trabalho comum ("tarefa se
pega no balcão, nunca de memória"). Decisão do mantenedor também é trabalho.

**Solução.**

1. **Antes de conduzir qualquer decisão pendente do livro, procure a corrida:**
   `gh pr list --state all --search "<tema>"` e `git branch -r | grep -i
   <tema>`. PR aberto ou ramo `agent/*` com o tema = outra sessão está na
   frente; recolha-se e deixe o registro dela valer (um fato mora num lugar
   só).
2. **Ao registrar uma pendência que exige CONDUÇÃO (uma sessão de decisão, um
   rito), crie junto a TAR correspondente** (`ci/fila.py criar` com
   `--despacho` apontando o registro) — e quem for conduzir REIVINDICA no
   balcão primeiro (`ci/fila.py pegar`). A pendência no livro continua sendo
   a vitrine para o dono; a TAR é a trava entre robôs.
3. **Se a corrida já aconteceu:** o registro que chegou primeiro ao livro (ou
   ao PR) vale; a outra sessão descarta as respostas duplicadas e, se houver
   divergência entre o que o dono respondeu nas duas caixas, UMA pergunta de
   desempate resolve — nunca as duas sessões seguirem, cada uma com a sua
   versão.

**Origem.** 30/08/2026, Sessão A da gamificação conduzida em duas sessões ao
mesmo tempo (registros `20260830-058`/`20260830-061`, PR #621). Custo: uma
rodada de decisões respondida em dobro pelo mantenedor e uma divergência
fabricada (quiz 15×10) que não existia.
