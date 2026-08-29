# Rodada de consultoria — CENTRAL DE ORQUESTRAÇÃO DE TRABALHO

**A pergunta desta rodada:** como dar ao painel uma fila de trabalho executável —
um quadro com as tarefas do projeto, o que pode rodar em paralelo, uma trava
para dois robôs não pegarem a mesma tarefa, e o prompt já pronto para colar na
sessão do robô.

Aberta em **28/08/2026**, a pedido do mantenedor. Três pareceres chegaram no
mesmo dia — `resposta-GPT.txt`, `resposta-OPUS.txt`, `resposta-Gemini.txt` — e
o Gemini ainda desenhou as cores do quadro
(`desenho-kanban-cores-Gemini.html`).

**Fechada em 29/08/2026**, com o `VEREDITO.md` desta pasta.

## A lição que esta rodada deixou (e que virou armadilha)

Os quatro arquivos ficaram **um dia parados fora do projeto** — na pasta local
`docs/paineis/Central de Orquestração de Trabalho/`, sem commit, sem registro
no livro. Faltou o passo do rito: pedir o veredito. E como o pedido nunca
entrou no livro, o painel — que só cobra o que está registrado — não tinha como
lembrar ninguém. A rodada só foi retomada porque o mantenedor lembrou dela.

A regra que fica: **abrir uma rodada de consultoria é criar a pasta em
`docs/consultorias/` E registrar no livro, no mesmo gesto.** O que não está no
livro não existe para o painel. A entrada completa está em `armadilhas/`
(procure por "consultoria" no `INDICE.md`).

## O molde (o mesmo das rodadas anteriores)

1. `PROMPT-...` → uma conversa nova por IA, o texto inteiro, sem resumir.
   (Nesta rodada o prompt não foi preservado — as perguntas aparecem no meio
   das próprias respostas, entre um bloco e outro.)
2. As respostas salvas nesta pasta, como `resposta-<IA>.txt`.
3. Uma sessão do Claude Code lê tudo e escreve o `VEREDITO.md`.
4. O veredito vira registro no livro — e o que ele decidir construir vira
   tarefa, nunca promessa solta.
