# Rodada de consultoria — O FÓRUM DA ESCOLA

**A pergunta desta rodada:** como construir um fórum excelente para a Meshcraft
Academy — alunos, professores e administradores — dentro deste sistema, e se o
caminho é instalar algo pronto ou construir na casa.

Aberta em 28/08/2026, a pedido do mantenedor.

## O que você faz (davi)

1. Abra `PROMPT-CONSULTORIA.md` e copie **tudo o que estiver abaixo da linha**.
2. Cole numa **conversa nova** de cada IA que você quiser ouvir. Uma IA por
   conversa — não misture, e não resuma o texto: o valor da resposta vem de o
   consultor ter a arquitetura real e as restrições na frente dele.
3. Copie a resposta e salve **nesta pasta**, como `resposta-<IA>.txt`
   (`resposta-GPT.txt`, `resposta-Gemini.txt`, `resposta-OPUS.txt`...). Mesmo
   padrão das rodadas anteriores, em `docs/paineis/` e
   `docs/consultorias/robos-sem-colisao/`.
4. Quando tiver as respostas, peça a uma sessão do Claude Code: *"leia as
   respostas em `docs/consultorias/forum-da-escola/` e me diga o veredito"*.

Não precisa ler as respostas antes. O trabalho de comparar, achar onde elas
discordam e transformar isso em decisão é do robô.

**Enquanto isso, há uma coisa só sua nesta pasta:** o `MEDIR-A-MEMORIA.md`. É um
bloco único para colar **dentro do servidor** que mostra quanta memória sobra de
verdade hoje. É o número que resolve a discussão do Discourse — sem ele, tanto a
sua leitura quanto a minha objeção são opinião. Pode fazer antes, durante ou
depois das consultas; quanto antes, melhor a síntese.

## Já existe uma resposta nesta pasta

O `MAPA-DAS-OPCOES.md` é a análise que a sessão fez **antes** de consultar
ninguém: as três famílias de caminho, o que descartei e por quê, a conta do
Discourse e uma recomendação assumida. Ele existe por dois motivos: para você
não ficar esperando as IAs para ter resposta, e para os consultores terem uma
posição concreta de que discordar — banca sem tese para atacar responde morno.

**Aquela recomendação está explicitamente aberta a ser derrubada por esta
rodada.**

## As quatro coisas que já estão decididas

Foram respondidas pelo mantenedor em 28/08/2026 e entram no prompt **como
dadas**, não como perguntas — para os consultores gastarem a resposta no que
ainda está em aberto:

1. **Fórum misto** — áreas públicas (que o Google indexa) e áreas trancadas por
   curso ou turma.
2. **O papel de professor nasce com o fórum**, com autoridade real.
3. **Não existe comunidade nenhuma hoje** — nem Discord, nem grupo de mensagens.
   O fórum nasce em salão vazio, e isso é um problema de desenho, não um detalhe.
4. **Escopo completo, nunca a versão reduzida** — a lei de
   `docs/decisoes/DECISAO-filosofia-de-escopo.md`, repetida dentro do prompt
   porque foi ela que impediu as rodadas anteriores de voltarem com "comece
   pequeno".

## O que acontece depois

A sessão que sintetizar produz, nesta mesma pasta:

- **`VEREDITO.md`** — onde os consultores concordaram, onde discordaram, e o que
  fica recomendado. Em português leigo, do jeito que o mantenedor lê.
- **Uma pergunta estruturada** com as bifurcações que só o mantenedor decide
  (`AskUserQuestion` — opção a opção, com o custo prático de cada uma).
- Depois da decisão dele: um `docs/decisoes/DECISAO-forum.md`, e só então a
  construção.

**Nada é construído antes disso, e há uma razão de lei:** um fórum é uma célula
nova, e célula nova exige que o mantenedor reabra nominalmente o congelamento
arquitetural — foi assim nas quatro anteriores (sugestões, identidade,
notificações, admin). O veredito desta rodada é o que ele vai ler para tomar
essa decisão.

## Fronteira com as outras rodadas

Esta rodada é sobre **o produto fórum**: o que ele é, para quem, com quais
capacidades, construído como. Ela **não** trata de como os robôs se organizam
para construí-lo (isso é a rodada `robos-sem-colisao/`) nem da tela de
acompanhamento do trabalho (`docs/paineis/`). Se um consultor começar a
redesenhar o processo de desenvolvimento, é sinal de que o prompt vazou escopo —
anote para a próxima versão.
