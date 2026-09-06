---
schema_version: 2
armadilha: 185
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/divida_do_livro.py
sinal:
  - `d[íi]vida do livro +FAIL`
  - `merge\(s\) sem registro`
gatilho:
  - painel/registros/*
licao: a `evidencia` do registro precisa CITAR o número do próprio PR (a URL completa dele), senão o portão de pouso reprova por dívida do livro e a conta cai na próxima sessão.
---

# O registro viajou dentro do PR, mas a evidência não cita o número — a dívida é REAL, e cai no colo da próxima sessão

**Sintoma.** `python ci/mergear.py <N> --conferir` (ou `--pousar`) reprova em
**"dívida do livro"** listando PRs que já foram mergeados **com registro
próprio dentro deles**. Você abre o registro, ele está lá, descreve a entrega
inteira — e mesmo assim o guarda cobra. Pior: quem paga a conta não é quem a
criou, é a **próxima** sessão que tentar mergear qualquer coisa.

**Causa.** `ci/divida_do_livro.py::numeros_citados()` procura o **número do
PR** dentro dos arquivos de `painel/registros/*.js` — a URL
`.../pull/<N>` ou a forma curta. Ele não lê o título, não infere pelo diff,
não sabe que aquele registro nasceu dentro daquele PR. **Sem o número escrito,
o registro não conta.**

E o número quase sempre falta pelo mesmo motivo inocente: **na hora de escrever
o registro, o PR ainda não existe.** O ciclo natural é escrever o registro →
commitar → abrir o PR — e nesse instante o número ainda não foi atribuído. O
autor então escreve `evidencia: null` ou uma prova longa e honesta que diz *"o
PR desta entrega"*, sem o número. O trabalho está todo lá; a contabilidade é
que fica furada.

Medido em 30/08/2026: dois merges da noite anterior (#537 e #538) apareceram
como dívida numa sessão que só tinha ido **atualizar o painel**. Os dois
levavam registro dentro do PR. Um tinha `evidencia: null`; o outro tinha uma
evidência de dez linhas, com medições reais — e a palavra "número" em lugar
nenhum.

**Não confunda com a `armadilhas/140`.** Lá a dívida era **falsa**: o guarda
lia `painel/registros/` de um checkout atrasado e não via o registro que já
existia. A pergunta de triagem é uma só:

```bash
git rev-parse HEAD; git rev-parse origin/main
```

Iguais (worktree recém-criado de `origin/main`)? Então a `140` está descartada
e **a dívida é real** — vá procurar o número, não o checkout.

**Solução — e ela muda a ORDEM do rito, não só o conteúdo:**

1. **Abra o PR primeiro, escreva o registro depois.** Commite o trabalho, faça
   `push`, abra o PR, leia o número que o `gh` devolve, e só então escreva o
   registro com `evidencia` citando
   `https://github.com/abundanciabr/sitesdoreino/pull/<N>`. Um segundo commit
   no mesmo ramo custa dez segundos; a dívida custa o merge da sessão seguinte.
2. **Se o registro já foi mergeado sem o número, não o edite** — registro
   mergeado é imutável (`painel/LEIA-ME.md`). Quem fecha a conta é um registro
   **NOVO** que cite os PRs devedores pelo número. Foi assim que #537 e #538
   foram quitados, pelo registro `20260830-005`.
3. **PR que só toca `painel/` é isento** (`so_toca_o_livro`) — é por isso que o
   registro-que-paga-a-dívida não gera dívida nova. Não conte com essa isenção
   para nada além disso.

**Origem.** 30/08/2026, numa sessão de "atualize o painel com o estado atual do
projeto": o espelho local estava 427 commits atrás, e depois de sincronizar,
o conferidor de contas apontou os dois merges órfãos da véspera. Registro:
`painel/registros/20260830-005-duas-entregas-nao-estavam-contadas-no-livro.js`.

---

**A ordem virou LEI COM PORTÃO em 31/08/2026** (`armadilhas/248`): o passo 1
acima deixou de ser conselho — `ci/mergear.py` confere o embarque na porta do
pouso (`checar_registro_embarcado`) e recusa PR de entrega cujo registro a
bordo não cite o próprio número. O erro desta armadilha agora é apanhado com
um commit de conserto, antes do merge, em vez de virar dívida no colo da
sessão seguinte.

---

**E em 06/09/2026 ganhou um degrau na MÃO, na hora do commit.** O que a porta
não muda é o preço: cada captura chega depois de uma rodada inteira de checks
(~8 min) e cobra um commit de conserto mais outra rodada. Medido no dia: uma
única sessão foi pega QUATRO vezes, pelo mesmo erro de ordem, e concluiu que
bastava disciplina — que é a garantia sem mecanismo que esta casa não aceita.
Desde então `.githooks/pre-commit` → `ci/registro_no_commit.py` recusa, no
instante do `git commit`, registro novo que não cita PR nenhum num ramo que
entrega, e a recusa reensina os três passos da ordem. A régua local é de
propósito mais frouxa que a da porta (basta citar ALGUM número; pendência de
carona passa junto do recibo; ramo que só escritura é isento) e "não consegui
medir" LIBERA o commit: quem faz valer continua sendo a porta — o degrau só
troca dez minutos por dez segundos.
