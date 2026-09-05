---
schema_version: 2
armadilha: 348
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: ci/tests/test_prestacao_de_contas.py
sinal:
  - "desde a última fala do usuário"
  - "inicio_da_janela"
---

# Obrigação escopada por "desde a última fala dele" é PERDOADA quando ele fala

**Sintoma:** um portão que cobra alguma coisa do agente (relatório, registro,
evidência) funciona nos testes, funciona no dia a dia, e **some exatamente na
sessão em que mais importava**. Nenhum erro, nenhuma recusa, nenhum rastro: ele
simplesmente decide que não há nada a cobrar.

Medido em 05/09/2026, no portão da prestação de contas, no dia em que ele
nasceu. A sessão abriu o PR #1092, mergeou e ficou esperando o deploy. No meio
das esperas o mantenedor respondeu uma pergunta curta — *"deixe assim: só admin
pode ver, ler"*. **A partir dali não houve mais nenhuma mudança no mundo:** só
turnos de espera. Como o portão media a janela aberta pela ÚLTIMA fala dele, a
resposta a "houve mudança nesta janela?" era não, em todos os turnos. A conversa
foi arquivada com "Aguardando." como última palavra, sem uma linha do que tinha
sido feito — que era o defeito exato que o portão existia para curar.

**Causa:** escopar a obrigação por "desde a última fala do usuário" parece
inofensivo (serve para não assombrar uma pergunta nova com trabalho velho), mas
transforma **a fala dele em quitação**. Ele não sabe que está perdoando dívida;
está só respondendo uma pergunta. E a forma mais comum de trabalho desta casa —
faz, pede pouso, espera — coloca quase sempre alguma fala dele DEPOIS do
trabalho e ANTES do fim.

**Solução:** dívida se paga com o pagamento, nunca com o devedor falando outra
coisa. Varra a **sessão inteira** e compare o último FATO devedor com o último
pagamento:

```python
# errado: a fala dele zera o passado
for entrada in entradas[inicio_da_janela(entradas):]: ...

# certo: a dívida atravessa as falas; só o relatório a quita
for entrada in entradas: ...
if ultima_prestacao is not None and ultima_prestacao > ultima_mudanca:
    return False  # pago
```

A janela continua útil — mas para outra coisa: saber o que pertence ao PEDIDO
ATUAL (o plano de abertura, por exemplo), nunca para decidir o que já é devido.

**O conserto que NÃO funcionou, escrito para ninguém refazer:** a primeira
tentativa foi adiar a cobrança até "não haver mais nada em voo", para o
relatório sair com o veredito do deploy dentro. O sinal parecia existir — a
tarefa nasce com `toolUseResult.taskId` e morre numa `<task-notification>` com
`<status>completed</status>`. **Ele não é confiável.** Medido no transcript
daquela mesma sessão: 4 tarefas de fundo tinham TERMINADO (o `✅` do desfecho
está no último evento de cada uma) e **nenhuma das 4 recebeu a notificação com
`<status>`**. Um portão apoiado nisso ficaria mudo justamente no caso
reclamado. Sinal que some sem avisar não vira guarda — e o custo de descobrir
isso foi um commit inteiro feito antes de medir.

**Como não cair de novo, em uma pergunta:** antes de escrever `desde a última
fala do usuário` num portão, pergunte — *"se ele responder qualquer coisa agora,
esta obrigação deveria sumir?"*. Se a resposta é não, a janela está errada.

**Parente próximo:** a [176](176-hook-fail-open-esconde-o-proprio-defeito-e-cala.md)
(hook que cala ao quebrar). A diferença é a origem do silêncio: lá o mecanismo
QUEBRA e a tolerância a falha apaga o rastro; aqui ele funciona perfeitamente e
**decide, corretamente segundo a própria régua, que não há nada a fazer**. Régua
errada é mais difícil de ver que código quebrado, porque tudo fica verde.

**Origem:** o portão da prestação de contas, 05/09/2026. Quem achou foi o
mantenedor, com uma captura de tela — não a suíte, que tinha 30 testes verdes, e
não a medição contra 40 transcripts, que rodou contra sessões sem fala dele
depois do trabalho.
