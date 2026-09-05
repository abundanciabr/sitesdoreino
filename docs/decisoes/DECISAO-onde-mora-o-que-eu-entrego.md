# DECISÃO: o que eu entrego para o mantenedor mora no site

**Decidida por ele em 05/09/2026.** As palavras dele, no pedido que virou lei:

> "Você consegue colocar esse artefato em uma página do site? E sempre criar
> isso no site ao invés de artefatos?"

## A lei, em uma frase

**Toda entrega para o mantenedor nasce dentro do site (`meshcraft.top`), nunca
como página solta fora dele.** Vale para análise, relatório, plano, painel,
comparação, resumo, lista, qualquer coisa que ele vá ler mais de uma vez.

## Por que

Uma página fora do site parece a entrega mais rápida, e é a mais cara. Quatro
motivos, todos medidos neste projeto:

1. **Ela não é editável por ele.** O site tem editor de documentos desde
   31/08/2026 porque ele pediu, com estas palavras: *"quero gerenciar / editar
   os documentos"*. Entrega fora do site nasce sem essa porta.
2. **Ela envelhece sozinha e ninguém percebe.** Uma análise com "40 votos"
   escrito dentro mente no primeiro voto novo. Dentro do site, o mesmo texto
   pode LER o número na hora de desenhar a tela.
3. **Ninguém de fora abre.** Já custou tempo dele em 31/08/2026: artefato do
   `claude.ai` é privado e nenhuma IA externa consegue lê-lo. O que mora no
   site tem endereço público quando precisa ter (`/mapa-ia/planos/`).
4. **Ela some do mapa.** O site tem menu, busca e o painel do dono; a página
   solta existe só enquanto o link estiver na mão de alguém.

## Onde exatamente, e como escolher

A pergunta que decide é uma só: **isto se apoia em fatos que o sistema já
conhece?**

| Se a entrega… | Ela mora em | Forma |
|---|---|---|
| **se apoia em fatos vivos** (votos, alunos, tarefas, dinheiro, estado de qualquer coisa) | uma **tela** em `/admin/`, calculada | código, com teste |
| **não depende de fato vivo** (plano, lei, explicação, roteiro) | o **editor de documentos**, `/admin/documentos/` | texto no banco, que ele edita |
| **precisa ser lida por uma IA de fora** | `/mapa-ia/planos/` | já era lei |

A primeira linha é a que engana. A tentação é escrever a análise inteira num
documento, porque é mais rápido: o resultado é uma fotografia que começa a
mentir no dia seguinte, e é a lista paralela que a lei anti-duplicação do
`CLAUDE.md` proíbe. **A divisão certa é fato vivo mais julgamento guardado** —
o padrão está implementado em `services/admin/apps/core/analise_da_caixa.py`, e
a armadilha `342` conta a história.

## O que continua permitido

- **Mandar um arquivo na conversa** (uma prévia, uma captura de tela, um
  rascunho para ele olhar antes de existir de verdade). Prévia não é entrega:
  ela morre no minuto seguinte, de propósito.
- **Texto curto direto na resposta.** Se cabe em dez linhas e ele não vai
  precisar disso amanhã, não precisa de página nenhuma.

## Quem faz valer

Ninguém, mecanicamente, e isso está declarado: esta lei mora em
`ci/leis-sem-mecanismo.txt`. Um portão que tentasse adivinhar "isto deveria ser
uma tela" reprovaria trabalho honesto e deixaria passar o descuido — e portão
que mede a coisa errada com precisão é como um portão morre. O que existe é o
`CLAUDE.md`, que toda sessão lê antes de começar.
