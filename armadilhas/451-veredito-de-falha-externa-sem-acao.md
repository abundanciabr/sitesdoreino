---
schema_version: 2
armadilha: 451
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/prestacao_de_contas.py
  detector: test_veredito_nao_pronto_por_falha_externa_sem_acao_e_recusado
sinal: 'veredito termina com falha externa de infraestrutura, mas nao diz se o mantenedor age, espera ou se a pista ja cuida'
gatilho:
  - ci/prestacao_de_contas.py
  - ci/tests/test_prestacao_de_contas.py
licao: 'Veredito NAO PRONTO por falha externa precisa carregar consequencia operacional no proprio veredito: quem age, o que fazer agora, quando reexecutar ou que nada depende do mantenedor.'
---

# 451: Veredito de falha externa sem ação

**Data:** 09/09/2026. **Onde:** prestação de contas de tarefa.

## Sintoma e causa

O relatório dizia que o PR estava correto, mas que o check do navegador
continuava vermelho por falha externa de infraestrutura. A frase pode ser
verdadeira e ainda assim deixar o mantenedor no escuro: ele não sabe se precisa
consertar infraestrutura, aguardar o provedor, reexecutar um check ou não fazer
nada.

A causa foi aceitar um veredito "NÃO PRONTO" com diagnóstico técnico, mas sem
consequência operacional na própria linha de veredito. O bloco anterior podia
conter uma ação, porém o veredito é a linha que o mantenedor lê primeiro.

## Regra

Quando o veredito for "NÃO PRONTO" por falha externa, bloqueio externo,
infraestrutura, provedor, GitHub, Google ou Actions, a linha precisa dizer a
ação: fazer, não fazer, aguardar, reexecutar, acompanhar pela pista ou declarar
que nada depende do mantenedor. Sem isso, o portão de prestação de contas
recusa o relatório.
