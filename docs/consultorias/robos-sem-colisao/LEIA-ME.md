# Rodada de consultoria — robôs em paralelo sem colidir

**A pergunta desta rodada:** como fazer vários robôs trabalharem livremente em
todo o sistema, ao mesmo tempo, sem que um atrapalhe ou apague o trabalho do
outro — resolvido por mecanismo, de forma definitiva.

Aberta em 28/08/2026, a pedido do mantenedor.

## O que você faz (davi)

1. Abra `PROMPT-CONSULTORIA.md` e copie **tudo o que estiver abaixo da linha**.
2. Cole numa **conversa nova** de cada IA que você quiser ouvir. Uma IA por
   conversa — não misture, e não resuma o texto: o valor da resposta vem de o
   consultor ter o histórico real de colisões na frente dele.
3. Copie a resposta e salve **nesta pasta**, como `resposta-<IA>.txt`
   (`resposta-GPT.txt`, `resposta-Gemini.txt`, `resposta-OPUS.txt`...). Mesmo
   padrão das rodadas anteriores, em `docs/paineis/`.
4. Quando tiver as respostas, peça a uma sessão do Claude Code: *"leia as
   respostas em `docs/consultorias/robos-sem-colisao/` e me diga o veredito"*.

Não precisa ler as respostas antes. O trabalho de comparar, achar onde elas
discordam e transformar isso em decisão é do robô.

## O que acontece depois

A sessão que sintetizar produz, nesta mesma pasta:

- **`VEREDITO.md`** — onde os consultores concordaram, onde discordaram, e o que
  fica recomendado. Em português leigo, do jeito que o mantenedor lê.
- **Uma pergunta estruturada** com as bifurcações que só o mantenedor decide
  (`AskUserQuestion` — opção a opção, com o custo prático de cada uma).
- Depois da decisão dele: um `docs/decisoes/DECISAO-*.md`, e a mudança de lei
  (CONSTITUICAO / RITOS) num PR próprio, com teste-guarda — porque neste projeto
  regra sem mecanismo não vale.

## Por que esta rodada existe

A não-colisão hoje é comprada com **restrição**: um worktree por agente,
1 PR = 1 célula, orçamento de 15 arquivos, merges em janela serial. Funciona —
mas cada trava nova estreita a fatia de sistema em que um robô pode mexer, e o
mantenedor quer o contrário: **liberdade ampla com segurança**.

As oito classes de colisão já medidas neste projeto estão no prompt, com data.
Três delas continuam curadas só por convenção escrita — e convenção escrita, em
sessão sob pressão, é a categoria de falha que mais custou aqui
(`docs/decisoes/RETROSPECTIVA-FASE-D.md`: *garantia sem mecanismo*).

## Fronteira com a outra rodada em andamento

A rodada **"Central de Orquestração de Trabalho"** (`docs/paineis/`) trata da
**tela**: o quadro que mostra a fila das tarefas e o que cada robô está fazendo.
Esta aqui trata do **andar de baixo**: o mecanismo que impede a colisão de
verdade. As duas se encontram — a tela precisa de um mecanismo embaixo, e o
mecanismo precisa de uma tela — mas as perguntas são diferentes, e misturá-las
faria os consultores responderem a mais fácil das duas.
